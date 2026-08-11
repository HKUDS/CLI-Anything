/**
 * Rauchtest im echten Browser.
 *
 * Oeffnet die gebaute Einzeldatei, laedt eine synthetische FCS-Datei ueber den
 * regulaeren Dateidialog und prueft, dass die gesamte Kette in der Oberflaeche
 * ankommt: Gates, Plots, Panelauswertung, Statistik, Qualitaet und Befund.
 * Konsolenfehler fuehren zum Fehlschlag.
 *
 * Aufruf:  node test/browser-smoke.mjs [--screenshots]
 */

import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { writeFile, mkdir } from 'node:fs/promises';

import { makeTBNKSample } from './helpers.js';

const wurzel = dirname(dirname(fileURLToPath(import.meta.url)));
const screenshots = process.argv.includes('--screenshots');
const ausgabe = join(wurzel, 'dist', 'screenshots');

let fehlgeschlagen = 0;
function pruefe(bedingung, beschreibung, zusatz = '') {
  if (bedingung) {
    console.log(`  ok    ${beschreibung}`);
  } else {
    console.log(`  FEHLT ${beschreibung}${zusatz ? ' — ' + zusatz : ''}`);
    fehlgeschlagen++;
  }
}

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const seite = await browser.newPage({ viewport: { width: 1600, height: 1000 } });

const konsolenfehler = [];
seite.on('console', (m) => {
  if (m.type() === 'error') konsolenfehler.push(m.text());
});
seite.on('pageerror', (e) => konsolenfehler.push(`pageerror: ${e.message}`));

console.log('\nRauchtest FlowCyto');
console.log('==================\n');

await seite.goto(`file://${join(wurzel, 'dist', 'flowcyto.html')}`);
await seite.waitForSelector('#app');
console.log('Anwendung geladen.\n');

/* --- Datei ueber den Dateidialog einspeisen --- */
const { buffer, soll } = makeTBNKSample(40000, 21);
await seite.setInputFiles('#dateiEingabe', {
  name: 'tbnk-test.fcs',
  mimeType: 'application/octet-stream',
  buffer: Buffer.from(buffer),
});
await seite.waitForTimeout(2500);

console.log('Datei laden:');
const statusText = await seite.textContent('#statusZeile');
pruefe(/geladen|Vorschlag/.test(statusText), 'Statuszeile meldet Erfolg', statusText);
pruefe((await seite.locator('#probenliste .eintrag').count()) === 1, 'Probe erscheint in der Liste');
pruefe((await seite.locator('#gatebaum .knoten').count()) >= 2, 'Vorgating hat Gates erzeugt');
pruefe((await seite.locator('.kachel').count()) >= 2, 'Plots wurden angelegt');

// Canvas darf nicht leer sein
const pixelSumme = await seite.evaluate(() => {
  const c = document.querySelector('.kachel canvas');
  const ctx = c.getContext('2d');
  const d = ctx.getImageData(0, 0, c.width, c.height).data;
  const farben = new Set();
  for (let i = 0; i < d.length; i += 4 * 97) farben.add(`${d[i]},${d[i + 1]},${d[i + 2]}`);
  return farben.size;
});
pruefe(pixelSumme > 8, 'Plot enthält gezeichnete Daten', `${pixelSumme} verschiedene Farben`);

if (screenshots) {
  await mkdir(ausgabe, { recursive: true });
  await seite.screenshot({ path: join(ausgabe, '1-plots.png') });
}

/* --- Panel anwenden --- */
console.log('\nPanel anwenden:');
const panelWert = await seite.inputValue('#panelAuswahl');
pruefe(panelWert === 'tbnk', 'TBNK-Panel wurde automatisch vorgeschlagen', panelWert);
await seite.selectOption('#panelAuswahl', 'tbnk');
await seite.click('#btnPanelAnwenden');
await seite.waitForTimeout(2500);

const panelStatus = await seite.textContent('#statusZeile');
pruefe(/vollständig angewandt/.test(panelStatus), 'Panel vollständig angewandt', panelStatus);
pruefe((await seite.locator('#gatebaum .knoten').count()) >= 10, 'Panel-Gates angelegt');

if (screenshots) await seite.screenshot({ path: join(ausgabe, '2-panel.png') });

/* --- Statistik --- */
console.log('\nStatistik:');
await seite.click('#reiterleiste button[data-reiter="Statistik"]');
await seite.waitForTimeout(900);

const kennzahlen = await seite.evaluate(() => {
  const zeilen = [...document.querySelectorAll('#inhaltStatistik table tbody tr')];
  const out = {};
  for (const tr of zeilen) {
    const zellen = [...tr.children].map((c) => c.textContent.trim());
    if (zellen.length >= 2) out[zellen[0]] = zellen[1];
  }
  return out;
});
const lese = (name) => parseFloat(String(kennzahlen[name] || '').replace(',', '.'));

pruefe(Math.abs(lese('T-Zellen') - soll.tPct) < 6, `T-Zellen ${kennzahlen['T-Zellen']} (Soll ${soll.tPct.toFixed(1)} %)`);
pruefe(Math.abs(lese('B-Zellen') - soll.bPct) < 5, `B-Zellen ${kennzahlen['B-Zellen']} (Soll ${soll.bPct.toFixed(1)} %)`);
pruefe(Math.abs(lese('NK-Zellen') - soll.nkPct) < 5, `NK-Zellen ${kennzahlen['NK-Zellen']} (Soll ${soll.nkPct.toFixed(1)} %)`);
pruefe(Math.abs(lese('CD4/CD8-Quotient') - soll.cd4cd8) < 0.5, `CD4/CD8 ${kennzahlen['CD4/CD8-Quotient']} (Soll ${soll.cd4cd8.toFixed(2)})`);
pruefe(Math.abs(lese('Summe T + B + NK') - 100) < 6, `Plausibilität: Summe ${kennzahlen['Summe T + B + NK']}`);

if (screenshots) await seite.screenshot({ path: join(ausgabe, '3-statistik.png') });

/* --- Qualitaetskontrolle --- */
console.log('\nQualitätskontrolle:');
await seite.click('#reiterleiste button[data-reiter="QC"]');
await seite.waitForTimeout(700);
pruefe((await seite.locator('#inhaltQC .karte').count()) >= 6, 'Alle Prüfungen dargestellt');
pruefe((await seite.locator('#inhaltQC .marke').count()) >= 6, 'Bewertungen vorhanden');

/* --- Clusteranalyse --- */
console.log('\nClusteranalyse:');
await seite.click('#reiterleiste button[data-reiter="Cluster"]');
await seite.waitForTimeout(400);
await seite.selectOption('#clusterVerfahren', 'flowsom');
await seite.fill('#clusterAnzahl', '8');
await seite.click('#btnClusterStart');
await seite.waitForTimeout(9000);
const clusterStatus = await seite.textContent('#statusZeile');
pruefe(/abgeschlossen/.test(clusterStatus), 'FlowSOM berechnet', clusterStatus);
pruefe((await seite.locator('#clusterAusgabe table tbody tr').count()) >= 4, 'Clustertabelle gefüllt');

if (screenshots) await seite.screenshot({ path: join(ausgabe, '4-cluster.png') });

/* --- Befund --- */
console.log('\nBefund:');
await seite.click('#reiterleiste button[data-reiter="Befund"]');
await seite.waitForTimeout(1200);

const befundText = await seite.textContent('#befundVorschau');
pruefe(befundText.includes('DURCHFLUSSZYTOMETRISCHER BEFUND'), 'Befundkopf vorhanden');
pruefe(befundText.includes('GATING-STRATEGIE'), 'Gating-Strategie dokumentiert');
pruefe(befundText.includes('QUALITÄTSKONTROLLE'), 'Qualitätskontrolle enthalten');
pruefe(befundText.includes('T-Zellen'), 'Kennzahlen enthalten');
pruefe(/In-vitro-Diagnostikum/.test(befundText), 'Hinweis zur Zweckbestimmung enthalten');

// Freigabe muss ohne Befunder gesperrt sein
const freigabeGesperrt = await seite.locator('#inhaltBefund button.primary').isDisabled();
pruefe(freigabeGesperrt, 'Freigabe ohne Befunder gesperrt');

// Befunder eintragen -> Freigabe moeglich
await seite.fill('#inhaltBefund input[type=text]', 'Dr. Test');
await seite.waitForTimeout(600);
const freigabeFrei = !(await seite.locator('#inhaltBefund button.primary').isDisabled());
pruefe(freigabeFrei, 'Freigabe nach Eintrag des Befunders möglich');

if (screenshots) await seite.screenshot({ path: join(ausgabe, '5-befund.png') });

/* --- Patientendaten wirken auf die Referenzbewertung --- */
console.log('\nAltersabhängige Referenzbereiche:');
const vorher = await seite.evaluate(() => {
  const zeilen = [...document.querySelectorAll('#inhaltStatistik table tbody tr')];
  const t = zeilen.find((tr) => tr.children[0]?.textContent.trim() === 'B-Zellen');
  return t ? t.children[3].textContent.trim() : '';
});
await seite.fill('#patientenformular input[type=number]', '2');
await seite.waitForTimeout(700);
await seite.click('#reiterleiste button[data-reiter="Statistik"]');
await seite.waitForTimeout(700);
const nachher = await seite.evaluate(() => {
  const zeilen = [...document.querySelectorAll('#inhaltStatistik table tbody tr')];
  const t = zeilen.find((tr) => tr.children[0]?.textContent.trim() === 'B-Zellen');
  return t ? t.children[3].textContent.trim() : '';
});
pruefe(vorher !== nachher, 'Altersänderung verändert den Referenzbereich', `${vorher} → ${nachher}`);

/* --- Konsolenfehler --- */
console.log('\nKonsole:');
pruefe(konsolenfehler.length === 0, 'Keine JavaScript-Fehler', konsolenfehler.slice(0, 3).join(' | '));

await browser.close();

console.log(`\n${fehlgeschlagen === 0 ? 'Alle Prüfungen bestanden.' : `${fehlgeschlagen} Prüfung(en) fehlgeschlagen.`}\n`);
process.exit(fehlgeschlagen === 0 ? 0 : 1);
