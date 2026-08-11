/**
 * FCS-Parser (Flow Cytometry Standard 2.0 / 3.0 / 3.1) sowie CSV-Import.
 *
 * Liest den HEADER, das TEXT-Segment inklusive Supplemental-TEXT, das
 * DATA-Segment in allen Standard-Datentypen (I/F/D/A) und beide Byte-Ordnungen,
 * linearisiert geraeteseitig logarithmierte Kanaele ($PnE) und extrahiert die
 * Spillover-Matrix. Ergebnis ist immer dieselbe Sample-Struktur -- egal ob die
 * Quelle eine FCS-Datei oder eine CSV-Ereignistabelle war.
 */

import { uid } from './store.js';

const DEC = new TextDecoder('latin1');

/* ------------------------------------------------------------------ */
/* TEXT-Segment                                                        */
/* ------------------------------------------------------------------ */

function parseTextSegment(bytes, start, end) {
  if (end <= start) return {};
  const raw = DEC.decode(bytes.subarray(start, end + 1));
  const delim = raw[0];
  const body = raw.slice(1);

  // Doppeltes Trennzeichen steht fuer ein literales Trennzeichen im Wert.
  const SENTINEL = '\u0000ESCAPED\u0000';
  const tokens = body.split(delim + delim).join(SENTINEL).split(delim);

  const kv = {};
  for (let i = 0; i + 1 < tokens.length; i += 2) {
    const key = tokens[i].split(SENTINEL).join(delim).trim();
    const val = tokens[i + 1].split(SENTINEL).join(delim).trim();
    if (key) kv[key.toUpperCase()] = val;
  }
  return kv;
}

function intAt(bytes, offset, length) {
  const s = DEC.decode(bytes.subarray(offset, offset + length)).trim();
  const n = parseInt(s, 10);
  return Number.isFinite(n) ? n : 0;
}

/* ------------------------------------------------------------------ */
/* Spillover                                                           */
/* ------------------------------------------------------------------ */

/**
 * Zerlegt $SPILLOVER / $SPILL: "n,name1,...,namen,v11,v12,...,vnn".
 * @returns {{channels:string[], matrix:Array<Float64Array>}|null}
 */
export function parseSpillover(str) {
  if (!str) return null;
  const parts = str.split(',').map((s) => s.trim()).filter((s) => s.length);
  if (parts.length < 2) return null;
  const n = parseInt(parts[0], 10);
  if (!Number.isFinite(n) || n <= 0) return null;
  if (parts.length < 1 + n + n * n) return null;

  const channels = parts.slice(1, 1 + n);
  const values = parts.slice(1 + n, 1 + n + n * n).map(Number);
  const matrix = [];
  for (let i = 0; i < n; i++) {
    const row = new Float64Array(n);
    for (let j = 0; j < n; j++) row[j] = values[i * n + j];
    matrix.push(row);
  }
  return { channels, matrix };
}

/* ------------------------------------------------------------------ */
/* Parameter-Metadaten                                                 */
/* ------------------------------------------------------------------ */

function readParameters(text, par) {
  const params = [];
  for (let i = 1; i <= par; i++) {
    const name = text[`$P${i}N`] || `P${i}`;
    const stain = text[`$P${i}S`] || '';
    const bits = parseInt(text[`$P${i}B`], 10) || 32;
    const range = parseFloat(text[`$P${i}R`]) || 262144;
    const gain = parseFloat(text[`$P${i}G`]) || 1;
    const eRaw = (text[`$P${i}E`] || '0,0').split(',').map(Number);
    const decades = Number.isFinite(eRaw[0]) ? eRaw[0] : 0;
    let offset = Number.isFinite(eRaw[1]) ? eRaw[1] : 0;
    // Nach FCS-Standard ist "f2 = 0" bei logarithmischer Skalierung als 1 zu lesen.
    if (decades > 0 && offset === 0) offset = 1;

    params.push({
      index: i - 1,
      name,
      stain,
      label: stain ? `${name} (${stain})` : name,
      bits,
      range,
      gain,
      logDecades: decades,
      logOffset: offset,
      isScatter: /^(fsc|ssc)/i.test(name),
      isTime: /^time$/i.test(name),
      display: text[`P${i}DISPLAY`] || '',
    });
  }
  return params;
}

/* ------------------------------------------------------------------ */
/* DATA-Segment                                                        */
/* ------------------------------------------------------------------ */

function bitMaskFor(range, bits) {
  // Uebliche Praxis: auf die tatsaechlich genutzte Bitbreite maskieren,
  // damit Geraete-Statusbits nicht als Messwert erscheinen.
  if (!Number.isFinite(range) || range <= 0) return null;
  const needed = Math.ceil(Math.log2(range));
  if (needed >= bits || needed <= 0) return null;
  return Math.pow(2, needed) - 1;
}

function readIntegerData(view, littleEndian, params, nEvents, byteOffset) {
  const nPar = params.length;
  const out = new Float32Array(nEvents * nPar);
  const widths = params.map((p) => p.bits >> 3);
  const masks = params.map((p) => bitMaskFor(p.range, p.bits));
  const stride = widths.reduce((a, b) => a + b, 0);

  for (let e = 0; e < nEvents; e++) {
    let off = byteOffset + e * stride;
    for (let p = 0; p < nPar; p++) {
      const w = widths[p];
      let v;
      if (w === 1) v = view.getUint8(off);
      else if (w === 2) v = view.getUint16(off, littleEndian);
      else if (w === 4) v = view.getUint32(off, littleEndian);
      else if (w === 8) v = Number(view.getBigUint64(off, littleEndian));
      else if (w === 3) {
        const b0 = view.getUint8(off);
        const b1 = view.getUint8(off + 1);
        const b2 = view.getUint8(off + 2);
        v = littleEndian ? b0 | (b1 << 8) | (b2 << 16) : b2 | (b1 << 8) | (b0 << 16);
      } else {
        v = 0;
      }
      const mask = masks[p];
      if (mask !== null) v &= mask;
      out[e * nPar + p] = v;
      off += w;
    }
  }
  return out;
}

function readFloatData(view, littleEndian, nPar, nEvents, byteOffset, isDouble) {
  const out = new Float32Array(nEvents * nPar);
  const w = isDouble ? 8 : 4;
  for (let i = 0; i < nEvents * nPar; i++) {
    const off = byteOffset + i * w;
    out[i] = isDouble ? view.getFloat64(off, littleEndian) : view.getFloat32(off, littleEndian);
  }
  return out;
}

function readAsciiData(bytes, params, nEvents, start, end) {
  const nPar = params.length;
  const out = new Float32Array(nEvents * nPar);
  const text = DEC.decode(bytes.subarray(start, end + 1));
  const tokens = text.split(/[\s,]+/).filter((t) => t.length);
  for (let i = 0; i < Math.min(tokens.length, out.length); i++) out[i] = parseFloat(tokens[i]) || 0;
  return out;
}

/**
 * Rechnet geraeteseitig logarithmierte Kanaele ($PnE) auf lineare Werte zurueck
 * und beruecksichtigt die Verstaerkung ($PnG). Ohne diesen Schritt sind
 * Kompensation und Logicle-Transformation falsch.
 */
function linearize(data, params, nEvents) {
  const nPar = params.length;
  for (let p = 0; p < nPar; p++) {
    const { logDecades, logOffset, gain, range } = params[p];
    if (logDecades > 0) {
      for (let e = 0; e < nEvents; e++) {
        const idx = e * nPar + p;
        data[idx] = Math.pow(10, (logDecades * data[idx]) / range) * logOffset;
      }
    } else if (gain && gain !== 1) {
      for (let e = 0; e < nEvents; e++) data[e * nPar + p] /= gain;
    }
  }
  return data;
}

/* ------------------------------------------------------------------ */
/* Hauptfunktion                                                       */
/* ------------------------------------------------------------------ */

/**
 * @param {ArrayBuffer} buffer Inhalt der FCS-Datei
 * @param {string} fileName
 * @returns {Sample}
 */
export function parseFCS(buffer, fileName = 'unbenannt.fcs') {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);

  const version = DEC.decode(bytes.subarray(0, 6)).trim();
  if (!/^FCS[23]\.\d/.test(version)) {
    throw new Error(`Kein gültiges FCS-Format (Kennung: "${version}")`);
  }

  let textStart = intAt(bytes, 10, 8);
  let textEnd = intAt(bytes, 18, 8);
  let dataStart = intAt(bytes, 26, 8);
  let dataEnd = intAt(bytes, 34, 8);

  let text = parseTextSegment(bytes, textStart, textEnd);

  // FCS 3.x: Bei Dateien > 99.999.999 Byte stehen die echten Offsets im TEXT.
  const bd = parseInt(text.$BEGINDATA, 10);
  const ed = parseInt(text.$ENDDATA, 10);
  if (Number.isFinite(bd) && bd > 0) dataStart = bd;
  if (Number.isFinite(ed) && ed > 0) dataEnd = ed;

  // Supplemental TEXT anhaengen (selten, aber Teil des Standards).
  const bst = parseInt(text.$BEGINSTEXT, 10);
  const est = parseInt(text.$ENDSTEXT, 10);
  if (Number.isFinite(bst) && bst > 0 && Number.isFinite(est) && est > bst) {
    text = { ...text, ...parseTextSegment(bytes, bst, est) };
  }

  const par = parseInt(text.$PAR, 10) || 0;
  let tot = parseInt(text.$TOT, 10) || 0;
  const mode = (text.$MODE || 'L').toUpperCase();
  const dataType = (text.$DATATYPE || 'I').toUpperCase();
  const byteOrd = (text.$BYTEORD || '1,2,3,4').trim();
  const littleEndian = byteOrd.startsWith('1');

  if (mode !== 'L') {
    throw new Error(`FCS-Modus "${mode}" wird nicht unterstützt (nur Listenmodus "L").`);
  }
  if (!par) throw new Error('FCS-Schluessel $PAR fehlt.');

  const params = readParameters(text, par);

  // Plausibilisierung: passt $TOT zur tatsaechlichen Segmentgroesse?
  const bytesPerEvent =
    dataType === 'I'
      ? params.reduce((a, p) => a + (p.bits >> 3), 0)
      : dataType === 'D'
        ? par * 8
        : par * 4;
  const available = dataEnd - dataStart + 1;
  if (dataType !== 'A' && bytesPerEvent > 0) {
    const fits = Math.floor(available / bytesPerEvent);
    if (fits > 0 && (!tot || tot > fits)) tot = fits;
  }
  if (!tot) throw new Error('Ereignisanzahl ($TOT) konnte nicht bestimmt werden.');

  let data;
  if (dataType === 'I') {
    data = readIntegerData(view, littleEndian, params, tot, dataStart);
  } else if (dataType === 'F') {
    data = readFloatData(view, littleEndian, par, tot, dataStart, false);
  } else if (dataType === 'D') {
    data = readFloatData(view, littleEndian, par, tot, dataStart, true);
  } else if (dataType === 'A') {
    data = readAsciiData(bytes, params, tot, dataStart, dataEnd);
  } else {
    throw new Error(`Datentyp "${dataType}" wird nicht unterstützt.`);
  }

  linearize(data, params, tot);

  const spill = parseSpillover(text.$SPILLOVER || text.$SPILL || text.SPILL || '');

  return buildSample({
    fileName,
    name: text.$FIL || text.GUID || fileName.replace(/\.fcs$/i, ''),
    params,
    data,
    nEvents: tot,
    text,
    spill,
    meta: {
      version,
      cytometer: text.$CYT || 'unbekannt',
      cytometerSN: text.$CYTSN || '',
      date: text.$DATE || '',
      btim: text.$BTIM || '',
      etim: text.$ETIM || '',
      operator: text.$OP || '',
      institution: text.$INST || '',
      experiment: text.$EXP || '',
      sampleId: text.$SMNO || '',
      tube: text.TUBENAME || text.$SRC || '',
      volume: text.$VOL || '',
      timestep: parseFloat(text.$TIMESTEP) || 0,
      software: text.CREATOR || text.$SYS || '',
      threshold: text.$TR || '',
      nextData: parseInt(text.$NEXTDATA, 10) || 0,
    },
  });
}

/** Baut die kanonische Sample-Struktur (auch vom CSV-Import genutzt). */
function buildSample({ fileName, name, params, data, nEvents, text = {}, spill = null, meta = {} }) {
  return {
    id: uid('smp'),
    name,
    fileName,
    params,
    /** Rohdaten, linear, Layout: event-major (event * nParams + param) */
    data,
    nEvents,
    nParams: params.length,
    text,
    meta,
    /** Kompensationszustand, siehe compensation.js */
    comp: {
      channels: spill ? spill.channels : [],
      matrix: spill ? spill.matrix : null,
      source: spill ? 'fcs' : 'keine',
      enabled: !!spill,
      tweak: null,
    },
    /** Cache fuer kompensierte Daten -- lazy, siehe compensation.js */
    compData: null,
    /** Transformationsparameter je Kanal, siehe transform.js */
    transforms: {},
    qc: null,
  };
}

export { buildSample };

/* ------------------------------------------------------------------ */
/* CSV-Import                                                          */
/* ------------------------------------------------------------------ */

/**
 * Importiert eine exportierte Ereignistabelle (Kopfzeile = Kanalnamen).
 * Unterstuetzt Komma, Semikolon und Tabulator als Trennzeichen.
 */
export function parseCSV(textContent, fileName = 'tabelle.csv') {
  const lines = textContent.split(/\r?\n/).filter((l) => l.trim().length);
  if (lines.length < 2) throw new Error('CSV enthält keine Datenzeilen.');

  const delim = [',', ';', '\t']
    .map((d) => ({ d, n: lines[0].split(d).length }))
    .sort((a, b) => b.n - a.n)[0].d;

  const header = lines[0].split(delim).map((h) => h.trim().replace(/^"|"$/g, ''));
  const nPar = header.length;
  const nEvents = lines.length - 1;
  const data = new Float32Array(nEvents * nPar);

  for (let e = 0; e < nEvents; e++) {
    const cells = lines[e + 1].split(delim);
    for (let p = 0; p < nPar; p++) {
      const v = parseFloat(String(cells[p] ?? '').replace(',', '.'));
      data[e * nPar + p] = Number.isFinite(v) ? v : 0;
    }
  }

  const params = header.map((h, i) => {
    // "CD3 FITC-A" oder "FITC-A :: CD3" in Kanal + Marker zerlegen
    const m = h.match(/^(.*?)\s*(?:::|\|)\s*(.*)$/);
    const nameRaw = m ? m[1] : h;
    const stain = m ? m[2] : '';
    let max = 0;
    for (let e = 0; e < nEvents; e++) max = Math.max(max, data[e * nPar + i]);
    return {
      index: i,
      name: nameRaw,
      stain,
      label: stain ? `${nameRaw} (${stain})` : nameRaw,
      bits: 32,
      range: Math.max(max, 1024),
      gain: 1,
      logDecades: 0,
      logOffset: 0,
      isScatter: /^(fsc|ssc)/i.test(nameRaw),
      isTime: /^time$/i.test(nameRaw),
      display: '',
    };
  });

  return buildSample({
    fileName,
    name: fileName.replace(/\.(csv|tsv|txt)$/i, ''),
    params,
    data,
    nEvents,
    meta: { version: 'CSV', cytometer: 'CSV-Import', date: '' },
  });
}

/** Erkennt anhand der Signatur, ob FCS oder CSV vorliegt. */
export function parseAny(buffer, fileName) {
  const head = DEC.decode(new Uint8Array(buffer.slice(0, 6)));
  if (/^FCS[23]\.\d/.test(head)) return parseFCS(buffer, fileName);
  return parseCSV(new TextDecoder('utf-8').decode(buffer), fileName);
}
