/**
 * Darstellungsschicht.
 *
 * Zeichnet Punkt-, Dichte-, Kontur- und Histogrammdarstellungen sowie Gates
 * auf ein Canvas. Alle Werte stammen aus core/data.js und core/stats.js --
 * die Darstellung rechnet nichts eigenstaendig aus, sie bildet nur ab. Damit
 * zeigt der Plot zwangslaeufig dieselben Zahlen wie Tabelle und Befund.
 */

import { scaledValues, transformFor } from '../core/data.js';
import { gateIndices, gateStats, pointInPolygon, pointInEllipse } from '../core/gating.js';
import { densityGrid, pointDensity, histogram1D, smooth1D } from '../core/stats.js';
import { gateById, state } from '../core/store.js';

/* ------------------------------------------------------------------ */
/* Farbskalen                                                          */
/* ------------------------------------------------------------------ */

/** Wahrnehmungsgleichmaessige Dichtefarbskala (an Viridis angelehnt). */
const DICHTE_LUT = buildLUT([
  [68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142],
  [38, 130, 142], [31, 158, 137], [53, 183, 121], [109, 205, 89],
  [180, 222, 44], [253, 231, 37],
]);

/** Waermeskala fuer Heatmaps (divergierend, farbfehlsichtigkeitstauglich). */
const HEAT_LUT = buildLUT([
  [5, 48, 97], [33, 102, 172], [67, 147, 195], [146, 197, 222],
  [209, 229, 240], [247, 247, 247], [253, 219, 199], [244, 165, 130],
  [214, 96, 77], [178, 24, 43],
]);

function buildLUT(stops, n = 256) {
  const lut = new Uint8ClampedArray(n * 3);
  for (let i = 0; i < n; i++) {
    const t = (i / (n - 1)) * (stops.length - 1);
    const i0 = Math.floor(t);
    const i1 = Math.min(i0 + 1, stops.length - 1);
    const f = t - i0;
    for (let c = 0; c < 3; c++) {
      lut[i * 3 + c] = stops[i0][c] + (stops[i1][c] - stops[i0][c]) * f;
    }
  }
  return lut;
}

export const CLUSTER_FARBEN = [
  '#4cc9f0', '#f72585', '#4361ee', '#ffd166', '#06d6a0', '#b5179e',
  '#fb8500', '#8ecae6', '#e63946', '#2a9d8f', '#a685e2', '#f4a261',
  '#43aa8b', '#577590', '#ff70a6', '#c9ada7', '#9bf6ff', '#bdb2ff',
];

/* ------------------------------------------------------------------ */
/* Plotansicht                                                         */
/* ------------------------------------------------------------------ */

const RAND = { links: 62, rechts: 14, oben: 26, unten: 46 };

export class PlotView {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {object} spec {sample, gateId, type, xParam, yParam, ...}
   */
  constructor(canvas, spec) {
    this.canvas = canvas;
    this.spec = spec;
    this.layout = null;
  }

  /** Rechnet die Zeichenflaeche aus (beruecksichtigt Geraetepixelverhaeltnis). */
  messen() {
    const dpr = window.devicePixelRatio || 1;
    const b = this.canvas.getBoundingClientRect();
    const breite = Math.max(120, Math.round(b.width));
    const hoehe = Math.max(120, Math.round(b.height));
    if (this.canvas.width !== breite * dpr || this.canvas.height !== hoehe * dpr) {
      this.canvas.width = breite * dpr;
      this.canvas.height = hoehe * dpr;
    }
    this.layout = {
      dpr,
      breite,
      hoehe,
      x0: RAND.links,
      y0: hoehe - RAND.unten,
      x1: breite - RAND.rechts,
      y1: RAND.oben,
      plotBreite: breite - RAND.links - RAND.rechts,
      plotHoehe: hoehe - RAND.unten - RAND.oben,
    };
    return this.layout;
  }

  /** Displaykoordinate [0,1] -> Bildpunkt. */
  toPixel(sx, sy) {
    const l = this.layout;
    return [l.x0 + sx * l.plotBreite, l.y0 - sy * l.plotHoehe];
  }

  /** Bildpunkt -> Displaykoordinate [0,1]. */
  toScale(px, py) {
    const l = this.layout;
    return [(px - l.x0) / l.plotBreite, (l.y0 - py) / l.plotHoehe];
  }

  imPlot(px, py) {
    const l = this.layout;
    return px >= l.x0 && px <= l.x1 && py >= l.y1 && py <= l.y0;
  }

  /* ---------------------------------------------------------------- */

  render() {
    const l = this.messen();
    const ctx = this.canvas.getContext('2d');
    ctx.save();
    ctx.scale(l.dpr, l.dpr);
    ctx.clearRect(0, 0, l.breite, l.hoehe);

    const stil = leseStil();
    ctx.fillStyle = stil.hintergrund;
    ctx.fillRect(0, 0, l.breite, l.hoehe);

    const { sample } = this.spec;
    if (!sample) {
      this.zeichneHinweis(ctx, 'Keine Probe geladen');
      ctx.restore();
      return;
    }

    try {
      if (this.spec.type === 'histogram') this.zeichneHistogramm(ctx, stil);
      else if (this.spec.type === 'embedding') this.zeichneEinbettung(ctx, stil);
      else this.zeichneZweiKanal(ctx, stil);
    } catch (err) {
      this.zeichneHinweis(ctx, `Darstellung nicht möglich: ${err.message}`);
    }
    ctx.restore();
  }

  zeichneHinweis(ctx, text) {
    const l = this.layout;
    const stil = leseStil();
    ctx.fillStyle = stil.gedaempft;
    ctx.font = '13px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(text, l.breite / 2, l.hoehe / 2);
    ctx.textAlign = 'left';
  }

  /* ---------------------------------------------------------------- */
  /* Zweikanaldarstellung                                              */
  /* ---------------------------------------------------------------- */

  zeichneZweiKanal(ctx, stil) {
    const l = this.layout;
    const { sample, xParam, yParam, gateId, type } = this.spec;
    const xs = scaledValues(sample, xParam);
    const ys = scaledValues(sample, yParam);
    const idx = gateIndices(sample, gateId);

    this.zeichneRahmen(ctx, stil);
    this.zeichneAchsen(ctx, stil, transformFor(sample, xParam), transformFor(sample, yParam));

    if (!idx.length) {
      this.zeichneHinweis(ctx, 'Population enthält keine Ereignisse');
      this.zeichneBeschriftung(ctx, stil, 0);
      return;
    }

    // Hintergrund-Population (Backgating): zeigt, wo die Auswahl herkommt
    if (this.spec.backgateId && this.spec.backgateId !== gateId) {
      const hintergrund = gateIndices(sample, this.spec.backgateId);
      this.zeichnePunkte(ctx, xs, ys, hintergrund, () => stil.backgate, 1);
    }

    const maxPunkte = this.spec.eventLimit || state.ui.eventLimit;
    const schritt = idx.length > maxPunkte ? idx.length / maxPunkte : 1;

    if (type === 'density' || type === 'contour') {
      const dens = densityGrid(xs, ys, idx, 256, 1.6);
      if (type === 'contour') {
        this.zeichnePunkte(ctx, xs, ys, idx, () => stil.gedaempft, schritt, 0.35);
        this.zeichneKonturen(ctx, dens, stil);
      } else {
        const pd = pointDensity(xs, ys, idx, dens);
        let maxD = 0;
        for (let i = 0; i < pd.length; i++) if (pd[i] > maxD) maxD = pd[i];
        // Wurzelskalierung: seltene Ereignisse bleiben sichtbar
        const farbe = (i) => lutFarbe(DICHTE_LUT, Math.sqrt(pd[i] / (maxD || 1)));
        this.zeichnePunkte(ctx, xs, ys, idx, farbe, schritt);
      }
    } else {
      const farbe = () => stil.punkt;
      this.zeichnePunkte(ctx, xs, ys, idx, farbe, schritt);
    }

    // Cluster-Einfaerbung
    if (this.spec.clusterZuordnung) {
      this.zeichneCluster(ctx, xs, ys);
    }

    this.zeichneGates(ctx, stil);
    this.zeichneBeschriftung(ctx, stil, idx.length);
  }

  zeichnePunkte(ctx, xs, ys, idx, farbeFn, schritt, alpha = 1) {
    const l = this.layout;
    ctx.globalAlpha = alpha;
    const groesse = idx.length > 50000 ? 1 : idx.length > 10000 ? 1.3 : 2;
    let letzteFarbe = null;
    for (let i = 0; i < idx.length; i += schritt) {
      const e = idx[Math.floor(i)];
      const px = l.x0 + xs[e] * l.plotBreite;
      const py = l.y0 - ys[e] * l.plotHoehe;
      if (px < l.x0 || px > l.x1 || py < l.y1 || py > l.y0) continue;
      const f = farbeFn(Math.floor(i));
      if (f !== letzteFarbe) {
        ctx.fillStyle = f;
        letzteFarbe = f;
      }
      ctx.fillRect(px, py, groesse, groesse);
    }
    ctx.globalAlpha = 1;
  }

  zeichneCluster(ctx, xs, ys) {
    const l = this.layout;
    const { events, eventCluster } = this.spec.clusterZuordnung;
    const groesse = events.length > 20000 ? 1 : 1.6;
    for (let i = 0; i < events.length; i++) {
      const e = events[i];
      const px = l.x0 + xs[e] * l.plotBreite;
      const py = l.y0 - ys[e] * l.plotHoehe;
      if (px < l.x0 || px > l.x1 || py < l.y1 || py > l.y0) continue;
      ctx.fillStyle = CLUSTER_FARBEN[eventCluster[i] % CLUSTER_FARBEN.length];
      ctx.fillRect(px, py, groesse, groesse);
    }
  }

  /** Konturlinien per Marching Squares ueber dem Dichtegitter. */
  zeichneKonturen(ctx, dens, stil) {
    const { grid, nBins } = dens;
    let maxD = 0;
    for (let i = 0; i < grid.length; i++) if (grid[i] > maxD) maxD = grid[i];
    if (!maxD) return;

    const stufen = [0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 0.9];
    ctx.lineWidth = 1;
    for (let s = 0; s < stufen.length; s++) {
      const schwelle = stufen[s] * maxD;
      ctx.strokeStyle = lutFarbe(DICHTE_LUT, 0.15 + 0.85 * stufen[s]);
      ctx.beginPath();
      for (let y = 0; y < nBins - 1; y++) {
        for (let x = 0; x < nBins - 1; x++) {
          const a = grid[y * nBins + x];
          const b = grid[y * nBins + x + 1];
          const c = grid[(y + 1) * nBins + x + 1];
          const d = grid[(y + 1) * nBins + x];
          const code = (a > schwelle ? 8 : 0) | (b > schwelle ? 4 : 0) | (c > schwelle ? 2 : 0) | (d > schwelle ? 1 : 0);
          if (code === 0 || code === 15) continue;
          const sx = x / nBins;
          const sy = y / nBins;
          const w = 1 / nBins;
          const segmente = MARCHING[code];
          for (const [p1, p2] of segmente) {
            const [ax, ay] = kante(p1, sx, sy, w);
            const [bx, by] = kante(p2, sx, sy, w);
            const [px1, py1] = this.toPixel(ax, ay);
            const [px2, py2] = this.toPixel(bx, by);
            ctx.moveTo(px1, py1);
            ctx.lineTo(px2, py2);
          }
        }
      }
      ctx.stroke();
    }
  }

  /* ---------------------------------------------------------------- */
  /* Histogramm                                                        */
  /* ---------------------------------------------------------------- */

  zeichneHistogramm(ctx, stil) {
    const l = this.layout;
    const { sample, xParam } = this.spec;
    const tr = transformFor(sample, xParam);

    this.zeichneRahmen(ctx, stil);
    this.zeichneAchsen(ctx, stil, tr, null, true);

    const reihen = this.spec.reihen || [{ sample, gateId: this.spec.gateId, farbe: stil.punkt, name: '' }];
    let maxWert = 0;
    const berechnet = reihen.map((r) => {
      const scaled = scaledValues(r.sample, r.xParam ?? xParam);
      const idx = gateIndices(r.sample, r.gateId);
      const { bins, total } = histogram1D(scaled, idx, 256);
      const geglaettet = smooth1D(bins, 1.8);
      // Auf den Modalwert normieren: Populationen unterschiedlicher Groesse
      // bleiben vergleichbar (uebliche Darstellung bei Overlays)
      let m = 0;
      for (let i = 0; i < geglaettet.length; i++) if (geglaettet[i] > m) m = geglaettet[i];
      const werte = this.spec.normiert === false ? geglaettet : geglaettet.map((v) => (m ? v / m : 0));
      for (const v of werte) if (v > maxWert) maxWert = v;
      return { ...r, werte, total };
    });

    for (const r of berechnet) {
      ctx.beginPath();
      for (let i = 0; i < r.werte.length; i++) {
        const sx = (i + 0.5) / r.werte.length;
        const sy = r.werte[i] / (maxWert || 1);
        const [px, py] = this.toPixel(sx, sy);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.strokeStyle = r.farbe;
      ctx.lineWidth = 1.6;
      ctx.stroke();
      // gefuellte Flaeche
      const [pxEnde] = this.toPixel(1, 0);
      const [pxStart, pyBasis] = this.toPixel(0, 0);
      ctx.lineTo(pxEnde, pyBasis);
      ctx.lineTo(pxStart, pyBasis);
      ctx.closePath();
      ctx.globalAlpha = 0.16;
      ctx.fillStyle = r.farbe;
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // Intervallgates als senkrechte Marken
    this.zeichneGates(ctx, stil, true);

    // Legende
    ctx.font = '11px system-ui, sans-serif';
    let y = l.y1 + 12;
    for (const r of berechnet) {
      if (!r.name) continue;
      ctx.fillStyle = r.farbe;
      ctx.fillRect(l.x1 - 120, y - 7, 8, 8);
      ctx.fillStyle = stil.text;
      ctx.fillText(`${r.name} (n=${r.total.toLocaleString('de-DE')})`, l.x1 - 108, y);
      y += 14;
    }
  }

  /* ---------------------------------------------------------------- */
  /* Einbettung (t-SNE, PCA, FlowSOM)                                  */
  /* ---------------------------------------------------------------- */

  zeichneEinbettung(ctx, stil) {
    const l = this.layout;
    const e = this.spec.embedding;
    this.zeichneRahmen(ctx, stil);
    if (!e || !e.punkte?.length) {
      this.zeichneHinweis(ctx, 'Noch keine Einbettung berechnet');
      return;
    }
    const groesse = e.punkte.length > 8000 ? 1.4 : 2.4;
    for (let i = 0; i < e.punkte.length; i++) {
      const [px, py] = this.toPixel(e.punkte[i][0], e.punkte[i][1]);
      ctx.fillStyle = e.cluster
        ? CLUSTER_FARBEN[e.cluster[i] % CLUSTER_FARBEN.length]
        : stil.punkt;
      ctx.fillRect(px, py, groesse, groesse);
    }
    ctx.fillStyle = stil.gedaempft;
    ctx.font = '11px system-ui, sans-serif';
    ctx.fillText(e.titel || '', l.x0, l.y1 - 8);
  }

  /* ---------------------------------------------------------------- */
  /* Achsen, Rahmen, Gates                                             */
  /* ---------------------------------------------------------------- */

  zeichneRahmen(ctx, stil) {
    const l = this.layout;
    ctx.strokeStyle = stil.achse;
    ctx.lineWidth = 1;
    ctx.strokeRect(l.x0 + 0.5, l.y1 + 0.5, l.plotBreite, l.plotHoehe);
  }

  zeichneAchsen(ctx, stil, trX, trY, istHistogramm = false) {
    const l = this.layout;
    const { sample, xParam, yParam } = this.spec;
    ctx.font = '10px system-ui, sans-serif';
    ctx.fillStyle = stil.gedaempft;
    ctx.strokeStyle = stil.achse;

    // Beschriftungen mit Mindestabstand: bei Logicle-Achsen liegen die
    // Dekaden nahe der Null so dicht, dass sie sonst uebereinanderfallen.
    let letzteX = -Infinity;
    for (const t of trX.ticks()) {
      const [px] = this.toPixel(t.pos, 0);
      if (px < l.x0 - 1 || px > l.x1 + 1) continue;
      ctx.beginPath();
      ctx.moveTo(px, l.y0);
      ctx.lineTo(px, l.y0 + (t.minor ? 3 : 6));
      ctx.stroke();
      if (t.label && px - letzteX >= 30) {
        ctx.textAlign = 'center';
        ctx.fillText(hochStellen(t.label), px, l.y0 + 18);
        letzteX = px;
      }
    }
    ctx.textAlign = 'left';

    if (trY) {
      let letzteY = Infinity;
      for (const t of trY.ticks()) {
        const [, py] = this.toPixel(0, t.pos);
        if (py < l.y1 - 1 || py > l.y0 + 1) continue;
        ctx.beginPath();
        ctx.moveTo(l.x0, py);
        ctx.lineTo(l.x0 - (t.minor ? 3 : 6), py);
        ctx.stroke();
        if (t.label && letzteY - py >= 13) {
          ctx.textAlign = 'right';
          ctx.fillText(hochStellen(t.label), l.x0 - 9, py + 3);
          letzteY = py;
        }
      }
      ctx.textAlign = 'left';
    } else if (istHistogramm) {
      ctx.textAlign = 'right';
      ctx.fillText('rel.', l.x0 - 9, l.y1 + 10);
      ctx.textAlign = 'left';
    }

    // Achsentitel
    ctx.fillStyle = stil.text;
    ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(kanalName(sample, xParam), l.x0 + l.plotBreite / 2, l.hoehe - 8);
    if (trY) {
      ctx.save();
      ctx.translate(13, l.y1 + l.plotHoehe / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(kanalName(sample, yParam), 0, 0);
      ctx.restore();
    } else {
      ctx.save();
      ctx.translate(13, l.y1 + l.plotHoehe / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText('Ereignisse (normiert)', 0, 0);
      ctx.restore();
    }
    ctx.textAlign = 'left';
  }

  /** Zeichnet alle Kindgates der dargestellten Population. */
  zeichneGates(ctx, stil, nurIntervalle = false) {
    const l = this.layout;
    const { sample, gateId, xParam, yParam } = this.spec;
    const sichtbar = state.gates.filter((g) => {
      if ((g.parentId || null) !== (gateId || null)) return false;
      if (g.type === 'boolean') return false;
      if (g.type === 'interval') return g.xParam === xParam;
      if (nurIntervalle) return false;
      return g.xParam === xParam && g.yParam === yParam;
    });

    ctx.font = '11px system-ui, sans-serif';
    const belegt = [];
    for (const g of sichtbar) {
      const aktiv = g.id === state.activeGateId;
      ctx.strokeStyle = g.color || stil.gate;
      ctx.lineWidth = aktiv ? 2.2 : 1.4;
      ctx.setLineDash(g.auto?.vorlaeufig ? [5, 3] : []);

      let beschriftungBei = null;
      if (g.type === 'rect') {
        const [x1, y1] = this.toPixel(Math.min(g.geom.x1, g.geom.x2), Math.max(g.geom.y1, g.geom.y2));
        const [x2, y2] = this.toPixel(Math.max(g.geom.x1, g.geom.x2), Math.min(g.geom.y1, g.geom.y2));
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        beschriftungBei = [x1, y1 - 5];
      } else if (g.type === 'polygon') {
        ctx.beginPath();
        g.geom.points.forEach((p, i) => {
          const [px, py] = this.toPixel(p[0], p[1]);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.closePath();
        ctx.stroke();
        const oben = g.geom.points.reduce((a, b) => (b[1] > a[1] ? b : a));
        beschriftungBei = this.toPixel(oben[0], oben[1]);
        beschriftungBei[1] -= 5;
      } else if (g.type === 'ellipse') {
        const [cx, cy] = this.toPixel(g.geom.cx, g.geom.cy);
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(-g.geom.angle);
        ctx.beginPath();
        ctx.ellipse(0, 0, g.geom.rx * l.plotBreite, g.geom.ry * l.plotHoehe, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
        beschriftungBei = [cx, cy - g.geom.ry * l.plotHoehe - 5];
      } else if (g.type === 'interval') {
        const [px1] = this.toPixel(g.geom.min, 0);
        const [px2] = this.toPixel(g.geom.max, 0);
        ctx.beginPath();
        ctx.moveTo(px1, l.y1);
        ctx.lineTo(px1, l.y0);
        ctx.moveTo(px2, l.y1);
        ctx.lineTo(px2, l.y0);
        ctx.stroke();
        ctx.globalAlpha = 0.07;
        ctx.fillStyle = g.color || stil.gate;
        ctx.fillRect(Math.min(px1, px2), l.y1, Math.abs(px2 - px1), l.plotHoehe);
        ctx.globalAlpha = 1;
        beschriftungBei = [Math.min(px1, px2) + 4, l.y1 + 12];
      } else if (g.type === 'quadrant') {
        const [qx, qy] = this.toPixel(g.geom.x, g.geom.y);
        ctx.beginPath();
        ctx.moveTo(qx, l.y1);
        ctx.lineTo(qx, l.y0);
        ctx.moveTo(l.x0, qy);
        ctx.lineTo(l.x1, qy);
        ctx.stroke();
        const ecken = { Q1: [l.x0 + 6, l.y1 + 14], Q2: [l.x1 - 90, l.y1 + 14], Q3: [l.x0 + 6, l.y0 - 6], Q4: [l.x1 - 90, l.y0 - 6] };
        beschriftungBei = ecken[g.geom.quadrant];
      }
      ctx.setLineDash([]);

      if (beschriftungBei && this.spec.gateBeschriftung !== false) {
        const st = gateStats(sample, g.id);
        const text = `${g.name}  ${st.pctParent.toFixed(1).replace('.', ',')} %`;
        // Farbmarke und Text getrennt: die Gate-Farben sind auf Unterscheid-
        // barkeit optimiert, nicht auf Lesbarkeit -- der Text nimmt deshalb
        // die Vordergrundfarbe des jeweiligen Designs.
        const MARKE = 9;
        const breite = ctx.measureText(text).width + 8 + MARKE;

        // In den Plotbereich hineinziehen, damit nichts abgeschnitten wird
        let bx = Math.min(Math.max(beschriftungBei[0], l.x0 + 2), l.x1 - breite - 2);
        let by = Math.min(Math.max(beschriftungBei[1], l.y1 + 12), l.y0 - 2);

        // Ueberdeckungen aufloesen: nach unten ausweichen
        for (let versuch = 0; versuch < 6; versuch++) {
          const kollision = belegt.some((r) => bx < r.x + r.b && bx + breite > r.x && by - 11 < r.y + 14 && by + 3 > r.y);
          if (!kollision) break;
          by += 15;
          if (by > l.y0 - 2) { by = l.y1 + 12; bx += 14; }
        }
        belegt.push({ x: bx, y: by - 11, b: breite });

        ctx.fillStyle = stil.beschriftungHintergrund;
        ctx.fillRect(bx - 2, by - 11, breite, 14);
        ctx.fillStyle = g.color || stil.gate;
        ctx.fillRect(bx + 1, by - 8, 6, 8);
        ctx.fillStyle = stil.text;
        ctx.fillText(text, bx + 2 + MARKE, by);
      }
    }
  }

  zeichneBeschriftung(ctx, stil, n) {
    const l = this.layout;
    const g = this.spec.gateId ? gateById(this.spec.gateId) : null;
    ctx.font = '11px system-ui, sans-serif';
    ctx.fillStyle = stil.gedaempft;
    const text = `${g ? g.name : 'Alle Ereignisse'} · n = ${n.toLocaleString('de-DE')}`;
    ctx.fillText(text, l.x0, l.y1 - 8);
  }

  /* ---------------------------------------------------------------- */
  /* Treffersuche fuer Interaktion                                     */
  /* ---------------------------------------------------------------- */

  /** Findet das Gate unter dem Mauszeiger. */
  gateAn(px, py) {
    const [sx, sy] = this.toScale(px, py);
    const { gateId, xParam, yParam } = this.spec;
    const kandidaten = state.gates.filter((g) => (g.parentId || null) === (gateId || null));
    for (const g of kandidaten) {
      if (g.type === 'rect' && g.xParam === xParam && g.yParam === yParam) {
        const { x1, y1, x2, y2 } = g.geom;
        if (sx >= Math.min(x1, x2) && sx <= Math.max(x1, x2) && sy >= Math.min(y1, y2) && sy <= Math.max(y1, y2)) return g;
      } else if (g.type === 'polygon' && g.xParam === xParam && g.yParam === yParam) {
        if (pointInPolygon(sx, sy, g.geom.points)) return g;
      } else if (g.type === 'ellipse' && g.xParam === xParam && g.yParam === yParam) {
        if (pointInEllipse(sx, sy, g.geom)) return g;
      } else if (g.type === 'interval' && g.xParam === xParam) {
        if (sx >= g.geom.min && sx <= g.geom.max) return g;
      }
    }
    return null;
  }
}

/* ------------------------------------------------------------------ */
/* Heatmap der Markerexpression je Cluster                             */
/* ------------------------------------------------------------------ */

/**
 * Zeichnet die Medianexpression je Metacluster als Waermekarte --
 * die kompakteste Uebersicht ueber ein Mehrfarbenpanel.
 */
export function zeichneHeatmap(canvas, ergebnis, sample) {
  const stil = leseStil();
  const dpr = window.devicePixelRatio || 1;
  const b = canvas.getBoundingClientRect();
  canvas.width = b.width * dpr;
  canvas.height = b.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, b.width, b.height);
  ctx.fillStyle = stil.hintergrund;
  ctx.fillRect(0, 0, b.width, b.height);

  if (!ergebnis?.profiles?.length) {
    ctx.fillStyle = stil.gedaempft;
    ctx.font = '13px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Noch keine Clusteranalyse berechnet', b.width / 2, b.height / 2);
    ctx.textAlign = 'left';
    return;
  }

  const links = 150;
  const oben = 84;
  const nZeilen = ergebnis.profiles.length;
  const nSpalten = ergebnis.params.length;
  const zh = Math.min(26, (b.height - oben - 20) / nZeilen);
  const zb = Math.min(64, (b.width - links - 60) / nSpalten);

  ctx.font = '10px system-ui, sans-serif';
  // Spaltenkoepfe (Marker), gedreht
  for (let j = 0; j < nSpalten; j++) {
    ctx.save();
    ctx.translate(links + j * zb + zb / 2, oben - 6);
    ctx.rotate(-Math.PI / 4);
    ctx.fillStyle = stil.text;
    ctx.textAlign = 'left';
    ctx.fillText(kanalName(sample, ergebnis.params[j]), 0, 0);
    ctx.restore();
  }

  for (let i = 0; i < nZeilen; i++) {
    const p = ergebnis.profiles[i];
    const y = oben + i * zh;
    ctx.fillStyle = stil.text;
    ctx.textAlign = 'right';
    ctx.fillText(`Cluster ${p.cluster + 1} (${p.fraction.toFixed(1)} %)`, links - 8, y + zh / 2 + 3);
    ctx.textAlign = 'left';

    ctx.fillStyle = CLUSTER_FARBEN[p.cluster % CLUSTER_FARBEN.length];
    ctx.fillRect(links - 5, y + 2, 3, zh - 4);

    for (let j = 0; j < nSpalten; j++) {
      ctx.fillStyle = lutFarbe(HEAT_LUT, p.profile[j]);
      ctx.fillRect(links + j * zb, y, zb - 1, zh - 1);
    }
  }

  // Farbskala
  const skalaY = oben + nZeilen * zh + 14;
  for (let i = 0; i < 120; i++) {
    ctx.fillStyle = lutFarbe(HEAT_LUT, i / 119);
    ctx.fillRect(links + i, skalaY, 1, 8);
  }
  ctx.fillStyle = stil.gedaempft;
  ctx.fillText('niedrig', links, skalaY + 20);
  ctx.fillText('hoch', links + 100, skalaY + 20);
  ctx.fillText('Medianexpression (Displayskala)', links + 150, skalaY + 20);
}

/**
 * Zeichnet den minimalen Spannbaum der SOM-Knoten (FlowSOM-Uebersicht).
 */
export function zeichneMST(canvas, ergebnis) {
  const stil = leseStil();
  const dpr = window.devicePixelRatio || 1;
  const b = canvas.getBoundingClientRect();
  canvas.width = b.width * dpr;
  canvas.height = b.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.fillStyle = stil.hintergrund;
  ctx.fillRect(0, 0, b.width, b.height);
  if (!ergebnis?.som) return;

  const { som, mst, meta, nodeCounts } = ergebnis;
  const { width, height } = som;
  const zellB = (b.width - 40) / width;
  const zellH = (b.height - 40) / height;
  const pos = (i) => [20 + (i % width) * zellB + zellB / 2, 20 + Math.floor(i / width) * zellH + zellH / 2];

  ctx.strokeStyle = stil.achse;
  ctx.lineWidth = 1;
  for (const e of mst) {
    const [x1, y1] = pos(e.a);
    const [x2, y2] = pos(e.b);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  let maxN = 1;
  for (const n of nodeCounts) if (n > maxN) maxN = n;
  for (let i = 0; i < som.nodes.length; i++) {
    const [x, y] = pos(i);
    const r = 2 + 10 * Math.sqrt(nodeCounts[i] / maxN);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = CLUSTER_FARBEN[meta.label[i] % CLUSTER_FARBEN.length];
    ctx.fill();
  }
  ctx.fillStyle = stil.gedaempft;
  ctx.font = '11px system-ui, sans-serif';
  ctx.fillText('FlowSOM: Knotengröße = Ereigniszahl, Farbe = Metacluster', 20, b.height - 8);
}

/* ------------------------------------------------------------------ */
/* Hilfen                                                              */
/* ------------------------------------------------------------------ */

function lutFarbe(lut, t) {
  const i = Math.max(0, Math.min(255, Math.round(t * 255)));
  return `rgb(${lut[i * 3]},${lut[i * 3 + 1]},${lut[i * 3 + 2]})`;
}

export function kanalName(sample, index) {
  const p = sample.params[index];
  if (!p) return '?';
  return p.stain ? `${p.stain}` : p.name;
}

export function kanalNameLang(sample, index) {
  const p = sample.params[index];
  if (!p) return '?';
  return p.stain ? `${p.stain} · ${p.name}` : p.name;
}

/** Wandelt "10^3" in eine hochgestellte Darstellung. */
function hochStellen(label) {
  const m = String(label).match(/^(-?)10\^(-?\d+)$/);
  if (!m) return label;
  const ziffern = { '-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' };
  return `${m[1]}10${[...m[2]].map((c) => ziffern[c] || c).join('')}`;
}

function leseStil() {
  const s = getComputedStyle(document.documentElement);
  const v = (n, f) => (s.getPropertyValue(n) || f).trim();
  return {
    hintergrund: v('--plot-bg', '#0e1116'),
    achse: v('--plot-axis', '#39414d'),
    text: v('--fg', '#e6e9ef'),
    gedaempft: v('--fg-muted', '#8b95a5'),
    punkt: v('--plot-point', '#7aa2f7'),
    backgate: v('--plot-backgate', '#2c3340'),
    gate: v('--accent', '#4cc9f0'),
    beschriftungHintergrund: v('--plot-label-bg', 'rgba(14,17,22,0.78)'),
  };
}

/** Kantenpunkte einer Gitterzelle fuer Marching Squares. */
function kante(nr, sx, sy, w) {
  switch (nr) {
    case 0: return [sx + w / 2, sy];
    case 1: return [sx + w, sy + w / 2];
    case 2: return [sx + w / 2, sy + w];
    default: return [sx, sy + w / 2];
  }
}

const MARCHING = {
  1: [[2, 3]], 2: [[1, 2]], 3: [[1, 3]], 4: [[0, 1]],
  5: [[0, 3], [1, 2]], 6: [[0, 2]], 7: [[0, 3]], 8: [[0, 3]],
  9: [[0, 2]], 10: [[0, 1], [2, 3]], 11: [[0, 1]], 12: [[1, 3]],
  13: [[1, 2]], 14: [[2, 3]],
};

export { leseStil };
