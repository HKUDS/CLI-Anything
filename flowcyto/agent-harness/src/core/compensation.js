/**
 * Fluoreszenz-Kompensation.
 *
 * Die Spillover-Matrix beschreibt, welcher Anteil eines Farbstoffs in fremde
 * Detektoren einstreut. Kompensiert wird durch Multiplikation der Rohwerte mit
 * der Inversen dieser Matrix -- zwingend VOR jeder Transformation, da Logicle
 * und arcsinh nichtlinear sind.
 */

import { invert, matVec } from './matrix.js';

/**
 * Ordnet die Spillover-Kanaele den Parametern der Probe zu.
 * @returns {{indices:number[], matrix:Array<Float64Array>}|null}
 */
export function alignSpillover(sample) {
  const { comp, params } = sample;
  if (!comp || !comp.matrix || !comp.channels.length) return null;

  const indices = comp.channels.map((ch) => {
    const norm = (s) => String(s).trim().toLowerCase();
    let i = params.findIndex((p) => norm(p.name) === norm(ch));
    if (i < 0) i = params.findIndex((p) => norm(p.label) === norm(ch));
    if (i < 0) i = params.findIndex((p) => norm(p.stain) === norm(ch));
    return i;
  });
  if (indices.some((i) => i < 0)) return null;

  // Anwenderkorrekturen (Feinjustage in Prozentpunkten) einrechnen.
  const n = comp.matrix.length;
  const m = comp.matrix.map((row) => Float64Array.from(row));
  if (comp.tweak) {
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const t = comp.tweak[`${i}:${j}`];
        if (t) m[i][j] = Math.max(0, m[i][j] + t / 100);
      }
    }
  }
  return { indices, matrix: m };
}

/**
 * Erzeugt die kompensierten Rohdaten. Nicht in der Spillover-Matrix enthaltene
 * Kanaele (Streulicht, Zeit) bleiben unveraendert.
 * @returns {{data:Float32Array, applied:boolean, warning:string|null}}
 */
export function computeCompensated(sample) {
  const src = sample.data;
  if (!sample.comp?.enabled) return { data: src, applied: false, warning: null };

  const aligned = alignSpillover(sample);
  if (!aligned) {
    return {
      data: src,
      applied: false,
      warning: 'Spillover-Kanäle konnten den Messparametern nicht zugeordnet werden.',
    };
  }

  const inv = invert(aligned.matrix);
  if (!inv) {
    return {
      data: src,
      applied: false,
      warning: 'Spillover-Matrix ist singulär und nicht invertierbar.',
    };
  }

  const { indices } = aligned;
  const n = indices.length;
  const nPar = sample.nParams;
  const out = new Float32Array(src.length);
  out.set(src);

  const vec = new Float64Array(n);
  const res = new Float64Array(n);
  for (let e = 0; e < sample.nEvents; e++) {
    const base = e * nPar;
    for (let k = 0; k < n; k++) vec[k] = src[base + indices[k]];
    matVec(inv, vec, res);
    for (let k = 0; k < n; k++) out[base + indices[k]] = res[k];
  }

  return { data: out, applied: true, warning: null };
}

/** Leere Einheits-Spillover-Matrix fuer manuelle Eingabe. */
export function emptySpillover(channelNames) {
  const n = channelNames.length;
  const matrix = [];
  for (let i = 0; i < n; i++) {
    const row = new Float64Array(n);
    row[i] = 1;
    matrix.push(row);
  }
  return { channels: [...channelNames], matrix };
}

/**
 * Importiert eine Kompensationsmatrix aus CSV (erste Zeile und erste Spalte
 * enthalten die Kanalnamen) -- z.B. aus FlowJo oder der Geraetesoftware.
 */
export function parseCompensationCSV(text) {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length);
  if (lines.length < 2) throw new Error('Kompensationsmatrix: zu wenige Zeilen.');
  const delim = lines[0].includes('\t') ? '\t' : lines[0].includes(';') ? ';' : ',';
  const header = lines[0].split(delim).map((s) => s.trim().replace(/^"|"$/g, ''));
  const hasCorner = header[0] === '' || /matrix|name|channel/i.test(header[0]);
  const channels = hasCorner ? header.slice(1) : header;

  const matrix = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = lines[i].split(delim).map((s) => s.trim().replace(/^"|"$/g, ''));
    const nums = (hasCorner ? cells.slice(1) : cells).map((c) => parseFloat(c.replace(',', '.')));
    if (nums.length < channels.length) continue;
    const row = new Float64Array(channels.length);
    for (let j = 0; j < channels.length; j++) row[j] = Number.isFinite(nums[j]) ? nums[j] : 0;
    matrix.push(row);
  }
  if (matrix.length !== channels.length) {
    throw new Error(
      `Kompensationsmatrix ist nicht quadratisch (${channels.length} Kanäle, ${matrix.length} Zeilen).`,
    );
  }
  // Werte in Prozent (Diagonale = 100) auf Anteile normieren.
  if (matrix[0][0] > 50) {
    for (const row of matrix) for (let j = 0; j < row.length; j++) row[j] /= 100;
  }
  return { channels, matrix };
}

/** Exportiert die aktuelle Matrix als CSV. */
export function compensationToCSV(comp) {
  if (!comp?.matrix) return '';
  const head = ['', ...comp.channels].join(',');
  const rows = comp.matrix.map((row, i) =>
    [comp.channels[i], ...Array.from(row, (v) => v.toFixed(6))].join(','),
  );
  return [head, ...rows].join('\n');
}

/**
 * Bewertet die Matrix: hoher Spillover und stark negative Kompensationswerte
 * sind Hinweise auf fehlerhafte Einzelfaerbekontrollen.
 */
export function assessCompensation(sample) {
  const aligned = alignSpillover(sample);
  if (!aligned) return { ok: false, issues: ['Keine zuordenbare Spillover-Matrix vorhanden.'] };
  const { matrix } = aligned;
  const issues = [];
  const n = matrix.length;
  for (let i = 0; i < n; i++) {
    if (Math.abs(matrix[i][i] - 1) > 0.01) {
      issues.push(`Diagonalelement ${sample.comp.channels[i]} ist ${matrix[i][i].toFixed(3)} statt 1,000.`);
    }
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      if (matrix[i][j] > 1.0) {
        issues.push(
          `Spillover ${sample.comp.channels[i]} → ${sample.comp.channels[j]} beträgt ${(matrix[i][j] * 100).toFixed(0)} % (> 100 %).`,
        );
      }
      if (matrix[i][j] < 0) {
        issues.push(
          `Negativer Spillover ${sample.comp.channels[i]} → ${sample.comp.channels[j]} (${(matrix[i][j] * 100).toFixed(1)} %).`,
        );
      }
    }
  }
  const inv = invert(matrix);
  if (!inv) issues.push('Matrix ist singulär.');
  return { ok: issues.length === 0, issues };
}
