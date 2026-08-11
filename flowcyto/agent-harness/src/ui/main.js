/**
 * Anwendungslogik und Bedienoberflaeche.
 *
 * Dieses Modul verdrahtet ausschliesslich -- es enthaelt keine eigene Analytik.
 * Jede Ansicht liest ueber die Selektoren aus core/, jede Aenderung laeuft
 * ueber den Store zurueck. Deshalb zeigen Plot, Statistiktabelle,
 * Qualitaetsbericht und Befund immer denselben Stand.
 */

import {
  state, on, uid, addSample, addGate, updateGate, removeGate,
  gateById, gatePath, activeSample, setPatient, setReport, bump, invalidate,
} from '../core/store.js';
import { parseAny } from '../core/fcs.js';
import {
  transformFor, setTransform, invalidateSample, findParam,
  fluorParams, scatterParams, compensationStatus, channelValues,
} from '../core/data.js';
import { parseCompensationCSV, compensationToCSV } from '../core/compensation.js';
import {
  gateIndices, gateStats, orderedGates, standardPreGating,
  makeGate, autoQuadrants, gateFromEvents,
} from '../core/gating.js';
import { channelStats } from '../core/stats.js';
import { runQC } from '../core/qc.js';
import { applyPanel, evaluateMetrics } from '../core/strategy.js';
import { flowSOM, tsne, pca, buildMatrix, normalizeEmbedding } from '../core/cluster.js';
import { autoMapMarkers, canonicalMarker, markerInfo } from '../knowledge/markers.js';
import { PANELS, panelById, panelKategorien, scorePanelFit } from '../knowledge/panels.js';
import { bewertePanel, formatWert } from '../knowledge/rules.js';
import {
  REFERENZBEREICHE, REFERENZ_QUELLE, importReferenzen, exportReferenzen,
} from '../knowledge/reference.js';
import { erzeugeBefund, befundAlsText, befundAlsCSV } from '../report/befund.js';
import { alsFHIR } from '../report/fhir.js';
import { PlotView, zeichneHeatmap, zeichneMST, kanalName, kanalNameLang, CLUSTER_FARBEN } from './plot.js';

/* ================================================================== */
/* Hilfen                                                             */
/* ================================================================== */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

function h(tag, attrs = {}, ...kinder) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v);
  }
  for (const kind of kinder.flat()) {
    if (kind == null) continue;
    el.append(kind instanceof Node ? kind : document.createTextNode(String(kind)));
  }
  return el;
}

function status(text, art = '') {
  const el = $('#statusZeile');
  el.textContent = text;
  el.style.color = art === 'fehler' ? 'var(--crit)' : art === 'ok' ? 'var(--ok)' : '';
}

function zahl(v, n = 1) {
  return Number.isFinite(v) ? v.toFixed(n).replace('.', ',') : '–';
}

/**
 * Designwahl merken. In eingebetteten oder abgeschotteten Kontexten kann der
 * Zugriff auf localStorage eine Ausnahme werfen -- das darf die Anwendung
 * nicht beim Start zu Fall bringen.
 */
function merkeDesign(wert) {
  try {
    localStorage.setItem('flowcyto-theme', wert);
  } catch {
    /* Speicher nicht verfügbar: Designwahl gilt nur für diese Sitzung. */
  }
}

function leseDesign() {
  try {
    return localStorage.getItem('flowcyto-theme');
  } catch {
    return null;
  }
}

/** Tatsaechlich wirksames Design -- ausdrueckliche Wahl oder Systemeinstellung. */
function aktuellesDesign() {
  const gesetzt = document.documentElement.dataset.theme;
  if (gesetzt === 'dark' || gesetzt === 'light') return gesetzt;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function download(inhalt, dateiname, typ = 'text/plain;charset=utf-8') {
  const blob = new Blob([inhalt], { type: typ });
  const url = URL.createObjectURL(blob);
  const a = h('a', { href: url, download: dateiname });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Zustand der Oberflaeche, der nicht in den Datenstore gehoert. */
const ui = {
  werkzeug: 'zeiger',
  zeichnen: null,
  polygonPunkte: [],
  aktiveKachel: null,
  panelErgebnis: null,
  clusterErgebnis: null,
  referenzKatalog: REFERENZBEREICHE,
  referenzQuelle: REFERENZ_QUELLE,
  views: new Map(),
};

/* ================================================================== */
/* Dateien laden                                                      */
/* ================================================================== */

async function dateienLaden(dateien) {
  let geladen = 0;
  for (const datei of dateien) {
    try {
      const puffer = await datei.arrayBuffer();
      const probe = parseAny(puffer, datei.name);
      addSample(probe);
      state.activeSampleId = probe.id;
      Object.assign(state.markerMap, autoMapMarkers(probe));
      geladen++;
    } catch (err) {
      status(`${datei.name}: ${err.message}`, 'fehler');
      console.error(err);
    }
  }
  if (!geladen) return;

  const probe = activeSample();
  if (!state.gates.length) standardPreGating(probe);
  if (!state.layout.length) standardPlots(probe);
  panelVorschlagen(probe);
  runQC(probe);
  status(`${geladen} Datei(en) geladen · ${probe.nEvents.toLocaleString('de-DE')} Ereignisse · ${probe.meta.cytometer}`, 'ok');
  allesZeichnen();
}

/** Legt sinnvolle Startplots an: Streulicht, Singlets, CD45/SSC. */
function standardPlots(probe) {
  const sc = scatterParams(probe);
  const gates = orderedGates();
  const wurzel = gates.find((g) => g.gate.name.startsWith('Zellen'))?.gate.id || null;
  const singlets = gates.find((g) => g.gate.name === 'Singlets')?.gate.id || wurzel;

  state.layout = [];
  if (sc.fscA >= 0 && sc.sscA >= 0) {
    state.layout.push({ id: uid('plot'), type: 'density', gateId: null, xParam: sc.fscA, yParam: sc.sscA });
  }
  if (sc.fscA >= 0 && sc.fscH >= 0) {
    state.layout.push({ id: uid('plot'), type: 'density', gateId: wurzel, xParam: sc.fscA, yParam: sc.fscH });
  }
  const cd45 = findParam(probe, 'CD45', state.markerMap);
  if (cd45 >= 0 && sc.sscA >= 0) {
    state.layout.push({ id: uid('plot'), type: 'density', gateId: singlets, xParam: cd45, yParam: sc.sscA });
  }
  const fl = fluorParams(probe).filter((p) => p !== cd45);
  if (fl.length >= 2) {
    state.layout.push({ id: uid('plot'), type: 'density', gateId: singlets, xParam: fl[0], yParam: fl[1] });
  }
}

function panelVorschlagen(probe) {
  const marker = Object.values(state.markerMap);
  if (!marker.length) return;
  const treffer = PANELS.map((p) => scorePanelFit(p, marker)).sort((a, b) => b.score - a.score);
  const beste = treffer[0];
  if (beste && beste.score >= 0.75) {
    $('#panelAuswahl').value = beste.panel.id;
    $('#btnPanelAnwenden').disabled = false;
    status(`Vorschlag: Panel "${beste.panel.name}" (${beste.treffer}/${beste.pflicht} Pflichtmarker vorhanden)`);
  }
}

/* ================================================================== */
/* Probenliste und Gate-Baum                                          */
/* ================================================================== */

function zeichneProbenliste() {
  const ziel = $('#probenliste');
  ziel.textContent = '';
  if (!state.samples.length) {
    ziel.append(h('div', { class: 'leer' }, 'Noch keine Datei geladen'));
    return;
  }
  for (const s of state.samples) {
    const aktiv = s.id === state.activeSampleId;
    ziel.append(
      h('div', {
        class: `eintrag${aktiv ? ' aktiv' : ''}`,
        onclick: () => {
          state.activeSampleId = s.id;
          ui.clusterErgebnis = null;
          allesZeichnen();
        },
      },
        h('div', {}, s.name),
        h('div', { class: 'meta' }, `${s.nEvents.toLocaleString('de-DE')} Ereignisse · ${s.nParams} Kanäle`),
      ),
    );
  }
}

function zeichneGateBaum() {
  const ziel = $('#gatebaum');
  const probe = activeSample();
  ziel.textContent = '';
  if (!probe || !state.gates.length) {
    ziel.append(h('div', { class: 'leer' }, 'Keine Gates'));
    return;
  }
  for (const { gate, depth } of orderedGates()) {
    const st = gateStats(probe, gate.id);
    ziel.append(
      h('div', {
        class: `knoten${gate.id === state.activeGateId ? ' aktiv' : ''}${gate.auto?.vorlaeufig ? ' vorlaeufig' : ''}`,
        style: `padding-left:${4 + depth * 13}px`,
        title: `${gatePath(gate.id).join(' > ')}\n${st.count.toLocaleString('de-DE')} Ereignisse\n${gate.auto ? 'Verfahren: ' + gate.auto.method : 'manuell'}`,
        onclick: () => {
          state.activeGateId = gate.id === state.activeGateId ? null : gate.id;
          zeichneGateBaum();
          zeichneInspektor();
          zeichnePlots();
        },
      },
        h('span', { class: 'punkt', style: `background:${gate.color}` }),
        h('span', { class: 'name' }, gate.name),
        h('span', { class: 'zahl' }, `${zahl(st.pctParent)} %`),
      ),
    );
  }
}

/* ================================================================== */
/* Plots                                                              */
/* ================================================================== */

function zeichnePlots() {
  const raster = $('#plotRaster');
  const probe = activeSample();
  if (!probe) {
    raster.textContent = '';
    raster.append(h('div', { class: 'leer' }, 'Datei öffnen, um zu beginnen'));
    return;
  }
  if (!state.layout.length) standardPlots(probe);

  // Kacheln nur neu aufbauen, wenn sich ihre Zusammensetzung geaendert hat
  const vorhandene = new Set([...raster.children].map((c) => c.dataset.id));
  const gewuenschte = new Set(state.layout.map((t) => t.id));
  if (vorhandene.size !== gewuenschte.size || [...gewuenschte].some((id) => !vorhandene.has(id))) {
    raster.textContent = '';
    for (const tile of state.layout) raster.append(kachelBauen(tile, probe));
  }

  for (const tile of state.layout) {
    const view = ui.views.get(tile.id);
    if (!view) continue;
    view.spec = {
      ...tile,
      sample: probe,
      backgateId: state.ui.showBackgate ? elterngateVon(tile.gateId) : null,
      clusterZuordnung: tile.zeigeCluster ? ui.clusterErgebnis : null,
      eventLimit: state.ui.eventLimit,
    };
    view.render();
    kachelKopfAktualisieren(tile, probe);
  }
}

function elterngateVon(gateId) {
  const g = gateId ? gateById(gateId) : null;
  return g ? g.parentId : null;
}

function kachelBauen(tile, probe) {
  const kachel = h('div', { class: 'kachel', 'data-id': tile.id });

  const gateWahl = h('select', {
    title: 'Dargestellte Population',
    onchange: (e) => {
      tile.gateId = e.target.value || null;
      zeichnePlots();
    },
  });
  const xWahl = h('select', { title: 'X-Achse', onchange: (e) => { tile.xParam = +e.target.value; zeichnePlots(); } });
  const yWahl = h('select', { title: 'Y-Achse', onchange: (e) => { tile.yParam = +e.target.value; zeichnePlots(); } });

  const kopf = h('div', { class: 'kopf' },
    gateWahl, xWahl, yWahl,
    h('button', {
      title: 'Als Histogramm / Zweikanaldarstellung umschalten',
      onclick: () => {
        tile.type = tile.type === 'histogram' ? 'density' : 'histogram';
        zeichnePlots();
      },
    }, '↕'),
    h('button', { title: 'Plot entfernen', onclick: () => {
      state.layout = state.layout.filter((t) => t.id !== tile.id);
      ui.views.delete(tile.id);
      zeichnePlots();
    } }, '×'),
  );

  const canvas = h('canvas');
  kachel.append(kopf, canvas);
  kachel._auswahl = { gateWahl, xWahl, yWahl };

  const view = new PlotView(canvas, { ...tile, sample: probe });
  ui.views.set(tile.id, view);
  interaktionAnbinden(canvas, view, tile, kachel);
  return kachel;
}

function kachelKopfAktualisieren(tile, probe) {
  const kachel = $(`.kachel[data-id="${tile.id}"]`);
  if (!kachel?._auswahl) return;
  const { gateWahl, xWahl, yWahl } = kachel._auswahl;

  const gateOptionen = [{ v: '', t: 'Alle Ereignisse' }, ...orderedGates().map(({ gate, depth }) => ({
    v: gate.id, t: `${'  '.repeat(depth)}${gate.name}`,
  }))];
  fuelleAuswahl(gateWahl, gateOptionen, tile.gateId || '');

  const kanalOptionen = probe.params.map((p, i) => ({ v: i, t: kanalNameLang(probe, i) }));
  fuelleAuswahl(xWahl, kanalOptionen, tile.xParam);
  fuelleAuswahl(yWahl, kanalOptionen, tile.yParam);
  yWahl.style.display = tile.type === 'histogram' ? 'none' : '';
  kachel.classList.toggle('zeiger', ui.werkzeug === 'zeiger');
}

function fuelleAuswahl(select, optionen, wert) {
  const signatur = optionen.map((o) => o.v).join('|');
  if (select._signatur !== signatur) {
    select.textContent = '';
    for (const o of optionen) select.append(h('option', { value: o.v }, o.t));
    select._signatur = signatur;
  }
  select.value = String(wert ?? '');
}

/* ------------------------------------------------------------------ */
/* Gate-Interaktion                                                    */
/* ------------------------------------------------------------------ */

function interaktionAnbinden(canvas, view, tile, kachel) {
  const posVon = (ev) => {
    const r = canvas.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top];
  };

  canvas.addEventListener('mousedown', (ev) => {
    const [px, py] = posVon(ev);
    if (!view.imPlot(px, py)) return;
    ui.aktiveKachel = tile.id;

    if (ui.werkzeug === 'zeiger') {
      const treffer = view.gateAn(px, py);
      state.activeGateId = treffer ? treffer.id : null;
      zeichneGateBaum();
      zeichneInspektor();
      zeichnePlots();
      return;
    }

    if (ui.werkzeug === 'quadrant') {
      const [sx, sy] = view.toScale(px, py);
      const gates = autoQuadrants(activeSample(), tile.xParam, tile.yParam, tile.gateId, {
        xThreshold: sx, yThreshold: sy,
      });
      for (const g of gates) addGate(g);
      status('Quadranten gesetzt');
      nachGateAenderung();
      return;
    }

    if (ui.werkzeug === 'polygon') {
      const [sx, sy] = view.toScale(px, py);
      ui.polygonPunkte.push([sx, sy]);
      vorschauZeichnen(view, tile);
      return;
    }

    ui.zeichnen = { tileId: tile.id, start: view.toScale(px, py), aktuell: view.toScale(px, py) };
  });

  canvas.addEventListener('mousemove', (ev) => {
    const [px, py] = posVon(ev);
    if (ui.zeichnen?.tileId === tile.id) {
      ui.zeichnen.aktuell = view.toScale(px, py);
      vorschauZeichnen(view, tile);
    } else if (ui.werkzeug === 'polygon' && ui.polygonPunkte.length && ui.aktiveKachel === tile.id) {
      ui.polygonVorschau = view.toScale(px, py);
      vorschauZeichnen(view, tile);
    }
  });

  canvas.addEventListener('mouseup', () => {
    if (ui.zeichnen?.tileId !== tile.id) return;
    const { start, aktuell } = ui.zeichnen;
    ui.zeichnen = null;
    if (Math.abs(start[0] - aktuell[0]) < 0.01 && Math.abs(start[1] - aktuell[1]) < 0.01) {
      zeichnePlots();
      return;
    }
    gateAusZeichnung(tile, start, aktuell);
  });

  // Polygon abschliessen
  canvas.addEventListener('dblclick', () => {
    if (ui.werkzeug !== 'polygon' || ui.polygonPunkte.length < 3) return;
    polygonAbschliessen(tile);
  });
  canvas.addEventListener('contextmenu', (ev) => {
    if (ui.werkzeug === 'polygon' && ui.polygonPunkte.length >= 3) {
      ev.preventDefault();
      polygonAbschliessen(tile);
    }
  });
}

function vorschauZeichnen(view, tile) {
  view.render();
  const ctx = view.canvas.getContext('2d');
  const l = view.layout;
  ctx.save();
  ctx.scale(l.dpr, l.dpr);
  ctx.strokeStyle = 'var(--accent)';
  ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4cc9f0';
  ctx.lineWidth = 1.4;
  ctx.setLineDash([4, 3]);

  if (ui.zeichnen?.tileId === tile.id) {
    const [x1, y1] = view.toPixel(...ui.zeichnen.start);
    const [x2, y2] = view.toPixel(...ui.zeichnen.aktuell);
    if (ui.werkzeug === 'rect') {
      ctx.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
    } else if (ui.werkzeug === 'ellipse') {
      ctx.beginPath();
      ctx.ellipse((x1 + x2) / 2, (y1 + y2) / 2, Math.abs(x2 - x1) / 2, Math.abs(y2 - y1) / 2, 0, 0, Math.PI * 2);
      ctx.stroke();
    } else if (ui.werkzeug === 'interval') {
      ctx.beginPath();
      ctx.moveTo(x1, l.y1); ctx.lineTo(x1, l.y0);
      ctx.moveTo(x2, l.y1); ctx.lineTo(x2, l.y0);
      ctx.stroke();
    }
  } else if (ui.polygonPunkte.length) {
    ctx.beginPath();
    ui.polygonPunkte.forEach((p, i) => {
      const [px, py] = view.toPixel(p[0], p[1]);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    if (ui.polygonVorschau) {
      const [px, py] = view.toPixel(...ui.polygonVorschau);
      ctx.lineTo(px, py);
    }
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.restore();
}

function gateAusZeichnung(tile, start, ende) {
  const name = neuerGateName();
  let gate = null;
  if (ui.werkzeug === 'rect') {
    gate = makeGate({
      name, parentId: tile.gateId, type: 'rect', xParam: tile.xParam, yParam: tile.yParam,
      geom: { x1: start[0], y1: start[1], x2: ende[0], y2: ende[1] },
    });
  } else if (ui.werkzeug === 'ellipse') {
    gate = makeGate({
      name, parentId: tile.gateId, type: 'ellipse', xParam: tile.xParam, yParam: tile.yParam,
      geom: {
        cx: (start[0] + ende[0]) / 2, cy: (start[1] + ende[1]) / 2,
        rx: Math.abs(ende[0] - start[0]) / 2, ry: Math.abs(ende[1] - start[1]) / 2, angle: 0,
      },
    });
  } else if (ui.werkzeug === 'interval') {
    gate = makeGate({
      name, parentId: tile.gateId, type: 'interval', xParam: tile.xParam,
      geom: { min: Math.min(start[0], ende[0]), max: Math.max(start[0], ende[0]) },
    });
  }
  if (gate) {
    addGate(gate);
    state.activeGateId = gate.id;
    nachGateAenderung();
  }
}

function polygonAbschliessen(tile) {
  const gate = makeGate({
    name: neuerGateName(), parentId: tile.gateId, type: 'polygon',
    xParam: tile.xParam, yParam: tile.yParam, geom: { points: [...ui.polygonPunkte] },
  });
  ui.polygonPunkte = [];
  ui.polygonVorschau = null;
  addGate(gate);
  state.activeGateId = gate.id;
  nachGateAenderung();
}

function neuerGateName() {
  const n = state.gates.filter((g) => /^Gate \d+$/.test(g.name)).length + 1;
  return `Gate ${n}`;
}

/** Nach jeder Gate-Aenderung alle abhaengigen Ansichten erneuern. */
function nachGateAenderung() {
  if (ui.panelErgebnis) auswertungAktualisieren();
  zeichneGateBaum();
  zeichnePlots();
  zeichneInspektor();
  zeichneStatistik();
  zeichneBefund();
}

/* ================================================================== */
/* Panel anwenden und auswerten                                       */
/* ================================================================== */

function panelAnwenden() {
  const probe = activeSample();
  const panel = panelById($('#panelAuswahl').value);
  if (!probe || !panel) return;

  // Die Vorlage beschreibt die vollstaendige Strategie einschliesslich
  // Vorgating. Bestehende Gates werden deshalb verworfen -- sonst entstuenden
  // zwei parallele Hierarchien mit denselben Populationen.
  const verworfen = state.gates.length;
  state.gates = [];
  state.activeGateId = null;
  invalidate();
  bump('gates');

  const ergebnis = applyPanel(probe, panel, { markerMap: state.markerMap });
  state.panelId = panel.id;
  ui.panelErgebnis = ergebnis;

  plotsAusPanel(probe, panel, ergebnis.stepGates);
  auswertungAktualisieren();

  const zusatz = verworfen ? ` (${verworfen} vorherige Gates ersetzt)` : '';
  const meldung = ergebnis.fehlend.length
    ? `Panel angewandt${zusatz}, ${ergebnis.fehlend.length} Schritt(e) nicht möglich: ${ergebnis.fehlend.join('; ')}`
    : `Panel "${panel.name}" vollständig angewandt${zusatz}`;
  status(meldung, ergebnis.fehlend.length ? '' : 'ok');
  allesZeichnen();
}

/** Legt fuer jeden Gating-Schritt einen Plot an -- die Strategie wird sichtbar. */
function plotsAusPanel(probe, panel, stepGates) {
  state.layout = [];
  ui.views.clear();
  for (const step of panel.gating) {
    const gateId = stepGates[step.id];
    if (!gateId) continue;
    const gate = gateById(gateId);
    if (!gate) continue;
    const elternId = gate.parentId || null;
    if (gate.type === 'interval') {
      state.layout.push({ id: uid('plot'), type: 'histogram', gateId: elternId, xParam: gate.xParam, yParam: gate.xParam });
    } else if (gate.xParam !== undefined && gate.yParam !== undefined) {
      state.layout.push({ id: uid('plot'), type: 'density', gateId: elternId, xParam: gate.xParam, yParam: gate.yParam });
    }
  }
  if (!state.layout.length) standardPlots(probe);
}

/** Berechnet Kennzahlen, Referenzbewertung und Scores neu. */
function auswertungAktualisieren() {
  const probe = activeSample();
  const panel = panelById(state.panelId);
  if (!probe || !panel || !ui.panelErgebnis) return null;

  const { metriken, ctx } = evaluateMetrics(probe, panel, ui.panelErgebnis.stepGates, state.markerMap);
  const bewertung = bewertePanel(probe, panel, ctx, metriken, state.patient, ui.referenzKatalog);
  ui.auswertung = { panel, metriken, ctx, bewertung };
  return ui.auswertung;
}

/* ================================================================== */
/* Statistik                                                          */
/* ================================================================== */

function zeichneStatistik() {
  const ziel = $('#inhaltStatistik');
  const probe = activeSample();
  ziel.textContent = '';
  if (!probe) {
    ziel.append(h('div', { class: 'leer' }, 'Keine Probe geladen'));
    return;
  }

  const auswertung = ui.auswertung || auswertungAktualisieren();

  /* --- Panel-Kennzahlen --- */
  if (auswertung) {
    const karte = h('div', { class: 'karte' }, h('h3', {}, `Kennzahlen — ${auswertung.panel.name}`));
    const tab = h('table', {},
      h('thead', {}, h('tr', {},
        h('th', {}, 'Kennzahl'), h('th', { class: 'zahl' }, 'Wert'),
        h('th', { class: 'zahl' }, 'absolut'), h('th', {}, 'Referenz'), h('th', {}, 'Hinweis'))),
    );
    const koerper = h('tbody');
    for (const m of auswertung.bewertung.metriken) {
      koerper.append(h('tr', { class: m.hinweis ? 'hervor' : '' },
        h('td', {}, m.name),
        h('td', { class: 'zahl' }, formatWert(m)),
        h('td', { class: 'zahl' }, Number.isFinite(m.absolut) ? `${zahl(m.absolut, 0)} /µl` : '–'),
        h('td', { class: `status-${m.bewertung?.status || 'unbekannt'}` }, m.bewertung?.text || '–'),
        h('td', {}, m.hinweis || m.fehler || ''),
      ));
    }
    tab.append(koerper);
    karte.append(tab);
    ziel.append(karte);

    /* --- Scores --- */
    for (const s of auswertung.bewertung.scores) {
      const karte2 = h('div', { class: 'karte' },
        h('h3', {}, `${s.name}: ${s.bewertung}${Number.isFinite(s.punkte) ? ` (${s.punkte}/${s.maximum})` : ''}`),
      );
      const t = h('table', {}, h('tbody', {}, ...(s.kriterien || []).map((k) =>
        h('tr', {},
          h('td', { style: 'width:26px' }, k.gemessen ? (k.erfuellt ? '✓' : '·') : '?'),
          h('td', {}, k.name),
          h('td', { class: 'zahl' }, k.wert),
        ))));
      karte2.append(t, h('p', { style: 'margin-top:8px' }, s.text));
      if (s.quelle) karte2.append(h('p', { style: 'color:var(--fg-muted);font-size:11px' }, `Grundlage: ${s.quelle}`));
      ziel.append(karte2);
    }

    /* --- Differentialdiagnose --- */
    if (auswertung.bewertung.ddx.length) {
      const karte3 = h('div', { class: 'karte' },
        h('h3', {}, 'Differentialdiagnostische Einordnung'),
        h('p', { style: 'color:var(--fg-muted)' }, 'Musterabgleich der Software mit dem Entitätskatalog — ein Vorschlag, keine Diagnose.'),
      );
      for (const d of auswertung.bewertung.ddx) {
        karte3.append(
          h('div', { style: 'margin-top:10px' },
            h('div', { class: 'reihe' },
              h('strong', { style: 'flex:1' }, d.entitaet.name),
              h('span', { class: 'zahl', style: 'flex:none' }, `${(d.passung * 100).toFixed(0)} %`)),
            h('div', { class: 'balken', style: 'margin:3px 0 5px' }, h('div', { style: `width:${d.passung * 100}%` })),
            d.stuetzend.length ? h('div', { style: 'font-size:11px' }, `Stützend: ${d.stuetzend.join(', ')}`) : null,
            d.widersprechend.length ? h('div', { style: 'font-size:11px;color:var(--warn)' }, `Abweichend: ${d.widersprechend.join(', ')}`) : null,
            d.nichtGemessen.length ? h('div', { style: 'font-size:11px;color:var(--fg-muted)' }, `Nicht gemessen: ${d.nichtGemessen.join(', ')}`) : null,
          ),
        );
      }
      ziel.append(karte3);
    }
  }

  /* --- Populationsstatistik aller Gates --- */
  const karteG = h('div', { class: 'karte' }, h('h3', {}, 'Populationen'));
  const tabG = h('table', {}, h('thead', {}, h('tr', {},
    h('th', {}, 'Population'), h('th', { class: 'zahl' }, 'Ereignisse'),
    h('th', { class: 'zahl' }, '% Eltern'), h('th', { class: 'zahl' }, '% gesamt'), h('th', {}, 'Verfahren'))));
  const koerperG = h('tbody');
  for (const { gate, depth } of orderedGates()) {
    const st = gateStats(probe, gate.id);
    koerperG.append(h('tr', {},
      h('td', { style: `padding-left:${8 + depth * 14}px` }, gate.name),
      h('td', { class: 'zahl' }, st.count.toLocaleString('de-DE')),
      h('td', { class: 'zahl' }, zahl(st.pctParent, 2)),
      h('td', { class: 'zahl' }, zahl(st.pctTotal, 2)),
      h('td', { style: 'font-size:11px;color:var(--fg-muted)' }, gate.auto?.method || 'manuell'),
    ));
  }
  tabG.append(koerperG);
  karteG.append(tabG);
  ziel.append(karteG);

  /* --- Kanalstatistik der ausgewaehlten Population --- */
  const gateId = state.activeGateId;
  const karteK = h('div', { class: 'karte' },
    h('h3', {}, `Kanalstatistik — ${gateId ? gateById(gateId).name : 'alle Ereignisse'}`));
  const idx = gateIndices(probe, gateId);
  const tabK = h('table', {}, h('thead', {}, h('tr', {},
    h('th', {}, 'Kanal'), h('th', { class: 'zahl' }, 'Median'), h('th', { class: 'zahl' }, 'geom. Mittel'),
    h('th', { class: 'zahl' }, 'Mittelwert'), h('th', { class: 'zahl' }, 'rSD'), h('th', { class: 'zahl' }, 'rCV %'))));
  const koerperK = h('tbody');
  for (let i = 0; i < probe.nParams; i++) {
    const st = channelStats(channelValues(probe, i), idx);
    koerperK.append(h('tr', {},
      h('td', {}, kanalNameLang(probe, i)),
      h('td', { class: 'zahl' }, zahl(st.median, 0)),
      h('td', { class: 'zahl' }, zahl(st.gmfi, 0)),
      h('td', { class: 'zahl' }, zahl(st.mean, 0)),
      h('td', { class: 'zahl' }, zahl(st.rsd, 0)),
      h('td', { class: 'zahl' }, zahl(st.rcv, 1)),
    ));
  }
  tabK.append(koerperK);
  karteK.append(tabK);
  ziel.append(karteK);

  ziel.append(h('div', { class: 'reihe nichtdrucken' },
    h('button', { onclick: () => exportStatistikCSV() }, 'Statistik als CSV'),
    h('span', { style: 'flex:1' }),
  ));
}

function exportStatistikCSV() {
  const probe = activeSample();
  if (!probe) return;
  const zeilen = [['Population', 'Ereignisse', 'Prozent_Eltern', 'Prozent_Gesamt', 'Pfad', 'Verfahren']];
  for (const { gate } of orderedGates()) {
    const st = gateStats(probe, gate.id);
    zeilen.push([gate.name, st.count, st.pctParent.toFixed(3), st.pctTotal.toFixed(3), gatePath(gate.id).join(' > '), gate.auto?.method || 'manuell']);
  }
  download(zeilen.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n'),
    `${probe.name}_populationen.csv`, 'text/csv;charset=utf-8');
}

/* ================================================================== */
/* Qualitaetskontrolle                                                */
/* ================================================================== */

function zeichneQC() {
  const ziel = $('#inhaltQC');
  const probe = activeSample();
  ziel.textContent = '';
  if (!probe) {
    ziel.append(h('div', { class: 'leer' }, 'Keine Probe geladen'));
    return;
  }
  const qc = probe.qc || runQC(probe);

  ziel.append(h('div', { class: `hinweisbox ${qc.overall === 'ok' ? 'info' : qc.overall}` },
    h('strong', {}, `Gesamtbewertung: ${qc.overall}`),
    h('p', {}, qc.summary),
  ));

  for (const c of qc.checks) {
    ziel.append(h('div', { class: 'karte' },
      h('div', { class: 'reihe' },
        h('h3', { style: 'flex:1;margin:0' }, c.label),
        h('span', { class: `marke ${c.status}`, style: 'flex:none' }, c.status),
        h('span', { class: 'zahl', style: 'flex:none' }, c.value),
      ),
      h('p', { style: 'margin-top:6px;color:var(--fg-muted)' }, c.detail),
    ));
  }

  ziel.append(h('div', { class: 'reihe nichtdrucken' },
    h('button', { onclick: () => { runQC(probe); zeichneQC(); zeichneBefund(); status('Qualitätskontrolle neu berechnet'); } },
      'Neu berechnen'),
    h('span', { style: 'flex:1' }),
  ));
}

/* ================================================================== */
/* Clusteranalyse                                                     */
/* ================================================================== */

function clusterBasisFuellen() {
  const auswahl = $('#clusterBasis');
  const optionen = [{ v: '', t: 'Alle Ereignisse' }, ...orderedGates().map(({ gate, depth }) => ({
    v: gate.id, t: `${'  '.repeat(depth)}${gate.name}`,
  }))];
  fuelleAuswahl(auswahl, optionen, auswahl.value);
}

async function clusterBerechnen() {
  const probe = activeSample();
  if (!probe) return;
  const verfahren = $('#clusterVerfahren').value;
  const gateId = $('#clusterBasis').value || null;
  const k = Math.max(2, Math.min(18, +$('#clusterAnzahl').value || 12));
  const marker = fluorParams(probe);
  if (marker.length < 2) {
    status('Für eine Clusteranalyse werden mindestens zwei Fluoreszenzkanäle benötigt.', 'fehler');
    return;
  }

  status('Clusteranalyse läuft …');
  $('#btnClusterStart').disabled = true;
  await new Promise((r) => setTimeout(r, 30)); // Oberflaeche aktualisieren lassen

  try {
    const idx = gateIndices(probe, gateId);
    if (verfahren === 'flowsom') {
      ui.clusterErgebnis = flowSOM(probe, marker, idx, { nMeta: k, maxEvents: 20000 });
      if (!ui.clusterErgebnis) throw new Error('Zu wenige Ereignisse für die gewählte Clusterzahl.');
    } else if (verfahren === 'tsne') {
      const { rows, events } = buildMatrix(probe, marker, idx, 1200);
      const punkte = normalizeEmbedding(tsne(rows, { perplexity: Math.min(30, Math.floor(rows.length / 5)) }));
      ui.clusterErgebnis = { einbettung: { punkte, titel: `t-SNE, ${rows.length} Ereignisse (Stichprobe)` }, events, params: marker };
    } else {
      const { rows, events } = buildMatrix(probe, marker, idx, 20000);
      const { projection, explained } = pca(rows, 2);
      const punkte = normalizeEmbedding(projection);
      ui.clusterErgebnis = {
        einbettung: { punkte, titel: `PCA — PC1 ${explained[0].toFixed(1)} %, PC2 ${explained[1].toFixed(1)} % erklärte Varianz` },
        events, params: marker,
      };
    }
    status('Clusteranalyse abgeschlossen', 'ok');
  } catch (err) {
    status(`Clusteranalyse fehlgeschlagen: ${err.message}`, 'fehler');
    ui.clusterErgebnis = null;
  }
  $('#btnClusterStart').disabled = false;
  zeichneCluster();
  zeichnePlots();
}

function zeichneCluster() {
  const ziel = $('#clusterAusgabe');
  const probe = activeSample();
  ziel.textContent = '';
  const e = ui.clusterErgebnis;
  if (!probe || !e) {
    ziel.append(h('div', { class: 'leer' }, 'Noch keine Analyse berechnet'));
    return;
  }

  if (e.einbettung) {
    const karte = h('div', { class: 'karte' }, h('h3', {}, 'Einbettung'));
    const canvas = h('canvas', { style: 'width:100%;height:420px;display:block' });
    karte.append(canvas);
    ziel.append(karte);
    const view = new PlotView(canvas, { sample: probe, type: 'embedding', embedding: e.einbettung, xParam: 0, yParam: 0 });
    requestAnimationFrame(() => view.render());
    return;
  }

  // FlowSOM: Heatmap, Spannbaum und Clustertabelle
  const karteH = h('div', { class: 'karte' }, h('h3', {}, 'Medianexpression je Metacluster'));
  const cH = h('canvas', { style: `width:100%;height:${Math.max(260, 120 + e.profiles.length * 26)}px;display:block` });
  karteH.append(cH);
  ziel.append(karteH);

  const karteM = h('div', { class: 'karte' }, h('h3', {}, 'Selbstorganisierende Karte'));
  const cM = h('canvas', { style: 'width:100%;height:340px;display:block' });
  karteM.append(cM);
  ziel.append(karteM);

  const karteT = h('div', { class: 'karte' }, h('h3', {}, 'Cluster'));
  const tab = h('table', {}, h('thead', {}, h('tr', {},
    h('th', {}, ''), h('th', {}, 'Cluster'), h('th', { class: 'zahl' }, 'Ereignisse'),
    h('th', { class: 'zahl' }, 'Anteil'), h('th', {}, 'Auffällige Marker'), h('th', {}, ''))));
  const koerper = h('tbody');
  for (const p of e.profiles) {
    // Marker mit der staerksten Abweichung vom Gesamtmedian benennen
    const auffaellig = p.profile
      .map((v, j) => ({ name: kanalName(probe, e.params[j]), v }))
      .sort((a, b) => b.v - a.v)
      .slice(0, 4)
      .filter((m) => m.v > 0.35)
      .map((m) => m.name);
    koerper.append(h('tr', {},
      h('td', {}, h('span', { class: 'punkt', style: `display:inline-block;width:10px;height:10px;border-radius:2px;background:${CLUSTER_FARBEN[p.cluster % CLUSTER_FARBEN.length]}` })),
      h('td', {}, `Cluster ${p.cluster + 1}`),
      h('td', { class: 'zahl' }, p.n.toLocaleString('de-DE')),
      h('td', { class: 'zahl' }, `${zahl(p.fraction, 2)} %`),
      h('td', {}, auffaellig.join(', ') || '–'),
      h('td', {}, h('button', {
        class: 'nichtdrucken',
        title: 'Cluster als Polygon-Gate übernehmen — erscheint danach in Statistik und Befund',
        onclick: () => clusterAlsGate(p),
      }, 'als Gate')),
    ));
  }
  tab.append(koerper);
  karteT.append(tab);
  ziel.append(karteT);

  requestAnimationFrame(() => {
    zeichneHeatmap(cH, e, probe);
    zeichneMST(cM, e);
  });
}

function clusterAlsGate(profil) {
  const probe = activeSample();
  const tile = state.layout[0];
  const xParam = tile ? tile.xParam : ui.clusterErgebnis.params[0];
  const yParam = tile ? tile.yParam : ui.clusterErgebnis.params[1];
  const gate = gateFromEvents(probe, profil.eventIds, xParam, yParam, $('#clusterBasis').value || null,
    `Cluster ${profil.cluster + 1}`);
  if (!gate) {
    status('Cluster konnte nicht in ein Gate überführt werden (zu wenige Punkte).', 'fehler');
    return;
  }
  gate.color = CLUSTER_FARBEN[profil.cluster % CLUSTER_FARBEN.length];
  addGate(gate);
  status(`Cluster ${profil.cluster + 1} als Gate "${gate.name}" übernommen — bitte Form im Plot prüfen.`, 'ok');
  nachGateAenderung();
}

/* ================================================================== */
/* Befund                                                             */
/* ================================================================== */

function befundErzeugen() {
  const probe = activeSample();
  if (!probe) return null;
  const auswertung = ui.auswertung || auswertungAktualisieren();
  const bewertung = auswertung?.bewertung || { metriken: [], scores: [], ddx: [], auffaelligkeiten: [], empfehlungen: [] };
  return erzeugeBefund({
    sample: probe,
    panel: auswertung?.panel || null,
    bewertung,
    qc: probe.qc || runQC(probe),
    stepGates: ui.panelErgebnis?.stepGates,
    patient: state.patient,
    report: state.report,
    fehlend: ui.panelErgebnis?.fehlend,
    warnungen: ui.panelErgebnis?.warnungen,
  });
}

function zeichneBefund() {
  const ziel = $('#inhaltBefund');
  const probe = activeSample();
  ziel.textContent = '';
  if (!probe) {
    ziel.append(h('div', { class: 'leer' }, 'Keine Auswertung vorhanden'));
    return;
  }
  const befund = befundErzeugen();

  /* --- Freitext und Signatur --- */
  const bearbeiten = h('div', { class: 'karte nichtdrucken' },
    h('h3', {}, 'Beurteilung und Freigabe'),
    h('label', { class: 'feld' },
      h('span', {}, 'Beurteilung (leer = automatischer Vorschlag wird übernommen)'),
      h('textarea', {
        rows: 6, placeholder: befund.beurteilungVorschlag,
        oninput: (e) => { setReport({ beurteilung: e.target.value }); befundVorschauAktualisieren(); },
      }, state.report.beurteilung),
    ),
    h('label', { class: 'feld' },
      h('span', {}, 'Empfehlung'),
      h('textarea', {
        rows: 3, placeholder: befund.empfehlungen.join(' '),
        oninput: (e) => { setReport({ empfehlung: e.target.value }); befundVorschauAktualisieren(); },
      }, state.report.empfehlung),
    ),
    h('div', { class: 'reihe' },
      h('label', { class: 'feld' }, h('span', {}, 'Befunder'),
        h('input', { type: 'text', value: state.report.befunder, oninput: (e) => { setReport({ befunder: e.target.value }); zeichneBefund(); } })),
      h('label', { class: 'feld' }, h('span', {}, 'Zweitbefunder (Vier-Augen-Prinzip)'),
        h('input', { type: 'text', value: state.report.zweitbefunder, oninput: (e) => { setReport({ zweitbefunder: e.target.value }); befundVorschauAktualisieren(); } })),
    ),
  );

  if (!befund.freigabeMoeglich) {
    bearbeiten.append(h('div', { class: 'hinweisbox' },
      h('strong', {}, 'Freigabe noch nicht möglich'),
      h('ul', { style: 'margin:6px 0 0 18px' }, ...befund.freigabeHindernisse.map((x) => h('li', {}, x))),
    ));
  }

  bearbeiten.append(h('div', { class: 'reihe', style: 'margin-top:10px' },
    h('button', {
      class: 'primary', disabled: !befund.freigabeMoeglich,
      onclick: () => {
        setReport({ freigabe: new Date().toISOString(), revision: state.report.revision });
        state.report.historie.push({ zeit: state.report.freigabe, befunder: state.report.befunder, revision: state.report.revision });
        status('Befund freigegeben', 'ok');
        zeichneBefund();
      },
    }, state.report.freigabe ? 'Erneut freigeben' : 'Befund freigeben'),
    h('button', { onclick: () => { setReport({ revision: state.report.revision + 1, freigabe: null }); zeichneBefund(); } },
      'Neue Revision'),
    h('span', { style: 'flex:1' }),
    h('button', { onclick: () => download(befundAlsText(befundErzeugen()), `${probe.name}_befund.txt`) }, 'Text'),
    h('button', { onclick: () => download(befundAlsCSV(befundErzeugen()), `${probe.name}_kennzahlen.csv`, 'text/csv;charset=utf-8') }, 'CSV'),
    h('button', { onclick: () => download(JSON.stringify(befundErzeugen(), null, 2), `${probe.name}_befund.json`, 'application/json') }, 'JSON'),
    h('button', {
      title: 'HL7-FHIR-Bundle für die Übernahme in ein Laborinformationssystem',
      onclick: () => download(JSON.stringify(alsFHIR(befundErzeugen()), null, 2), `${probe.name}_fhir.json`, 'application/fhir+json'),
    }, 'FHIR'),
    h('button', { onclick: () => window.print() }, 'Drucken / PDF'),
  ));
  ziel.append(bearbeiten);

  if (befund.ddx.some((d) => d.dringend && d.passung > 0.75)) {
    ziel.append(h('div', { class: 'hinweisbox kritisch' },
      h('strong', {}, 'Dringlicher Hinweis'),
      h('p', {}, befund.ddx.find((d) => d.dringend).zusatz),
    ));
  }

  ziel.append(h('pre', { class: 'befund', id: 'befundVorschau' }, befundAlsText(befund)));
}

function befundVorschauAktualisieren() {
  const el = $('#befundVorschau');
  if (el) el.textContent = befundAlsText(befundErzeugen());
}

/* ================================================================== */
/* Inspektor: Gate- und Kanaleigenschaften                            */
/* ================================================================== */

function zeichneInspektor() {
  const ziel = $('#inspektor');
  const probe = activeSample();
  ziel.textContent = '';
  if (!probe) {
    ziel.append(h('div', { class: 'leer' }, 'Nichts ausgewählt'));
    return;
  }

  const gate = state.activeGateId ? gateById(state.activeGateId) : null;
  if (gate) {
    const st = gateStats(probe, gate.id);
    ziel.append(
      h('label', { class: 'feld' }, h('span', {}, 'Name'),
        h('input', { type: 'text', value: gate.name, oninput: (e) => { updateGate(gate.id, { name: e.target.value }); zeichneGateBaum(); zeichnePlots(); } })),
      h('div', { style: 'font-size:11px;color:var(--fg-muted);margin-bottom:8px' },
        `${gatePath(gate.id).join(' > ')}`, h('br'),
        `${st.count.toLocaleString('de-DE')} Ereignisse · ${zahl(st.pctParent, 2)} % der Elternpopulation · ${zahl(st.pctTotal, 2)} % gesamt`,
        gate.auto ? h('div', {}, `Verfahren: ${gate.auto.method}`) : null,
      ),
      h('label', { class: 'feld' }, h('span', {}, 'Farbe'),
        h('input', { type: 'color', value: gate.color, oninput: (e) => { updateGate(gate.id, { color: e.target.value }); zeichneGateBaum(); zeichnePlots(); } })),
    );
    if (gate.auto?.vorlaeufig) {
      ziel.append(h('div', { class: 'hinweisbox' }, 'Startvorschlag aus der Panel-Vorlage. Vor der Freigabe visuell prüfen und anpassen.'));
    }
    ziel.append(h('button', { onclick: () => { removeGate(gate.id); nachGateAenderung(); } }, 'Gate löschen'));
    ziel.append(h('hr', { style: 'border:none;border-top:1px solid var(--border);margin:12px 0' }));
  }

  /* --- Skalierung des Kanals der aktiven Kachel --- */
  const tile = state.layout.find((t) => t.id === ui.aktiveKachel) || state.layout[0];
  if (!tile) return;
  for (const [achse, paramIndex] of [['X', tile.xParam], ['Y', tile.yParam]]) {
    if (paramIndex == null || (achse === 'Y' && tile.type === 'histogram')) continue;
    const tr = transformFor(probe, paramIndex);
    const spec = probe.transforms[paramIndex];
    const block = h('div', { style: 'margin-bottom:12px' },
      h('div', { style: 'font-size:11px;color:var(--fg-muted)' }, `${achse}-Achse: ${kanalNameLang(probe, paramIndex)}`),
      h('select', {
        style: 'width:100%;margin:4px 0',
        onchange: (e) => {
          const art = e.target.value;
          const werte = channelValues(probe, paramIndex);
          let max = 0;
          for (let i = 0; i < werte.length; i++) if (werte[i] > max) max = werte[i];
          const neu = art === 'linear' ? { kind: 'linear', min: 0, max: max || 1 }
            : art === 'log' ? { kind: 'log', min: 1, max: max || 1e4 }
              : art === 'asinh' ? { kind: 'asinh', cofactor: 150, min: -1000, max: max || 1e5 }
                : { kind: 'logicle', T: probe.params[paramIndex].range || 262144, W: 0.5, M: 4.5, A: 0 };
          setTransform(probe, paramIndex, neu);
          zeichnePlots();
          zeichneInspektor();
        },
      },
        ...['logicle', 'linear', 'log', 'asinh'].map((k) =>
          h('option', { value: k, selected: spec?.kind === k }, { logicle: 'Logicle', linear: 'linear', log: 'log10', asinh: 'arcsinh' }[k])),
      ),
      h('div', { style: 'font-size:10px;color:var(--fg-muted)' }, tr.describe()),
    );
    if (spec?.kind === 'logicle') {
      block.append(h('label', { class: 'feld' }, h('span', {}, `W (Linearisierungsbreite): ${spec.W.toFixed(2)}`),
        h('input', {
          type: 'range', min: '0.05', max: '2', step: '0.05', value: spec.W,
          oninput: (e) => { setTransform(probe, paramIndex, { ...spec, W: +e.target.value }); zeichnePlots(); zeichneInspektor(); },
        })));
    }
    if (spec?.kind === 'asinh') {
      block.append(h('label', { class: 'feld' }, h('span', {}, `Kofaktor: ${spec.cofactor}`),
        h('input', {
          type: 'range', min: '5', max: '2000', step: '5', value: spec.cofactor,
          oninput: (e) => { setTransform(probe, paramIndex, { ...spec, cofactor: +e.target.value }); zeichnePlots(); zeichneInspektor(); },
        })));
    }
    ziel.append(block);
  }

  /* --- Markerzuordnung --- */
  const zuordnung = h('div', {}, h('div', { style: 'font-size:11px;color:var(--fg-muted);margin-bottom:4px' }, 'Markerzuordnung'));
  for (const p of probe.params) {
    if (p.isScatter || p.isTime) continue;
    zuordnung.append(h('div', { class: 'reihe', style: 'margin-bottom:3px' },
      h('span', { style: 'font-size:11px;flex:1' }, p.name),
      h('input', {
        type: 'text', style: 'flex:1;font-size:11px;padding:2px 5px',
        value: state.markerMap[p.name] || p.stain || '',
        onchange: (e) => {
          const kanon = canonicalMarker(e.target.value) || e.target.value;
          state.markerMap[p.name] = kanon;
          e.target.value = kanon;
          status(`${p.name} → ${kanon}${markerInfo(kanon) ? ': ' + markerInfo(kanon).text : ' (unbekannter Marker)'}`);
        },
      }),
    ));
  }
  ziel.append(zuordnung);
}

/* ================================================================== */
/* Kompensation                                                       */
/* ================================================================== */

function zeichneKompensation() {
  const ziel = $('#kompensationsbereich');
  const probe = activeSample();
  ziel.textContent = '';
  if (!probe) {
    ziel.append(h('div', { class: 'leer' }, 'Keine Probe geladen'));
    return;
  }
  const st = compensationStatus(probe);

  ziel.append(h('label', { class: 'feld' },
    h('input', {
      type: 'checkbox', checked: probe.comp.enabled,
      onchange: (e) => {
        probe.comp.enabled = e.target.checked;
        invalidateSample(probe);
        invalidate();
        bump('compensation');
        allesZeichnen();
      },
    }),
    ' Kompensation anwenden',
  ));

  ziel.append(h('div', { style: 'font-size:11px;color:var(--fg-muted);margin-bottom:8px' },
    st.applied ? `Angewandt auf ${probe.comp.channels.length} Kanäle (Quelle: ${probe.comp.source}).`
      : st.warning || 'Keine Matrix vorhanden.'));

  if (probe.comp.matrix) {
    const details = h('details', {}, h('summary', { style: 'cursor:pointer;font-size:11px' }, 'Matrix anzeigen und feinjustieren'));
    const tab = h('table', { class: 'matrix' });
    const kopf = h('tr', {}, h('th', {}, ''));
    for (const c of probe.comp.channels) kopf.append(h('th', {}, c.replace(/-A$/, '')));
    tab.append(h('thead', {}, kopf));
    const koerper = h('tbody');
    probe.comp.matrix.forEach((zeile, i) => {
      const tr = h('tr', {}, h('th', {}, probe.comp.channels[i].replace(/-A$/, '')));
      zeile.forEach((v, j) => {
        tr.append(h('td', {}, i === j ? h('span', {}, '1,00') : h('input', {
          type: 'number', step: '0.001', value: (v * 100).toFixed(1),
          title: `Anteil ${probe.comp.channels[i]} in ${probe.comp.channels[j]} (%)`,
          onchange: (e) => {
            probe.comp.tweak = probe.comp.tweak || {};
            probe.comp.tweak[`${i}:${j}`] = +e.target.value - v * 100;
            invalidateSample(probe);
            invalidate();
            bump('compensation');
            allesZeichnen();
          },
        })));
      });
      koerper.append(tr);
    });
    tab.append(koerper);
    details.append(tab);
    details.append(h('div', { class: 'reihe', style: 'margin-top:6px' },
      h('button', { onclick: () => download(compensationToCSV(probe.comp), `${probe.name}_kompensation.csv`, 'text/csv') }, 'Export'),
      h('button', { onclick: () => { probe.comp.tweak = null; invalidateSample(probe); invalidate(); bump('compensation'); allesZeichnen(); } }, 'Zurücksetzen'),
    ));
    ziel.append(details);
  }

  ziel.append(h('label', { class: 'btn', style: 'display:block;text-align:center;margin-top:8px' },
    'Matrix aus CSV laden',
    h('input', {
      type: 'file', accept: '.csv,.txt',
      onchange: async (e) => {
        const datei = e.target.files[0];
        if (!datei) return;
        try {
          const { channels, matrix } = parseCompensationCSV(await datei.text());
          probe.comp = { channels, matrix, source: 'CSV-Import', enabled: true, tweak: null };
          invalidateSample(probe);
          invalidate();
          bump('compensation');
          status(`Kompensationsmatrix mit ${channels.length} Kanälen geladen`, 'ok');
          allesZeichnen();
        } catch (err) {
          status(`Kompensationsmatrix: ${err.message}`, 'fehler');
        }
      },
    }),
  ));
}

/* ================================================================== */
/* Patientendaten und Kalibrierung                                    */
/* ================================================================== */

function zeichnePatientenformular() {
  const ziel = $('#patientenformular');
  ziel.textContent = '';
  const p = state.patient;

  const feld = (schluessel, beschriftung, typ = 'text') =>
    h('label', { class: 'feld' }, h('span', {}, beschriftung),
      h('input', {
        type: typ, value: p[schluessel] ?? '',
        oninput: (e) => {
          setPatient({ [schluessel]: typ === 'number' ? (e.target.value === '' ? null : +e.target.value) : e.target.value });
          if (schluessel === 'alterJahre' || schluessel === 'geburtsjahr') { auswertungAktualisieren(); zeichneStatistik(); }
          befundVorschauAktualisieren();
        },
      }));

  ziel.append(
    feld('pseudonym', 'Pseudonym / Fallnummer'),
    h('div', { class: 'reihe' }, feld('alterJahre', 'Alter (Jahre)', 'number'),
      h('label', { class: 'feld' }, h('span', {}, 'Geschlecht'),
        h('select', { onchange: (e) => { setPatient({ geschlecht: e.target.value }); befundVorschauAktualisieren(); } },
          ...['', 'weiblich', 'männlich', 'divers'].map((g) => h('option', { value: g, selected: p.geschlecht === g }, g || '–'))))),
    feld('material', 'Material'),
    feld('auftragsnummer', 'Auftragsnummer'),
    feld('einsender', 'Einsender'),
    h('label', { class: 'feld' }, h('span', {}, 'Fragestellung'),
      h('textarea', { rows: 2, oninput: (e) => { setPatient({ fragestellung: e.target.value }); befundVorschauAktualisieren(); } }, p.fragestellung)),
  );

  /* --- Kalibrierung fuer Absolutzahlen --- */
  const probe = activeSample();
  if (probe) {
    const kal = probe.kalibrierung || { modus: null };
    const block = h('details', { open: !!kal.modus },
      h('summary', { style: 'cursor:pointer;font-size:11px;color:var(--fg-muted);margin:8px 0 6px' }, 'Absolutzahlen kalibrieren'));

    const modusWahl = h('select', {
      style: 'width:100%',
      onchange: (e) => {
        probe.kalibrierung = { modus: e.target.value || null };
        auswertungAktualisieren();
        zeichnePatientenformular();
        zeichneStatistik();
        befundVorschauAktualisieren();
      },
    },
      h('option', { value: '', selected: !kal.modus }, 'keine'),
      h('option', { value: 'beads', selected: kal.modus === 'beads' }, 'Zählbeads (Einplattform)'),
      h('option', { value: 'blutbild', selected: kal.modus === 'blutbild' }, 'Blutbild (Zweiplattform)'),
    );
    block.append(modusWahl);

    const kalFeld = (schluessel, beschriftung) =>
      h('label', { class: 'feld' }, h('span', {}, beschriftung),
        h('input', {
          type: 'number', value: kal[schluessel] ?? '',
          oninput: (e) => {
            probe.kalibrierung[schluessel] = e.target.value === '' ? null : +e.target.value;
            auswertungAktualisieren();
            zeichneStatistik();
            befundVorschauAktualisieren();
          },
        }));

    if (kal.modus === 'beads') {
      block.append(kalFeld('beadEreignisse', 'gezählte Beads'), kalFeld('beadsProTest', 'Beads laut Zertifikat'), kalFeld('probenvolumen', 'Probenvolumen (µl)'));
    } else if (kal.modus === 'blutbild') {
      const schritte = ui.panelErgebnis?.stepGates || {};
      block.append(
        h('label', { class: 'feld' }, h('span', {}, 'Bezugspopulation'),
          h('select', {
            onchange: (e) => { probe.kalibrierung.refStep = e.target.value; auswertungAktualisieren(); zeichneStatistik(); befundVorschauAktualisieren(); },
          }, ...Object.keys(schritte).map((s) => h('option', { value: s, selected: kal.refStep === s }, gateById(schritte[s])?.name || s)))),
        kalFeld('refAbsolut', 'Absolutwert der Bezugspopulation (/µl)'),
      );
    }
    ziel.append(block);
  }
}

/* ================================================================== */
/* Referenzbereiche                                                   */
/* ================================================================== */

function zeichneReferenzbereich() {
  const ziel = $('#referenzbereich');
  ziel.textContent = '';
  ziel.append(
    h('div', { style: 'font-size:11px;color:var(--fg-muted)' }, ui.referenzQuelle.bezeichnung),
    h('div', { class: 'hinweisbox', style: 'font-size:11px' }, ui.referenzQuelle.hinweis || REFERENZ_QUELLE.hinweis),
    h('div', { class: 'reihe', style: 'margin-top:8px' },
      h('button', { onclick: () => download(exportReferenzen(ui.referenzKatalog, ui.referenzQuelle), 'referenzbereiche.json', 'application/json') }, 'Export'),
      h('label', { class: 'btn' }, 'Import',
        h('input', {
          type: 'file', accept: '.json',
          onchange: async (e) => {
            const datei = e.target.files[0];
            if (!datei) return;
            try {
              const { katalog, quelle, uebernommen } = importReferenzen(await datei.text());
              ui.referenzKatalog = katalog;
              ui.referenzQuelle = quelle;
              auswertungAktualisieren();
              status(`${uebernommen} Referenzbereiche übernommen (${quelle.bezeichnung})`, 'ok');
              zeichneReferenzbereich();
              zeichneStatistik();
              befundVorschauAktualisieren();
            } catch (err) {
              status(`Referenzbereiche: ${err.message}`, 'fehler');
            }
          },
        })),
    ),
  );
}

/* ================================================================== */
/* Panelinformationen                                                 */
/* ================================================================== */

function zeichnePanelInfo() {
  const ziel = $('#panelInfo');
  ziel.textContent = '';
  const panel = panelById(state.panelId);
  if (!panel) {
    ziel.append(h('div', { class: 'leer' }, 'Kein Panel gewählt'));
    return;
  }
  const probe = activeSample();
  const vorhanden = probe ? Object.values(state.markerMap) : [];
  const fit = scorePanelFit(panel, vorhanden);

  ziel.append(
    h('div', { style: 'font-weight:600;margin-bottom:4px' }, panel.name),
    h('div', { style: 'font-size:11px;color:var(--fg-muted);margin-bottom:8px' }, panel.indikation),
    h('div', { style: 'font-size:11px' }, `Material: ${panel.material}`),
    h('div', { style: 'font-size:11px;margin-top:6px' }, `Pflichtmarker: ${fit.treffer}/${fit.pflicht}`),
    fit.fehlend.length ? h('div', { style: 'font-size:11px;color:var(--warn)' }, `Fehlend: ${fit.fehlend.join(', ')}`) : null,
  );

  if (ui.panelErgebnis?.warnungen?.length) {
    ziel.append(h('div', { class: 'hinweisbox', style: 'font-size:11px' },
      ...ui.panelErgebnis.warnungen.map((w) => h('div', {}, w))));
  }
  if (panel.hinweise?.length) {
    const d = h('details', {}, h('summary', { style: 'cursor:pointer;font-size:11px;margin-top:8px' }, 'Fachliche Hinweise'));
    for (const hw of panel.hinweise) d.append(h('p', { style: 'font-size:11px;color:var(--fg-muted)' }, hw));
    ziel.append(d);
  }
}

/* ================================================================== */
/* Sitzung sichern und laden                                          */
/* ================================================================== */

function sitzungSichern() {
  const probe = activeSample();
  const daten = {
    format: 'flowcyto-sitzung',
    version: 1,
    erstellt: new Date().toISOString(),
    // Ereignisdaten werden bewusst NICHT gespeichert: die Sitzungsdatei bleibt
    // klein und enthaelt keine Messdaten, die Datenschutzauflagen unterliegen.
    proben: state.samples.map((s) => ({
      name: s.name, fileName: s.fileName, nEvents: s.nEvents,
      transforms: s.transforms, comp: { source: s.comp.source, enabled: s.comp.enabled, tweak: s.comp.tweak },
      kalibrierung: s.kalibrierung || null,
    })),
    gates: state.gates,
    layout: state.layout,
    panelId: state.panelId,
    markerMap: state.markerMap,
    patient: state.patient,
    report: state.report,
    referenzQuelle: ui.referenzQuelle,
  };
  download(JSON.stringify(daten, null, 2), `${probe ? probe.name : 'sitzung'}_flowcyto.json`, 'application/json');
  status('Sitzung gesichert (ohne Messdaten — FCS-Dateien separat aufbewahren)', 'ok');
}

async function sitzungLaden(datei) {
  try {
    const daten = JSON.parse(await datei.text());
    if (daten.format !== 'flowcyto-sitzung') throw new Error('Keine FlowCyto-Sitzungsdatei.');
    if (!state.samples.length) throw new Error('Bitte zuerst die zugehörige FCS-Datei öffnen.');

    state.gates = daten.gates || [];
    state.layout = daten.layout || [];
    state.panelId = daten.panelId || null;
    state.markerMap = daten.markerMap || {};
    Object.assign(state.patient, daten.patient || {});
    Object.assign(state.report, daten.report || {});

    const probe = activeSample();
    const gesichert = daten.proben?.[0];
    if (gesichert && probe) {
      if (gesichert.nEvents !== probe.nEvents) {
        status(`Achtung: die geladene Datei hat ${probe.nEvents.toLocaleString('de-DE')} Ereignisse, die Sitzung wurde mit ${gesichert.nEvents.toLocaleString('de-DE')} gesichert.`, 'fehler');
      }
      probe.transforms = gesichert.transforms || {};
      probe.comp.enabled = gesichert.comp?.enabled ?? probe.comp.enabled;
      probe.comp.tweak = gesichert.comp?.tweak || null;
      probe.kalibrierung = gesichert.kalibrierung || null;
      invalidateSample(probe);
    }

    ui.views.clear();
    invalidate();
    bump('gates', 'transforms', 'compensation', 'panel', 'patient');

    // Panel-Schrittzuordnung aus den gespeicherten Gates rekonstruieren
    if (state.panelId) {
      const stepGates = {};
      for (const g of state.gates) if (g.panelStep) stepGates[g.panelStep] = g.id;
      ui.panelErgebnis = { stepGates, fehlend: [], warnungen: [] };
      auswertungAktualisieren();
    }
    status('Sitzung geladen', 'ok');
    allesZeichnen();
  } catch (err) {
    status(`Sitzung laden: ${err.message}`, 'fehler');
  }
}

/* ================================================================== */
/* Gesamtaktualisierung und Initialisierung                           */
/* ================================================================== */

function allesZeichnen() {
  zeichneProbenliste();
  zeichneGateBaum();
  zeichnePanelInfo();
  zeichnePlots();
  zeichneInspektor();
  zeichneKompensation();
  zeichnePatientenformular();
  zeichneReferenzbereich();
  clusterBasisFuellen();
  zeichneStatistik();
  zeichneQC();
  zeichneCluster();
  zeichneBefund();
}

function reiterUmschalten(name) {
  state.ui.tab = name;
  $$('#reiterleiste button').forEach((b) => b.classList.toggle('aktiv', b.dataset.reiter === name));
  $$('.reiterinhalt').forEach((el) => el.classList.remove('aktiv'));
  $(`#inhalt${name}`).classList.add('aktiv');
  if (name === 'Plots') requestAnimationFrame(zeichnePlots);
  if (name === 'Cluster') requestAnimationFrame(zeichneCluster);
}

function init() {
  /* --- Panelauswahl fuellen --- */
  const auswahl = $('#panelAuswahl');
  for (const [kategorie, panels] of panelKategorien()) {
    const gruppe = h('optgroup', { label: kategorie });
    for (const p of panels) gruppe.append(h('option', { value: p.id }, p.name));
    auswahl.append(gruppe);
  }
  auswahl.addEventListener('change', () => {
    $('#btnPanelAnwenden').disabled = !auswahl.value || !state.samples.length;
    state.panelId = auswahl.value || null;
    zeichnePanelInfo();
  });

  /* --- Kopfzeile --- */
  $('#dateiEingabe').addEventListener('change', (e) => { dateienLaden([...e.target.files]); e.target.value = ''; });
  $('#sitzungEingabe').addEventListener('change', (e) => { if (e.target.files[0]) sitzungLaden(e.target.files[0]); e.target.value = ''; });
  $('#btnPanelAnwenden').addEventListener('click', panelAnwenden);
  $('#btnSitzungSpeichern').addEventListener('click', sitzungSichern);
  $('#btnDesign').addEventListener('click', () => {
    // Ohne gesetztes Attribut gilt die Systemeinstellung -- sonst waere der
    // erste Klick bei dunklem System wirkungslos.
    const neu = aktuellesDesign() === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = neu;
    state.ui.theme = neu;
    merkeDesign(neu);
    zeichnePlots();
    zeichneCluster();
  });

  /* --- Reiter --- */
  $$('#reiterleiste button').forEach((b) => b.addEventListener('click', () => reiterUmschalten(b.dataset.reiter)));

  /* --- Werkzeugleiste --- */
  $$('.werkzeuge [data-werkzeug]').forEach((b) => b.addEventListener('click', () => {
    ui.werkzeug = b.dataset.werkzeug;
    ui.polygonPunkte = [];
    $$('.werkzeuge [data-werkzeug]').forEach((x) => x.classList.toggle('aktiv', x === b));
    zeichnePlots();
  }));
  $('#plottyp').addEventListener('change', (e) => {
    state.ui.plotType = e.target.value;
    for (const t of state.layout) t.type = e.target.value;
    zeichnePlots();
  });
  $('#btnPlotHinzu').addEventListener('click', () => {
    const probe = activeSample();
    if (!probe) return;
    const fl = fluorParams(probe);
    state.layout.push({
      id: uid('plot'), type: state.ui.plotType, gateId: state.activeGateId,
      xParam: fl[0] ?? 0, yParam: fl[1] ?? 1,
    });
    zeichnePlots();
  });
  $('#chkBackgate').addEventListener('change', (e) => { state.ui.showBackgate = e.target.checked; zeichnePlots(); });
  $('#ereignislimit').addEventListener('change', (e) => { state.ui.eventLimit = +e.target.value; zeichnePlots(); });

  /* --- Gate-Werkzeuge --- */
  $('#btnVorgating').addEventListener('click', () => {
    const probe = activeSample();
    if (!probe) return;
    const neu = standardPreGating(probe);
    status(neu.length ? `${neu.length} Gates gesetzt: ${neu.map((g) => g.name).join(', ')}` : 'Vorgating nicht möglich (Streulichtkanäle fehlen).');
    nachGateAenderung();
  });
  $('#btnGateLoeschen').addEventListener('click', () => {
    if (!state.activeGateId) return;
    removeGate(state.activeGateId);
    nachGateAenderung();
  });

  /* --- Clusteranalyse --- */
  $('#btnClusterStart').addEventListener('click', clusterBerechnen);

  /* --- Tastatur --- */
  window.addEventListener('keydown', (e) => {
    if (e.target.matches('input, textarea, select')) return;
    if (e.key === 'Escape') { ui.polygonPunkte = []; ui.zeichnen = null; zeichnePlots(); }
    if (e.key === 'Enter' && ui.polygonPunkte.length >= 3) {
      const tile = state.layout.find((t) => t.id === ui.aktiveKachel);
      if (tile) polygonAbschliessen(tile);
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && state.activeGateId) {
      removeGate(state.activeGateId);
      nachGateAenderung();
    }
    const werkzeuge = { v: 'zeiger', r: 'rect', p: 'polygon', e: 'ellipse', i: 'interval', q: 'quadrant' };
    if (werkzeuge[e.key]) $(`.werkzeuge [data-werkzeug="${werkzeuge[e.key]}"]`)?.click();
  });

  window.addEventListener('resize', () => {
    clearTimeout(window._resizeTimer);
    window._resizeTimer = setTimeout(() => { zeichnePlots(); zeichneCluster(); }, 120);
  });

  // Wechselt die Systemeinstellung, muessen die Canvas-Ansichten neu gezeichnet
  // werden -- sie lesen ihre Farben beim Zeichnen aus den CSS-Token.
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
    if (!document.documentElement.dataset.theme) {
      zeichnePlots();
      zeichneCluster();
    }
  });

  const gespeichertesDesign = leseDesign();
  if (gespeichertesDesign) document.documentElement.dataset.theme = gespeichertesDesign;

  on('gates:changed', () => { /* Ansichten werden gezielt aktualisiert */ });

  allesZeichnen();
  status('Bereit — FCS- oder CSV-Datei öffnen. Tastatur: V Zeiger, R Rechteck, P Polygon, E Ellipse, I Intervall, Q Quadranten.');
}

// Module werden verzoegert ausgefuehrt: je nach Zeitpunkt ist das DOM schon
// fertig. Der Waechter verhindert, dass init() zweimal laeuft.
let initialisiert = false;
function initEinmal() {
  if (initialisiert) return;
  initialisiert = true;
  init();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initEinmal);
else initEinmal();
