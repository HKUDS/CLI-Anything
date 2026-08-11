import { test, expect, describe } from 'bun:test';

import { Logicle, makeTransform, estimateW } from '../src/core/transform.js';
import { invert, matVec, jacobiEigen, identity } from '../src/core/matrix.js';
import { parseFCS, parseSpillover, parseCSV } from '../src/core/fcs.js';
import { pointInPolygon, pointInEllipse, convexHull } from '../src/core/gating.js';
import {
  percentileSorted,
  channelStats,
  otsuThreshold,
  histogram1D,
  smooth1D,
  densityGrid,
  findPeaks2D,
  ellipseFromPoints,
  rareEventLimits,
  poissonCI,
  overtonPositive,
  ksStatistic,
} from '../src/core/stats.js';
import { evaluateExpression } from '../src/core/strategy.js';
import { kmeans, pca, metaCluster, minimumSpanningTree } from '../src/core/cluster.js';
import { canonicalMarker, autoMapMarkers } from '../src/knowledge/markers.js';
import { bewerte, bereichFuerAlter, importReferenzen, exportReferenzen } from '../src/knowledge/reference.js';
import { scorePanelFit, PANELS } from '../src/knowledge/panels.js';
import { writeFCS, makeTBNKSample, rng, gauss } from './helpers.js';

/* ================================================================== */
describe('Lineare Algebra', () => {
  test('Inverse einer regulaeren Matrix', () => {
    const m = [
      Float64Array.from([1, 0.14, 0.02]),
      Float64Array.from([0.03, 1, 0.09]),
      Float64Array.from([0, 0.05, 1]),
    ];
    const inv = invert(m);
    expect(inv).not.toBeNull();
    // m * inv soll die Einheitsmatrix ergeben
    for (let i = 0; i < 3; i++) {
      const row = matVec(inv, m.map((r) => r[i]));
      for (let j = 0; j < 3; j++) {
        expect(row[j]).toBeCloseTo(i === j ? 1 : 0, 10);
      }
    }
  });

  test('Singulaere Matrix liefert null', () => {
    const m = [Float64Array.from([1, 2]), Float64Array.from([2, 4])];
    expect(invert(m)).toBeNull();
  });

  test('Eigenzerlegung einer symmetrischen Matrix', () => {
    const m = [Float64Array.from([2, 1]), Float64Array.from([1, 2])];
    const { values } = jacobiEigen(m);
    expect(values[0]).toBeCloseTo(3, 8);
    expect(values[1]).toBeCloseTo(1, 8);
  });
});

/* ================================================================== */
describe('Logicle-Transformation', () => {
  const lg = new Logicle(262144, 0.5, 4.5, 0);

  test('Nullpunkt liegt bei x1', () => {
    expect(lg.scale(0)).toBeCloseTo(lg.x1, 10);
    expect(lg.inverse(lg.x1)).toBeCloseTo(0, 6);
  });

  test('Oberer Skalenwert bildet auf 1 ab', () => {
    expect(lg.inverse(1)).toBeCloseTo(262144, 2);
    expect(lg.scale(262144)).toBeCloseTo(1, 8);
  });

  test('scale und inverse sind zueinander invers', () => {
    for (const v of [-5000, -100, -1, 0, 1, 100, 1000, 25000, 262144]) {
      expect(lg.inverse(lg.scale(v))).toBeCloseTo(v, 3);
    }
  });

  test('streng monoton wachsend', () => {
    let last = -Infinity;
    for (let i = 0; i <= 200; i++) {
      const v = lg.inverse(i / 200);
      expect(v).toBeGreaterThan(last);
      last = v;
    }
  });

  test('zweite Ableitung verschwindet in x1 (Logicle-Bedingung)', () => {
    // taylor[1] ist der Koeffizient von t^2 und muss null sein
    expect(Math.abs(lg.taylor[1])).toBeLessThan(1e-12);
  });

  test('Tabellenbasierte Skalierung stimmt im Anzeigebereich mit der exakten ueberein', () => {
    const tr = makeTransform({ kind: 'logicle', T: 262144, W: 0.5, M: 4.5, A: 0 });
    for (const v of [-100, -50, 0, 33, 900, 15000, 200000, 262144]) {
      expect(tr.scale(v)).toBeCloseTo(tr.scaleExact(v), 4);
    }
  });

  test('Werte ausserhalb des Anzeigebereichs werden auf die Achse geklemmt', () => {
    const tr = makeTransform({ kind: 'logicle', T: 262144, W: 0.5, M: 4.5, A: 0 });
    // Der darstellbare Bereich reicht von inverse(0) bis inverse(1).
    expect(tr.vMin).toBeGreaterThan(-1000);
    expect(tr.scale(tr.vMin - 5000)).toBe(0);
    expect(tr.scale(tr.vMax * 10)).toBe(1);
    // die exakte Skalierung klemmt bewusst nicht -- sie wird fuer Achsen gebraucht
    expect(tr.scaleExact(tr.vMin - 5000)).toBeLessThan(0);
  });

  test('W-Schaetzung liefert einen zulaessigen Wert', () => {
    const rand = rng(5);
    const values = new Float32Array(5000);
    for (let i = 0; i < values.length; i++) values[i] = i % 3 === 0 ? gauss(rand) * 400 : 20000 * Math.exp(gauss(rand) * 0.3);
    const w = estimateW(values, 262144, 4.5);
    expect(w).toBeGreaterThan(0);
    expect(2 * w).toBeLessThanOrEqual(4.5);
    expect(() => new Logicle(262144, w, 4.5, 0)).not.toThrow();
  });

  test('unzulaessige Parameter werden abgewiesen', () => {
    expect(() => new Logicle(0, 0.5, 4.5, 0)).toThrow();
    expect(() => new Logicle(262144, 3, 4.5, 0)).toThrow();
  });
});

/* ================================================================== */
describe('Weitere Transformationen', () => {
  test('linear', () => {
    const tr = makeTransform({ kind: 'linear', min: 0, max: 1000 });
    expect(tr.scale(500)).toBeCloseTo(0.5, 10);
    expect(tr.inverse(0.25)).toBeCloseTo(250, 10);
  });

  test('log10', () => {
    const tr = makeTransform({ kind: 'log', min: 1, max: 10000 });
    expect(tr.scale(100)).toBeCloseTo(0.5, 10);
    expect(tr.inverse(1)).toBeCloseTo(10000, 6);
  });

  test('arcsinh bildet negative Werte ab', () => {
    const tr = makeTransform({ kind: 'asinh', cofactor: 150, min: -1000, max: 262144 });
    expect(tr.scale(-1000)).toBeCloseTo(0, 10);
    expect(tr.scale(0)).toBeGreaterThan(0);
    expect(tr.inverse(tr.scale(-500))).toBeCloseTo(-500, 3);
  });
});

/* ================================================================== */
describe('FCS-Parser', () => {
  test('liest eine 32-Bit-Float-Datei vollstaendig', () => {
    const data = new Float32Array([1, 2, 3, 4, 5, 6]);
    const buf = writeFCS(['FSC-A', 'SSC-A', 'FITC-A'], ['', '', 'CD3'], data, 2);
    const s = parseFCS(buf, 'test.fcs');
    expect(s.nEvents).toBe(2);
    expect(s.nParams).toBe(3);
    expect(s.params[2].stain).toBe('CD3');
    expect(s.params[2].label).toBe('FITC-A (CD3)');
    expect(Array.from(s.data)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(s.meta.cytometer).toBe('Testzytometer');
  });

  test('liest Ganzzahldaten', () => {
    const data = new Float32Array([10, 20, 30, 40]);
    const buf = writeFCS(['FSC-A', 'SSC-A'], ['', ''], data, 2, {}, 'I');
    const s = parseFCS(buf, 'int.fcs');
    expect(Array.from(s.data)).toEqual([10, 20, 30, 40]);
  });

  test('lehnt Nicht-FCS-Dateien ab', () => {
    const buf = new TextEncoder().encode('Dies ist keine FCS-Datei........').buffer;
    expect(() => parseFCS(buf, 'x.fcs')).toThrow(/FCS-Format/);
  });

  test('Spillover-Matrix wird korrekt zerlegt', () => {
    const spill = parseSpillover('2,FITC-A,PE-A,1,0.15,0.02,1');
    expect(spill.channels).toEqual(['FITC-A', 'PE-A']);
    expect(spill.matrix[0][1]).toBeCloseTo(0.15, 10);
    expect(spill.matrix[1][0]).toBeCloseTo(0.02, 10);
  });

  test('unvollstaendige Spillover-Angabe liefert null', () => {
    expect(parseSpillover('3,A,B,C,1,0,0')).toBeNull();
    expect(parseSpillover('')).toBeNull();
  });

  test('Spillover aus der Datei landet in der Probe', () => {
    const { buffer } = makeTBNKSample(500, 3);
    const s = parseFCS(buffer, 'tbnk.fcs');
    expect(s.comp.channels.length).toBe(5);
    expect(s.comp.enabled).toBe(true);
    expect(s.comp.matrix[0][1]).toBeCloseTo(0.14, 6);
  });

  test('logarithmisch aufgezeichnete Kanaele werden linearisiert', () => {
    // $PnE = "4,1" bedeutet 4 Dekaden ueber den Bereich 1024
    const data = new Float32Array([0, 512, 1024]);
    const buf = writeFCS(['LOG-A'], [''], data, 3, {
      $P1E: '4,1',
      $P1R: '1024',
    });
    const s = parseFCS(buf, 'log.fcs');
    expect(s.data[0]).toBeCloseTo(1, 4); // 10^0
    expect(s.data[1]).toBeCloseTo(100, 2); // 10^2
    expect(s.data[2]).toBeCloseTo(10000, 0); // 10^4
  });

  test('CSV-Import erkennt Trennzeichen und Marker', () => {
    const csv = 'FSC-A;SSC-A;FITC-A :: CD3\n100;200;5000\n110;210;40\n';
    const s = parseCSV(csv, 'tabelle.csv');
    expect(s.nEvents).toBe(2);
    expect(s.params[2].stain).toBe('CD3');
    expect(s.data[2]).toBeCloseTo(5000, 6);
  });
});

/* ================================================================== */
describe('Gate-Geometrie', () => {
  const quadrat = [[0, 0], [1, 0], [1, 1], [0, 1]];

  test('Punkt im Polygon', () => {
    expect(pointInPolygon(0.5, 0.5, quadrat)).toBe(true);
    expect(pointInPolygon(1.5, 0.5, quadrat)).toBe(false);
    expect(pointInPolygon(-0.1, 0.5, quadrat)).toBe(false);
  });

  test('konkaves Polygon', () => {
    const l = [[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]];
    expect(pointInPolygon(0.5, 1.5, l)).toBe(true);
    expect(pointInPolygon(1.5, 1.5, l)).toBe(false);
  });

  test('Punkt in Ellipse mit Drehung', () => {
    const g = { cx: 0, cy: 0, rx: 2, ry: 1, angle: 0 };
    expect(pointInEllipse(1.9, 0, g)).toBe(true);
    expect(pointInEllipse(0, 1.1, g)).toBe(false);
    const gedreht = { ...g, angle: Math.PI / 2 };
    expect(pointInEllipse(0, 1.9, gedreht)).toBe(true);
    expect(pointInEllipse(1.9, 0, gedreht)).toBe(false);
  });

  test('konvexe Huelle', () => {
    const pts = [[0, 0], [1, 0], [1, 1], [0, 1], [0.5, 0.5]];
    const hull = convexHull(pts);
    expect(hull.length).toBe(4);
    expect(hull.some((p) => p[0] === 0.5 && p[1] === 0.5)).toBe(false);
  });
});

/* ================================================================== */
describe('Statistik', () => {
  test('Perzentile', () => {
    const s = Float64Array.from([1, 2, 3, 4, 5]);
    expect(percentileSorted(s, 0.5)).toBe(3);
    expect(percentileSorted(s, 0)).toBe(1);
    expect(percentileSorted(s, 1)).toBe(5);
    expect(percentileSorted(Float64Array.from([1, 2, 3, 4]), 0.5)).toBeCloseTo(2.5, 10);
  });

  test('Kennzahlen eines Kanals', () => {
    const v = Float32Array.from([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    const st = channelStats(v, null);
    expect(st.n).toBe(10);
    expect(st.mean).toBeCloseTo(5.5, 10);
    expect(st.median).toBeCloseTo(5.5, 10);
    expect(st.min).toBe(1);
    expect(st.max).toBe(10);
    expect(st.q1).toBeCloseTo(3.25, 10);
    expect(st.q3).toBeCloseTo(7.75, 10);
  });

  test('Kennzahlen nur der ausgewaehlten Ereignisse', () => {
    const v = Float32Array.from([1, 100, 2, 200, 3]);
    const st = channelStats(v, Int32Array.from([0, 2, 4]));
    expect(st.n).toBe(3);
    expect(st.median).toBe(2);
  });

  test('leere Auswahl liefert NaN statt Absturz', () => {
    const st = channelStats(Float32Array.from([1, 2]), Int32Array.from([]));
    expect(st.n).toBe(0);
    expect(Number.isNaN(st.median)).toBe(true);
  });

  test('Otsu trennt zwei Gipfel', () => {
    const bins = new Float64Array(256);
    for (let i = 20; i < 40; i++) bins[i] = 100;
    for (let i = 180; i < 200; i++) bins[i] = 100;
    const t = otsuThreshold(bins);
    // zulaessig ist jede Trennstelle zwischen dem letzten Bin des ersten und
    // dem ersten Bin des zweiten Gipfels
    expect(t).toBeGreaterThanOrEqual(39);
    expect(t).toBeLessThan(180);
  });

  test('Dichtegitter findet den Gipfel an der richtigen Stelle', () => {
    const rand = rng(9);
    const n = 5000;
    const xs = new Float32Array(n);
    const ys = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      xs[i] = 0.3 + gauss(rand) * 0.02;
      ys[i] = 0.7 + gauss(rand) * 0.02;
    }
    const d = densityGrid(xs, ys, null, 128, 2);
    const peaks = findPeaks2D(d, 0.3);
    expect(peaks.length).toBeGreaterThan(0);
    expect(peaks[0].sx).toBeCloseTo(0.3, 1);
    expect(peaks[0].sy).toBeCloseTo(0.7, 1);
  });

  test('Ellipse aus einer Punktwolke', () => {
    const rand = rng(4);
    const n = 4000;
    const xs = new Float32Array(n);
    const ys = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      xs[i] = 0.5 + gauss(rand) * 0.1;
      ys[i] = 0.5 + gauss(rand) * 0.02;
    }
    const e = ellipseFromPoints(xs, ys, null, 2);
    expect(e.cx).toBeCloseTo(0.5, 1);
    expect(e.rx).toBeGreaterThan(e.ry);
    expect(e.rx).toBeCloseTo(0.2, 1);
  });

  test('Glaettung erhaelt die Gesamtmasse', () => {
    const bins = new Float64Array(64);
    bins[32] = 100;
    const sm = smooth1D(bins, 2);
    const summe = sm.reduce((a, b) => a + b, 0);
    expect(summe).toBeCloseTo(100, 6);
  });

  test('Nachweis- und Bestimmungsgrenze', () => {
    const l = rareEventLimits(500000);
    expect(l.lod).toBeCloseTo(0.004, 6);
    expect(l.lloq).toBeCloseTo(0.01, 6);
  });

  test('Poisson-Vertrauensbereich umschliesst den Punktwert', () => {
    const ci = poissonCI(50, 100000);
    expect(ci.low).toBeLessThan(0.05);
    expect(ci.high).toBeGreaterThan(0.05);
  });

  test('Overton-Subtraktion', () => {
    const kontrolle = new Float64Array(100);
    const probe = new Float64Array(100);
    for (let i = 0; i < 20; i++) kontrolle[i] = 100;
    for (let i = 0; i < 20; i++) probe[i] = 50;
    for (let i = 60; i < 80; i++) probe[i] = 50;
    const pos = overtonPositive(probe, kontrolle);
    expect(pos).toBeCloseTo(50, 0);
  });

  test('KS-Statistik erkennt identische und verschiedene Verteilungen', () => {
    const a = new Float64Array(50);
    const b = new Float64Array(50);
    for (let i = 0; i < 25; i++) a[i] = 10;
    for (let i = 25; i < 50; i++) b[i] = 10;
    expect(ksStatistic(a, a).d).toBeCloseTo(0, 10);
    expect(ksStatistic(a, b).d).toBeCloseTo(1, 6);
  });
});

/* ================================================================== */
describe('Ausdrucksauswertung', () => {
  const ctx = {
    pctOf: (a, b) => (a === 'x' && b === 'y' ? 40 : 10),
    ratio: (a, b) => 2.5,
    count: () => 1000,
    mfiRatio: (a, b, m) => (m === 'SSC-A' ? 5.5 : 1),
    mfi: (s, m) => 1234,
  };

  test('einfacher Funktionsaufruf', () => {
    expect(evaluateExpression('pctOf(x, y)', ctx)).toBe(40);
  });

  test('Grundrechenarten und Klammern', () => {
    expect(evaluateExpression('100 - pctOf(x, y) - pctOf(a, b)', ctx)).toBe(50);
    expect(evaluateExpression('(pctOf(x, y) + 60) / 2', ctx)).toBe(50);
    expect(evaluateExpression('2 * ratio(a, b)', ctx)).toBe(5);
  });

  test('Argumente mit Bindestrich', () => {
    expect(evaluateExpression('mfiRatio(g, l, SSC-A)', ctx)).toBe(5.5);
  });

  test('unbekannte Funktion wird gemeldet', () => {
    expect(() => evaluateExpression('gibtsNicht(a)', ctx)).toThrow(/Unbekannte Funktion/);
  });
});

/* ================================================================== */
describe('Clustering', () => {
  function blobs(seed = 2) {
    const rand = rng(seed);
    const rows = [];
    const zentren = [[0, 0], [10, 10], [0, 10]];
    for (let c = 0; c < 3; c++) {
      for (let i = 0; i < 200; i++) {
        rows.push(Float32Array.from([zentren[c][0] + gauss(rand) * 0.6, zentren[c][1] + gauss(rand) * 0.6]));
      }
    }
    return rows;
  }

  test('k-Means trennt drei getrennte Wolken', () => {
    const rows = blobs();
    const { assignment } = kmeans(rows, 3, { seed: 1 });
    const gruppe = (start) => new Set(Array.from(assignment.slice(start, start + 200))).size;
    expect(gruppe(0)).toBe(1);
    expect(gruppe(200)).toBe(1);
    expect(gruppe(400)).toBe(1);
    expect(new Set(Array.from(assignment)).size).toBe(3);
  });

  test('k-Means ist bei gleichem Startwert reproduzierbar', () => {
    const rows = blobs();
    const a = kmeans(rows, 3, { seed: 7 }).assignment;
    const b = kmeans(rows, 3, { seed: 7 }).assignment;
    expect(Array.from(a)).toEqual(Array.from(b));
  });

  test('PCA erkennt die Hauptachse', () => {
    const rand = rng(6);
    const rows = [];
    for (let i = 0; i < 500; i++) {
      const t = gauss(rand) * 5;
      rows.push(Float32Array.from([t, t * 0.5 + gauss(rand) * 0.1]));
    }
    const { explained } = pca(rows, 2);
    expect(explained[0]).toBeGreaterThan(95);
  });

  test('Metaclustering fasst Knoten zusammen', () => {
    const nodes = [
      Float64Array.from([0, 0]),
      Float64Array.from([0.1, 0]),
      Float64Array.from([10, 10]),
      Float64Array.from([10.1, 10]),
    ];
    const { label, k } = metaCluster(nodes, 2);
    expect(k).toBe(2);
    expect(label[0]).toBe(label[1]);
    expect(label[2]).toBe(label[3]);
    expect(label[0]).not.toBe(label[2]);
  });

  test('Spannbaum verbindet alle Knoten', () => {
    const nodes = [
      Float64Array.from([0, 0]),
      Float64Array.from([1, 0]),
      Float64Array.from([2, 0]),
      Float64Array.from([3, 0]),
    ];
    const edges = minimumSpanningTree(nodes);
    expect(edges.length).toBe(3);
    expect(edges.every((e) => Math.abs(e.w - 1) < 1e-9)).toBe(true);
  });
});

/* ================================================================== */
describe('Markerlexikon', () => {
  test('kanonische Namen und Synonyme', () => {
    expect(canonicalMarker('CD3')).toBe('CD3');
    expect(canonicalMarker('cd3')).toBe('CD3');
    expect(canonicalMarker('HLA-DR')).toBe('HLA-DR');
    expect(canonicalMarker('HLADR')).toBe('HLA-DR');
    expect(canonicalMarker('LCA')).toBe('CD45');
    expect(canonicalMarker('FLAER-A')).toBe('FLAER');
  });

  test('Marker aus zusammengesetztem Kanalnamen', () => {
    expect(canonicalMarker('CD19 PE-Cy7')).toBe('CD19');
  });

  test('unbekannter Marker liefert null', () => {
    expect(canonicalMarker('Phantasiemarker')).toBeNull();
  });

  test('automatische Zuordnung einer Probe', () => {
    const { buffer } = makeTBNKSample(300, 2);
    const s = parseFCS(buffer, 'x.fcs');
    const map = autoMapMarkers(s);
    expect(map['FITC-A']).toBe('CD3');
    expect(map['APC-Cy7-A']).toBe('CD45');
  });
});

/* ================================================================== */
describe('Referenzbereiche', () => {
  test('altersabhaengige Auswahl', () => {
    const kind = bereichFuerAlter('CD4_LYMPH_PCT', 3);
    const erwachsen = bereichFuerAlter('CD4_LYMPH_PCT', 40);
    expect(kind).not.toBeNull();
    expect(erwachsen).not.toBeNull();
    expect(kind.oben).not.toBe(erwachsen.oben);
  });

  test('Bewertung gegen den Bereich', () => {
    expect(bewerte('CD4_LYMPH_PCT', 40, 40).status).toBe('normal');
    expect(bewerte('CD4_LYMPH_PCT', 10, 40).status).toBe('erniedrigt');
    expect(bewerte('CD4_LYMPH_PCT', 80, 40).status).toBe('erhoeht');
    expect(bewerte('CD4_LYMPH_PCT', NaN, 40).status).toBe('unbekannt');
  });

  test('Import und Export laboreigener Bereiche', () => {
    const json = exportReferenzen();
    const { katalog, uebernommen } = importReferenzen(json);
    expect(uebernommen).toBeGreaterThan(5);
    expect(katalog.CD4_LYMPH_PCT).toBeDefined();
  });

  test('fehlerhafter Import wird abgewiesen', () => {
    expect(() => importReferenzen('{"bereiche":{"X":{"bereiche":[{"vonJahre":0}]}}}')).toThrow(/unvollständige/);
    expect(() => importReferenzen('{}')).toThrow(/bereiche/);
  });
});

/* ================================================================== */
describe('Panel-Vorlagen', () => {
  test('jedes Panel ist in sich schluessig', () => {
    for (const p of PANELS) {
      const ids = new Set();
      for (const step of p.gating) {
        expect(step.id, `${p.id}: Schritt ohne ID`).toBeTruthy();
        expect(ids.has(step.id), `${p.id}: doppelte Schritt-ID ${step.id}`).toBe(false);
        ids.add(step.id);
        if (step.parent) {
          expect(ids.has(step.parent), `${p.id}: Elternschritt ${step.parent} vor ${step.id} nicht definiert`).toBe(true);
        }
      }
      // Kennzahlen duerfen sich nur auf definierte Schritte beziehen
      for (const m of p.metriken || []) {
        const bezuege = [...m.ausdruck.matchAll(/[a-zA-Z_][a-zA-Z0-9_]*\(([^)]*)\)/g)]
          .flatMap((match) => match[1].split(',').map((s) => s.trim()))
          .filter((a) => a && !/^[0-9.]+$/.test(a));
        for (const b of bezuege) {
          const istMarker = /^(CD|HLA|FSC|SSC|Kappa|Lambda|MPO|TdT|FLAER|IgD|IgM|DHR|7-AAD|cyCD3|FMC7|Time)/i.test(b);
          if (!istMarker) {
            expect(ids.has(b), `${p.id}/${m.id}: unbekannter Schrittbezug "${b}"`).toBe(true);
          }
        }
      }
    }
  });

  test('Panelpassung wird korrekt bewertet', () => {
    const tbnk = PANELS.find((p) => p.id === 'tbnk');
    const voll = scorePanelFit(tbnk, ['CD45', 'CD3', 'CD4', 'CD8', 'CD19', 'CD16', 'CD56']);
    expect(voll.score).toBeGreaterThanOrEqual(1);
    expect(voll.fehlend.length).toBe(0);

    const teil = scorePanelFit(tbnk, ['CD45', 'CD3']);
    expect(teil.score).toBeLessThan(voll.score);
    expect(teil.fehlend).toContain('CD19');
  });
});
