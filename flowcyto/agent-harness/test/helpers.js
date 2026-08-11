/**
 * Testhilfen: erzeugt synthetische FCS-Dateien mit bekannter Zusammensetzung,
 * damit sich Parser, Transformation, Gating und Auswertung gegen erwartete
 * Sollwerte pruefen lassen.
 */

/** Deterministischer Zufallsgenerator. */
export function rng(seed = 1) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Standardnormalverteilte Zufallszahl (Box-Muller). */
export function gauss(rand) {
  let u = 0;
  let v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

/**
 * Schreibt eine FCS-3.1-Datei.
 * @param {string[]} channels Kanalnamen ($PnN)
 * @param {string[]} stains   Faerbungen ($PnS)
 * @param {Float32Array} data event-major
 * @param {number} nEvents
 * @param {object} extraText zusaetzliche TEXT-Schluessel
 * @param {'F'|'I'} datatype
 */
export function writeFCS(channels, stains, data, nEvents, extraText = {}, datatype = 'F') {
  const DELIM = '|';
  const nPar = channels.length;
  const range = 262144;

  const kv = {
    $BEGINANALYSIS: '0',
    $ENDANALYSIS: '0',
    $BEGINSTEXT: '0',
    $ENDSTEXT: '0',
    $BYTEORD: '1,2,3,4',
    $DATATYPE: datatype,
    $MODE: 'L',
    $NEXTDATA: '0',
    $PAR: String(nPar),
    $TOT: String(nEvents),
    $CYT: 'Testzytometer',
    $DATE: '10-AUG-2026',
    $BTIM: '09:00:00',
    $ETIM: '09:04:30',
  };
  for (let i = 0; i < nPar; i++) {
    kv[`$P${i + 1}N`] = channels[i];
    kv[`$P${i + 1}S`] = stains[i] || '';
    kv[`$P${i + 1}B`] = '32';
    kv[`$P${i + 1}E`] = '0,0';
    kv[`$P${i + 1}R`] = String(range);
    kv[`$P${i + 1}G`] = '1';
  }
  // Zusatzschluessel zuletzt, damit Tests einzelne Parameterangaben
  // (z. B. $P1E fuer logarithmische Aufzeichnung) gezielt ueberschreiben koennen.
  Object.assign(kv, extraText);

  const bytesPerEvent = nPar * 4;
  const dataLength = nEvents * bytesPerEvent;
  const textStart = 256;

  // TEXT zweimal aufbauen: die Offsets haengen von seiner eigenen Laenge ab.
  const buildText = (dataStart, dataEnd) => {
    const all = { ...kv, $BEGINDATA: String(dataStart), $ENDDATA: String(dataEnd) };
    let s = DELIM;
    for (const [k, v] of Object.entries(all)) s += `${k}${DELIM}${v}${DELIM}`;
    return s;
  };
  let text = buildText(0, 0);
  let dataStart = textStart + text.length;
  text = buildText(dataStart, dataStart + dataLength - 1);
  // Laengenaenderung kann den Offset verschieben -- bis zur Stabilitaet wiederholen
  for (let i = 0; i < 5; i++) {
    const ds = textStart + text.length;
    const next = buildText(ds, ds + dataLength - 1);
    if (next.length === text.length) {
      text = next;
      dataStart = ds;
      break;
    }
    text = next;
    dataStart = ds;
  }
  const textEnd = textStart + text.length - 1;
  const dataEnd = dataStart + dataLength - 1;

  const total = dataEnd + 1;
  const buf = new ArrayBuffer(total);
  const bytes = new Uint8Array(buf);
  const view = new DataView(buf);

  const put = (str, off) => {
    for (let i = 0; i < str.length; i++) bytes[off + i] = str.charCodeAt(i);
  };
  const pad = (n) => String(n).padStart(8, ' ');

  put('FCS3.1', 0);
  put('    ', 6);
  put(pad(textStart), 10);
  put(pad(textEnd), 18);
  put(pad(dataStart), 26);
  put(pad(dataEnd), 34);
  put(pad(0), 42);
  put(pad(0), 50);
  for (let i = 58; i < textStart; i++) bytes[i] = 32;
  put(text, textStart);

  for (let i = 0; i < nEvents * nPar; i++) {
    const off = dataStart + i * 4;
    if (datatype === 'F') view.setFloat32(off, data[i], true);
    else view.setUint32(off, Math.max(0, Math.min(range, Math.round(data[i]))), true);
  }
  return buf;
}

/**
 * Erzeugt eine realitaetsnahe TBNK-Probe mit bekannter Zusammensetzung.
 * Rueckgabe enthaelt die Sollwerte, gegen die die Auswertung geprueft wird.
 */
export function makeTBNKSample(nEvents = 30000, seed = 11) {
  const rand = rng(seed);
  const channels = ['FSC-A', 'FSC-H', 'SSC-A', 'Time', 'FITC-A', 'PE-A', 'PerCP-A', 'APC-A', 'PE-Cy7-A', 'APC-Cy7-A'];
  const stains = ['', '', '', '', 'CD3', 'CD4', 'CD8', 'CD19', 'CD56', 'CD45'];
  const nPar = channels.length;
  const data = new Float32Array(nEvents * nPar);

  // Sollzusammensetzung der Lymphozyten
  const anteile = { tzell: 0.72, bzell: 0.12, nk: 0.16 };
  const cd4Anteil = 0.62;

  const zusammensetzung = { lymphozyten: 0.45, monozyten: 0.12, granulozyten: 0.35, debris: 0.08 };

  // Positiv-/Negativlagen in linearen Einheiten
  const NEG = () => Math.max(-800, 120 + gauss(rand) * 260);
  const POS = (m = 22000) => m * Math.exp(gauss(rand) * 0.28);
  const DIM = () => 2200 * Math.exp(gauss(rand) * 0.35);

  let counts = { lymph: 0, t: 0, b: 0, nk: 0, cd4: 0, cd8: 0 };

  for (let e = 0; e < nEvents; e++) {
    const base = e * nPar;
    const u = rand();
    let fsc;
    let ssc;
    let cd45;
    let cd3 = NEG();
    let cd4 = NEG();
    let cd8 = NEG();
    let cd19 = NEG();
    let cd56 = NEG();

    if (u < zusammensetzung.debris) {
      fsc = 12000 * Math.exp(gauss(rand) * 0.5);
      ssc = 9000 * Math.exp(gauss(rand) * 0.6);
      cd45 = NEG();
    } else if (u < zusammensetzung.debris + zusammensetzung.lymphozyten) {
      fsc = 62000 + gauss(rand) * 6000;
      ssc = 21000 + gauss(rand) * 4200;
      cd45 = POS(60000);
      counts.lymph++;
      const v = rand();
      if (v < anteile.tzell) {
        cd3 = POS(30000);
        counts.t++;
        if (rand() < cd4Anteil) {
          cd4 = POS(26000);
          counts.cd4++;
        } else {
          cd8 = POS(28000);
          counts.cd8++;
        }
      } else if (v < anteile.tzell + anteile.bzell) {
        cd19 = POS(24000);
        counts.b++;
      } else {
        cd56 = POS(18000);
        counts.nk++;
      }
    } else if (u < zusammensetzung.debris + zusammensetzung.lymphozyten + zusammensetzung.monozyten) {
      fsc = 98000 + gauss(rand) * 11000;
      ssc = 47000 + gauss(rand) * 8000;
      cd45 = POS(48000);
      cd4 = DIM();
    } else {
      fsc = 105000 + gauss(rand) * 12000;
      ssc = 105000 + gauss(rand) * 16000;
      cd45 = POS(26000);
    }

    const fscH = fsc * (0.94 + gauss(rand) * 0.02);
    data[base + 0] = Math.max(0, fsc);
    data[base + 1] = Math.max(0, rand() < 0.03 ? fscH * 0.62 : fscH); // 3 % Dubletten
    data[base + 2] = Math.max(0, ssc);
    data[base + 3] = (e / nEvents) * 270; // gleichmaessige Ereignisrate
    data[base + 4] = cd3;
    data[base + 5] = cd4;
    data[base + 6] = cd8;
    data[base + 7] = cd19;
    data[base + 8] = cd56;
    data[base + 9] = cd45;
  }

  const spill = [
    '5,FITC-A,PE-A,PerCP-A,APC-A,PE-Cy7-A',
    '1,0.14,0.02,0,0',
    '0.03,1,0.09,0.01,0.04',
    '0,0.05,1,0.06,0.11',
    '0,0.01,0.02,1,0.13',
    '0,0.02,0.03,0.07,1',
  ].join(',');

  const buffer = writeFCS(channels, stains, data, nEvents, { $SPILLOVER: spill, $FIL: 'TBNK-Test' });

  return {
    buffer,
    soll: {
      nEvents,
      lymphozyten: counts.lymph,
      tPct: (100 * counts.t) / counts.lymph,
      bPct: (100 * counts.b) / counts.lymph,
      nkPct: (100 * counts.nk) / counts.lymph,
      cd4Pct: (100 * counts.cd4) / counts.lymph,
      cd8Pct: (100 * counts.cd8) / counts.lymph,
      cd4cd8: counts.cd4 / counts.cd8,
    },
    channels,
    stains,
  };
}
