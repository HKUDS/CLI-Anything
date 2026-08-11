#!/usr/bin/env bun
/**
 * Kommandozeilenschnittstelle.
 *
 * Nutzt exakt dieselben Module wie die Oberflaeche -- Parser, Kompensation,
 * Transformation, Gating, Statistik, Regelwerk und Befund. Es gibt keine
 * zweite Rechenstrecke: die CLI liefert per Definition dieselben Zahlen wie
 * die grafische Auswertung.
 *
 * Zweck: Stapelverarbeitung, Einbindung in Laborskripte und Nutzung durch
 * Agenten ohne Browser.
 */

import { readFile, writeFile } from 'node:fs/promises';
import { basename } from 'node:path';

import { state, resetWorkspace, addSample, activeSample } from './src/core/store.js';
import { parseAny } from './src/core/fcs.js';
import { invalidateSample, compensationStatus, fluorParams } from './src/core/data.js';
import { orderedGates, gateStats } from './src/core/gating.js';
import { runQC } from './src/core/qc.js';
import { applyPanel, evaluateMetrics } from './src/core/strategy.js';
import { autoMapMarkers, markerInfo, MARKERS } from './src/knowledge/markers.js';
import { PANELS, panelById, scorePanelFit } from './src/knowledge/panels.js';
import { bewertePanel, formatWert } from './src/knowledge/rules.js';
import { REFERENZBEREICHE, importReferenzen } from './src/knowledge/reference.js';
import { erzeugeBefund, befundAlsText, befundAlsCSV } from './src/report/befund.js';
import { alsFHIR } from './src/report/fhir.js';

/* ------------------------------------------------------------------ */
/* Argumente                                                           */
/* ------------------------------------------------------------------ */

function parseArgs(argv) {
  const positional = [];
  const flags = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const [name, direkt] = a.slice(2).split('=');
      if (direkt !== undefined) flags[name] = direkt;
      else if (argv[i + 1] && !argv[i + 1].startsWith('--')) flags[name] = argv[++i];
      else flags[name] = true;
    } else {
      positional.push(a);
    }
  }
  return { positional, flags };
}

const HILFE = `
FlowCyto — Befundwerkzeug für durchflusszytometrische Daten

  bun cli.mjs <befehl> [argumente]

Befehle
  info <datei>              Metadaten, Kanäle, Markerzuordnung, Spillover
  qc <datei>                Qualitätskontrolle der Messung
  analyse <datei>           Vollständige Auswertung und Befund
  batch <datei...>          Mehrere Proben mit demselben Panel, Vergleichstabelle
  panels [--marker LISTE]   Panel-Vorlagen, optional nach Passung sortiert
  marker <name>             Marker im Lexikon nachschlagen

Optionen für analyse und batch
  --panel <id>              Panel-Vorlage (Vorgabe: beste Passung)
  --format text|json|csv|fhir      Ausgabeformat (Vorgabe: text)
  --ausgabe <datei>         In Datei schreiben statt auf die Standardausgabe
  --alter <jahre>           Alter für altersabhängige Referenzbereiche
  --geschlecht <w|m|d>
  --pseudonym <text>        Fallnummer oder Pseudonym
  --material <text>         Vorgabe: EDTA-Blut
  --fragestellung <text>
  --befunder <name>         ohne Eintrag bleibt die Freigabe gesperrt
  --referenzen <datei.json> laboreigene Referenzbereiche
  --beads <n,beads,volumen> Absolutzahlen über Zählbeads (Einplattform)
  --blutbild <schritt,wert> Absolutzahlen über das Blutbild (Zweiplattform)
  --ohne-kompensation       Spillover-Korrektur nicht anwenden

Beispiele
  bun cli.mjs info probe.fcs
  bun cli.mjs analyse probe.fcs --panel tbnk --alter 45 --befunder "Dr. Muster"
  bun cli.mjs analyse probe.fcs --format fhir --ausgabe befund.json
  bun cli.mjs batch lauf/*.fcs --panel pnh --format csv --ausgabe verlauf.csv
`;

/* ------------------------------------------------------------------ */
/* Laden                                                               */
/* ------------------------------------------------------------------ */

async function ladeProbe(pfad, flags) {
  const puffer = await readFile(pfad);
  const probe = parseAny(puffer.buffer.slice(puffer.byteOffset, puffer.byteOffset + puffer.byteLength), basename(pfad));

  if (flags['ohne-kompensation']) probe.comp.enabled = false;
  invalidateSample(probe);
  addSample(probe);
  state.activeSampleId = probe.id;
  Object.assign(state.markerMap, autoMapMarkers(probe));

  if (flags.beads) {
    const [beadEreignisse, beadsProTest, probenvolumen] = String(flags.beads).split(',').map(Number);
    probe.kalibrierung = { modus: 'beads', beadEreignisse, beadsProTest, probenvolumen };
  } else if (flags.blutbild) {
    const [refStep, refAbsolut] = String(flags.blutbild).split(',');
    probe.kalibrierung = { modus: 'blutbild', refStep, refAbsolut: Number(refAbsolut) };
  }
  return probe;
}

function patientAus(flags) {
  return {
    pseudonym: flags.pseudonym || '',
    alterJahre: flags.alter !== undefined ? Number(flags.alter) : null,
    geschlecht: flags.geschlecht || '',
    material: flags.material || 'EDTA-Blut',
    fragestellung: flags.fragestellung || '',
    auftragsnummer: flags.auftrag || '',
    einsender: flags.einsender || '',
    entnahme: '',
    eingang: '',
    klinik: '',
    vorbefunde: '',
  };
}

async function katalogAus(flags) {
  if (!flags.referenzen) return REFERENZBEREICHE;
  const { katalog, quelle, uebernommen } = importReferenzen(await readFile(flags.referenzen, 'utf8'));
  process.stderr.write(`${uebernommen} Referenzbereiche übernommen (${quelle.bezeichnung})\n`);
  return katalog;
}

/** Waehlt das Panel: ausdrueckliche Angabe oder beste Passung. */
function panelWaehlen(probe, flags) {
  if (flags.panel) {
    const p = panelById(flags.panel);
    if (!p) throw new Error(`Unbekanntes Panel "${flags.panel}". Verfügbare: ${PANELS.map((x) => x.id).join(', ')}`);
    return p;
  }
  const marker = Object.values(state.markerMap);
  const treffer = PANELS.map((p) => scorePanelFit(p, marker)).sort((a, b) => b.score - a.score);
  if (!treffer.length || treffer[0].score < 0.5) {
    throw new Error('Kein Panel passt ausreichend zu den vorhandenen Markern. Panel mit --panel angeben.');
  }
  process.stderr.write(`Panel automatisch gewählt: ${treffer[0].panel.name} (${treffer[0].treffer}/${treffer[0].pflicht} Pflichtmarker)\n`);
  return treffer[0].panel;
}

/* ------------------------------------------------------------------ */
/* Befehle                                                             */
/* ------------------------------------------------------------------ */

async function befehlInfo(pfad, flags) {
  const probe = await ladeProbe(pfad, flags);
  const komp = compensationStatus(probe);
  const zeilen = [];

  zeilen.push(`Datei          ${probe.fileName}`);
  zeilen.push(`Format         ${probe.meta.version}`);
  zeilen.push(`Gerät          ${probe.meta.cytometer}${probe.meta.cytometerSN ? ' / SN ' + probe.meta.cytometerSN : ''}`);
  zeilen.push(`Messdatum      ${probe.meta.date} ${probe.meta.btim}–${probe.meta.etim}`);
  zeilen.push(`Ereignisse     ${probe.nEvents.toLocaleString('de-DE')}`);
  zeilen.push(`Kanäle         ${probe.nParams}`);
  zeilen.push(`Kompensation   ${komp.applied ? `${probe.comp.channels.length} Kanäle (${probe.comp.source})` : komp.warning || 'keine'}`);
  zeilen.push('');
  zeilen.push('Kanal            Färbung          Marker     Bereich     Skalierung');
  zeilen.push('─'.repeat(74));
  for (const p of probe.params) {
    const marker = state.markerMap[p.name] || '';
    const art = p.isScatter ? 'linear (Streulicht)' : p.isTime ? 'linear (Zeit)' : 'Logicle';
    zeilen.push(
      `${p.name.padEnd(16)} ${(p.stain || '–').padEnd(16)} ${marker.padEnd(10)} ${String(p.range).padEnd(11)} ${art}`,
    );
  }
  if (probe.comp.matrix) {
    zeilen.push('');
    zeilen.push('Spillover-Matrix (%):');
    zeilen.push('               ' + probe.comp.channels.map((c) => c.slice(0, 8).padStart(9)).join(''));
    probe.comp.matrix.forEach((r, i) => {
      zeilen.push(probe.comp.channels[i].slice(0, 14).padEnd(15) + Array.from(r, (v) => (v * 100).toFixed(1).padStart(9)).join(''));
    });
  }
  return zeilen.join('\n');
}

async function befehlQC(pfad, flags) {
  const probe = await ladeProbe(pfad, flags);
  const qc = runQC(probe);
  if (flags.format === 'json') return JSON.stringify(qc, null, 2);

  const zeilen = [`Qualitätskontrolle — ${probe.name}`, ''];
  for (const c of qc.checks) {
    zeilen.push(`[${c.status.toUpperCase().padEnd(9)}] ${c.label.padEnd(32)} ${String(c.value).padStart(14)}`);
    zeilen.push(`             ${c.detail}`);
  }
  zeilen.push('');
  zeilen.push(`Gesamtbewertung: ${qc.overall}`);
  zeilen.push(qc.summary);
  return zeilen.join('\n');
}

async function befehlAnalyse(pfad, flags) {
  const probe = await ladeProbe(pfad, flags);
  const katalog = await katalogAus(flags);
  const panel = panelWaehlen(probe, flags);

  const ergebnis = applyPanel(probe, panel, { markerMap: state.markerMap });
  const { metriken, ctx } = evaluateMetrics(probe, panel, ergebnis.stepGates, state.markerMap);
  const patient = patientAus(flags);
  const bewertung = bewertePanel(probe, panel, ctx, metriken, patient, katalog);
  const qc = runQC(probe);

  const befund = erzeugeBefund({
    sample: probe, panel, bewertung, qc,
    stepGates: ergebnis.stepGates,
    patient,
    report: { befunder: flags.befunder || '', zweitbefunder: flags.zweitbefunder || '', revision: 1, freigabe: null },
    fehlend: ergebnis.fehlend,
    warnungen: ergebnis.warnungen,
  });

  if (ergebnis.fehlend.length) {
    process.stderr.write(`Hinweis: ${ergebnis.fehlend.length} Gating-Schritt(e) nicht möglich — ${ergebnis.fehlend.join('; ')}\n`);
  }

  switch (flags.format) {
    case 'json': return JSON.stringify(befund, null, 2);
    case 'csv': return befundAlsCSV(befund);
    case 'fhir': return JSON.stringify(alsFHIR(befund), null, 2);
    default: return befundAlsText(befund);
  }
}

async function befehlBatch(pfade, flags) {
  const katalog = await katalogAus(flags);
  const zeilen = [];
  const kopf = new Set();
  const berichte = [];

  for (const pfad of pfade) {
    resetWorkspace();
    try {
      const probe = await ladeProbe(pfad, flags);
      const panel = panelWaehlen(probe, flags);
      const ergebnis = applyPanel(probe, panel, { markerMap: state.markerMap });
      const { metriken, ctx } = evaluateMetrics(probe, panel, ergebnis.stepGates, state.markerMap);
      const patient = patientAus(flags);
      const bewertung = bewertePanel(probe, panel, ctx, metriken, patient, katalog);
      const qc = runQC(probe);

      const zeile = { Datei: basename(pfad), Ereignisse: probe.nEvents, 'Qualität': qc.overall, Panel: panel.id };
      for (const m of bewertung.metriken) {
        zeile[m.name] = Number.isFinite(m.wert) ? m.wert.toFixed(m.nachkomma ?? 1) : '';
        if (Number.isFinite(m.absolut)) zeile[`${m.name} (/µl)`] = m.absolut.toFixed(1);
        kopf.add(m.name);
        if (Number.isFinite(m.absolut)) kopf.add(`${m.name} (/µl)`);
      }
      for (const s of bewertung.scores) {
        zeile[s.name] = s.bewertung;
        kopf.add(s.name);
      }
      zeilen.push(zeile);
      berichte.push({ datei: basename(pfad), panel: panel.id, qc: qc.overall, bewertung });
      process.stderr.write(`✓ ${basename(pfad)} — ${probe.nEvents.toLocaleString('de-DE')} Ereignisse, Qualität: ${qc.overall}\n`);
    } catch (err) {
      process.stderr.write(`✗ ${basename(pfad)}: ${err.message}\n`);
      zeilen.push({ Datei: basename(pfad), Ereignisse: '', 'Qualität': 'Fehler', Panel: err.message });
    }
  }

  if (flags.format === 'json') return JSON.stringify(berichte, null, 2);

  const spalten = ['Datei', 'Ereignisse', 'Qualität', 'Panel', ...kopf];
  const csv = [spalten, ...zeilen.map((z) => spalten.map((s) => z[s] ?? ''))];
  return csv.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
}

function befehlPanels(flags) {
  const marker = flags.marker ? String(flags.marker).split(',').map((m) => m.trim()) : null;
  const liste = marker
    ? PANELS.map((p) => scorePanelFit(p, marker)).sort((a, b) => b.score - a.score)
    : PANELS.map((p) => ({ panel: p, score: null, fehlend: [], treffer: 0, pflicht: p.marker.length }));

  const zeilen = [];
  for (const t of liste) {
    const p = t.panel;
    zeilen.push(`${p.id.padEnd(18)} ${p.name}`);
    zeilen.push(`${''.padEnd(18)} ${p.kategorie} · ${p.indikation}`);
    zeilen.push(`${''.padEnd(18)} Marker: ${p.marker.join(', ')}`);
    if (p.optional?.length) zeilen.push(`${''.padEnd(18)} optional: ${p.optional.join(', ')}`);
    if (t.score !== null) {
      zeilen.push(`${''.padEnd(18)} Passung: ${(t.score * 100).toFixed(0)} % (${t.treffer}/${t.pflicht})${t.fehlend.length ? ', fehlend: ' + t.fehlend.join(', ') : ''}`);
    }
    zeilen.push('');
  }
  return zeilen.join('\n');
}

function befehlMarker(name) {
  const info = markerInfo(name);
  if (!info) {
    const treffer = Object.keys(MARKERS).filter((m) => m.toLowerCase().includes(String(name).toLowerCase()));
    return treffer.length
      ? `"${name}" nicht gefunden. Ähnlich: ${treffer.join(', ')}`
      : `"${name}" nicht im Lexikon (${Object.keys(MARKERS).length} Marker).`;
  }
  return [
    `Marker    ${info.name}`,
    `Linie     ${info.lineage}`,
    info.aliases?.length ? `Synonyme  ${info.aliases.join(', ')}` : null,
    '',
    info.text,
  ].filter(Boolean).join('\n');
}

/* ------------------------------------------------------------------ */
/* Einstieg                                                            */
/* ------------------------------------------------------------------ */

async function main() {
  const { positional, flags } = parseArgs(process.argv.slice(2));
  const befehl = positional[0];

  if (!befehl || flags.help || flags.h) {
    process.stdout.write(HILFE);
    return 0;
  }

  let ausgabe;
  switch (befehl) {
    case 'info':
      if (!positional[1]) throw new Error('Dateiname fehlt.');
      ausgabe = await befehlInfo(positional[1], flags);
      break;
    case 'qc':
      if (!positional[1]) throw new Error('Dateiname fehlt.');
      ausgabe = await befehlQC(positional[1], flags);
      break;
    case 'analyse':
      if (!positional[1]) throw new Error('Dateiname fehlt.');
      ausgabe = await befehlAnalyse(positional[1], flags);
      break;
    case 'batch':
      if (positional.length < 2) throw new Error('Mindestens eine Datei angeben.');
      ausgabe = await befehlBatch(positional.slice(1), flags);
      break;
    case 'panels':
      ausgabe = befehlPanels(flags);
      break;
    case 'marker':
      if (!positional[1]) throw new Error('Markername fehlt.');
      ausgabe = befehlMarker(positional[1]);
      break;
    default:
      throw new Error(`Unbekannter Befehl "${befehl}". Mit --help die Übersicht anzeigen.`);
  }

  if (flags.ausgabe) {
    await writeFile(flags.ausgabe, ausgabe, 'utf8');
    process.stderr.write(`Geschrieben: ${flags.ausgabe}\n`);
  } else {
    process.stdout.write(ausgabe + '\n');
  }
  return 0;
}

try {
  process.exit(await main());
} catch (err) {
  process.stderr.write(`Fehler: ${err.message}\n`);
  process.exit(1);
}
