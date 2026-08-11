/**
 * Datenintegritäts-Prüfung im echten Seitenkontext.
 *
 * Lädt die Einzeldatei in Chromium und prüft die Querverweise, die das
 * Nachschlagewerk zusammenhalten: Häufigkeiten → Quellen, Marker → Lexikon,
 * Baum-Kanten → Knoten/Blätter, Panel-Abdeckungen → Entitäten, Suchindex →
 * gültige Routen. Bricht mit Exit 1 ab, wenn ein Verweis ins Leere geht.
 */
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const wurzel = dirname(dirname(fileURLToPath(import.meta.url)));
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const seite = await browser.newPage();
const konsole = [];
seite.on('pageerror', (e) => konsole.push(e.message));

await seite.goto(`file://${join(wurzel, 'haemflow.html')}`);
await seite.waitForTimeout(700);

const bericht = await seite.evaluate(() => {
  const fehler = [];
  const ok = [];

  /* FREQ: Entitäten existieren, Markerschlüssel lösen auf, Quellen gültig */
  let nFreq = 0;
  Object.entries(FREQ).forEach(([entId, tab]) => {
    if (!ENT.some((e) => e.id === entId)) fehler.push(`FREQ: Entität "${entId}" existiert nicht`);
    Object.entries(tab).forEach(([key, f]) => {
      nFreq++;
      if (LEX_INDEX[key] === undefined) fehler.push(`FREQ ${entId}.${key}: kein Lexikon-Eintrag`);
      if (!(Number.isInteger(f[1]) && f[1] >= 0 && f[1] < LIT.length)) {
        fehler.push(`FREQ ${entId}.${key}: Quellenindex ${f[1]} außerhalb der Literaturliste (0–${LIT.length - 1})`);
      }
    });
  });
  ok.push(`${nFreq} Häufigkeitsangaben geprüft (Marker + Quelle)`);

  /* ENT_EXTRA / CONFIRM decken alle Entitäten sinnvoll ab */
  ENT.forEach((e) => {
    if (!CONFIRM[e.id]) fehler.push(`CONFIRM fehlt für Entität "${e.id}"`);
  });
  ok.push(`${ENT.length} Entitäten mit Bestätigungsdiagnostik`);

  /* Entitäts-Marker lösen im Lexikon auf (Chips wären sonst tot) */
  let tot = 0;
  ENT.forEach((e) => {
    [...(e.pos || []), ...(e.neg || []), ...(e.abr || [])].forEach((m) => {
      if (lexIndex(m.name) < 0) { tot++; fehler.push(`Marker ohne Lexikon-Eintrag: ${e.id} → "${m.name}"`); }
    });
  });
  ok.push('Alle Entitäts-Markerchips lösen im Lexikon auf');

  /* Vergleichs- und Zellmatrix-Spalten */
  Object.entries(MATRIX).forEach(([gid, cols]) => cols.forEach((c) => {
    if (lexIndex(c) < 0) fehler.push(`MATRIX ${gid}: Spalte "${c}" ohne Lexikon-Eintrag`);
  }));
  [CELLS_LYMPH, CELLS_MYE].forEach((def, di) => def.cols.forEach((c) => {
    if (lexIndex(c) < 0) fehler.push(`Zellmatrix ${di ? 'myeloisch' : 'lymphatisch'}: Spalte "${c}" ohne Lexikon-Eintrag`);
  }));
  ok.push('Matrix-Spalten vollständig verlinkbar');

  /* Bäume: jede Kante endet in Knoten oder Blatt; jedes Blatt-Entity existiert */
  TREES.forEach((t) => {
    if (!t.nodes[t.start]) fehler.push(`Baum ${t.id}: Startknoten fehlt`);
    Object.entries(t.nodes).forEach(([nid, n]) => n.opts.forEach(([label, ziel]) => {
      if (!t.nodes[ziel] && !t.leaves[ziel]) fehler.push(`Baum ${t.id}/${nid}: Ziel "${ziel}" existiert nicht`);
    }));
    Object.entries(t.leaves).forEach(([lid, leaf]) => {
      (leaf.ents || []).forEach((id) => {
        if (!ENT.some((e) => e.id === id)) fehler.push(`Baum ${t.id}/${lid}: Entität "${id}" existiert nicht`);
      });
      if (leaf.jump && !validRoute(leaf.jump)) fehler.push(`Baum ${t.id}/${lid}: Route "${leaf.jump}" ungültig`);
    });
    /* Erreichbarkeit: alle Blätter von der Wurzel erreichbar */
    const erreichbar = new Set();
    const stapel = [t.start];
    while (stapel.length) {
      const id = stapel.pop();
      if (erreichbar.has(id)) continue;
      erreichbar.add(id);
      const n = t.nodes[id];
      if (n) n.opts.forEach(([, ziel]) => stapel.push(ziel));
    }
    Object.keys(t.leaves).forEach((lid) => {
      if (!erreichbar.has(lid)) fehler.push(`Baum ${t.id}: Blatt "${lid}" unerreichbar`);
    });
    Object.keys(t.nodes).forEach((nid) => {
      if (!erreichbar.has(nid)) fehler.push(`Baum ${t.id}: Knoten "${nid}" unerreichbar`);
    });
  });
  ok.push(`${TREES.length} Bäume: Kanten, Blätter und Erreichbarkeit geprüft`);

  /* Panels: covers + Quellen */
  PANELS.forEach((p) => {
    (p.covers || []).forEach((id) => {
      if (!ENT.some((e) => e.id === id)) fehler.push(`Panel ${p.abk}: covers "${id}" existiert nicht`);
    });
    if (p.src != null && !(p.src >= 0 && p.src < LIT.length)) fehler.push(`Panel ${p.abk}: Quellenindex ungültig`);
  });
  SOP.forEach((t) => {
    if (t.src != null && !(t.src >= 0 && t.src < LIT.length)) fehler.push(`SOP ${t.id}: Quellenindex ungültig`);
    t.rows.forEach((r) => { if (r.length !== 5) fehler.push(`SOP ${t.id}: Zeile mit ${r.length} statt 5 Spalten`); });
  });
  ok.push(`${PANELS.length} Panels + ${SOP.length} SOP-Tabellen geprüft`);

  /* Suchindex: jede Route gültig */
  SEARCH_INDEX.forEach((h) => {
    if (!validRoute(h.route)) fehler.push(`Suchindex: ungültige Route "${h.route}" (${h.title})`);
  });
  ok.push(`${SEARCH_INDEX.length} Suchindex-Einträge mit gültigen Routen`);

  /* LEX_INDEX-Duplikate: jede MARKERS-Zeile erreichbar */
  const erreichteZeilen = new Set(Object.values(LEX_INDEX));
  MARKERS.forEach((m, i) => {
    if (!erreichteZeilen.has(i)) fehler.push(`Lexikon-Zeile "${m[0]}" über keinen Schlüssel erreichbar`);
  });
  ok.push(`${MARKERS.length} Lexikon-Einträge erreichbar`);

  return { fehler, ok, zahlen: { ent: ENT.length, marker: MARKERS.length, lit: LIT.length, freq: nFreq } };
});

console.log('\nDatenintegrität HämFlow v10');
console.log('===========================\n');
for (const zeile of bericht.ok) console.log(`  ok    ${zeile}`);
if (bericht.fehler.length) {
  console.log('');
  for (const f of bericht.fehler) console.log(`  FEHLT ${f}`);
}
console.log(`\nBestand: ${bericht.zahlen.ent} Entitäten · ${bericht.zahlen.marker} Marker · ${bericht.zahlen.freq} Häufigkeiten · ${bericht.zahlen.lit} Quellen`);
if (konsole.length) console.log(`Konsolenfehler: ${konsole.join(' | ')}`);

await browser.close();
process.exit(bericht.fehler.length || konsole.length ? 1 : 0);
