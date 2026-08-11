/**
 * Rauchtest: die wichtigsten Nutzerpfade des Nachschlagewerks im echten Browser.
 * Aufruf: node test/smoke.mjs [--screenshots]
 */
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdir } from 'node:fs/promises';

const wurzel = dirname(dirname(fileURLToPath(import.meta.url)));
const screenshots = process.argv.includes('--screenshots');
const ablage = join(wurzel, 'test', 'screenshots');
if (screenshots) await mkdir(ablage, { recursive: true });

let fehlgeschlagen = 0;
const pruefe = (bedingung, text, zusatz = '') => {
  console.log(`  ${bedingung ? 'ok   ' : 'FEHLT'} ${text}${!bedingung && zusatz ? ' — ' + zusatz : ''}`);
  if (!bedingung) fehlgeschlagen++;
};

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const seite = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const konsole = [];
seite.on('pageerror', (e) => konsole.push('pageerror: ' + e.message));
seite.on('console', (m) => { if (m.type() === 'error') konsole.push(m.text()); });

const shot = async (name) => { if (screenshots) await seite.screenshot({ path: join(ablage, name + '.png') }); };

console.log('\nRauchtest HämFlow v10');
console.log('=====================\n');

await seite.goto(`file://${join(wurzel, 'haemflow.html')}`);
await seite.waitForSelector('#content .card');

/* --- Suche --- */
console.log('Globale Suche:');
await seite.click('#search');
await seite.fill('#search', 'CD200');
await seite.waitForTimeout(400);
const treffer = await seite.locator('#searchPanel .hit').count();
pruefe(treffer >= 2, `Suche „CD200" liefert Treffer (${treffer})`);
await seite.locator('#searchPanel .hit', { hasText: 'CD200' }).first().click();
await seite.waitForTimeout(400);
pruefe((await seite.locator('#content .title').first().textContent()).includes('CD200'), 'Treffer öffnet Marker-Detailkarte');

await seite.click('#search');
await seite.fill('#search', 'Hämatogon');
await seite.waitForTimeout(400);
const hgTreffer = await seite.locator('#searchPanel .hit').count();
pruefe(hgTreffer >= 2, `Suche „Hämatogon" findet Entität + Zellmatrix (${hgTreffer})`);
await seite.keyboard.press('Escape');

/* --- Marker-Detail + Backlinks --- */
console.log('\nMarker-Lexikon:');
await seite.evaluate(() => navigate('mkr:cd200'));
await seite.waitForTimeout(350);
const backlinks = await seite.locator('#content .bl').count();
pruefe(backlinks >= 4, `CD200-Detailkarte hat Entitäts-Backlinks (${backlinks})`);
const fqChips = await seite.locator('#content .bl .fq').count();
pruefe(fqChips >= 2, `Backlinks tragen Häufigkeiten (${fqChips})`);
await seite.locator('#content .bl').first().click();
await seite.waitForTimeout(350);
pruefe((await seite.locator('#content .ent-head').count()) === 1, 'Backlink öffnet Entitätskarte');
await shot('1-marker');

/* --- Entitätskarte --- */
console.log('\nEntitätskarte:');
await seite.evaluate(() => navigate('ent:cll'));
await seite.waitForTimeout(350);
const inhalt = await seite.locator('#content').textContent();
pruefe(inhalt.includes('~95'), 'Häufigkeits-Chips vorhanden');
pruefe(inhalt.includes('Fallstricke'), 'Fallstricke-Abschnitt vorhanden');
pruefe((await seite.locator('#content .ent-link').count()) >= 2, 'DD-Text verlinkt Entitäten');
await seite.locator('#content .ent-link').first().click();
await seite.waitForTimeout(350);
pruefe((await seite.locator('#content .ent-head').count()) === 1, 'DD-Link navigiert zur Entität');

/* --- Neue Entitäten --- */
for (const [id, erwartet] of [['pnh', 'FLAER'], ['hema', 'Reifungskontinuum'], ['etpall', 'CD1a'], ['aitl', 'Tfh'], ['mbl', 'MBL']]) {
  await seite.evaluate((r) => navigate(r), 'ent:' + id);
  await seite.waitForTimeout(250);
  const t = await seite.locator('#content').textContent();
  pruefe(t.includes(erwartet), `Entität ${id} enthält „${erwartet}"`);
}
await shot('2-entitaet');

/* --- Zell-Marker-Matrix --- */
console.log('\nZell-Marker-Matrix:');
await seite.evaluate(() => navigate('sec:cells'));
await seite.waitForTimeout(350);
pruefe((await seite.locator('#content table.matrix').count()) === 2, 'Beide Matrizen gerendert');
const zellen = await seite.locator('#content .cell').count();
pruefe(zellen > 300, `Intensitätszellen gefüllt (${zellen})`);
await seite.locator('#content th .mx-ent').first().click();
await seite.waitForTimeout(350);
pruefe((await seite.locator('#content .title').first().textContent()).length > 1, 'Spaltenkopf öffnet Marker-Lexikon');
await shot('3-zellmatrix');

/* --- Entscheidungsbäume --- */
console.log('\nEntscheidungsbäume:');
await seite.evaluate(() => navigate('sec:trees'));
await seite.waitForTimeout(350);
pruefe((await seite.locator('[data-treebody]').count()) === 5, 'Fünf Bäume vorhanden');
await seite.locator('#tree-blpd .tree-opt', { hasText: 'CD5 positiv' }).click();
await seite.waitForTimeout(250);
await seite.locator('#tree-blpd .tree-opt', { hasText: 'CD23+ und CD200 bright' }).click();
await seite.waitForTimeout(250);
pruefe((await seite.locator('#tree-blpd .tree-leaf h4').textContent()).includes('CLL'), 'B-LPD-Pfad endet bei CLL');
pruefe((await seite.locator('#tree-blpd .tree-crumb').count()) === 3, 'Pfad-Chips + Reset vorhanden');
await shot('4-baum');

/* --- DD-Fallmodus --- */
console.log('\nFallmodus:');
await seite.evaluate(() => navigate('sec:tool'));
await seite.waitForTimeout(350);
await seite.selectOption('#casePopulation', 'b');
await seite.waitForTimeout(250);
const klick = async (m, n) => { for (let i = 0; i < n; i++) { await seite.locator(`.mkbtn[data-m="${m}"]`).click(); await seite.waitForTimeout(100); } };
await klick('CD5', 1); await klick('CD23', 1); await klick('CD200', 4); await klick('FMC7', 2);
pruefe((await seite.locator('#toolresults .res.top .res-name b').textContent()).includes('Chronische Lymphatische'), 'CD5+/CD23+/CD200bright/FMC7– → CLL vorn');
const gruende = await seite.locator('#toolresults .res.top').textContent();
pruefe(/typisch ~\d+/.test(gruende), 'Begründung nennt Literatur-Häufigkeiten');
pruefe(gruende.includes('trennt'), 'Nächster Trennmarker mit Begründung');
await shot('5-fallmodus');

/* --- Ogata-Score --- */
console.log('\nOgata-Score:');
await seite.evaluate(() => navigate('sec:scores'));
await seite.waitForTimeout(350);
for (const id of ['og1', 'og2', 'og3']) await seite.selectOption('#' + id, '1');
await seite.selectOption('#og4', '0');
await seite.waitForTimeout(250);
const ogata = await seite.locator('#outOgata').textContent();
pruefe(ogata.includes('3/4'), `Ogata rechnet (3/4): „${ogata.slice(0, 60).trim()}…"`);
pruefe(ogata.includes('MDS-verdächtig'), 'Ogata-Bewertung korrekt');

/* --- Panels + SOP --- */
console.log('\nPanels & SOP:');
await seite.evaluate(() => navigate('sec:panels'));
await seite.waitForTimeout(350);
pruefe((await seite.locator('#content [id^="panel-"]').count()) >= 10, 'Zehn Panels gerendert');
pruefe((await seite.locator('#content [id^="sop-"]').count()) === 5, 'Fünf SOP-Tabellen gerendert');
const pnhPanel = await seite.locator('#panel-pnh-iccs').textContent();
pruefe(pnhPanel.includes('FLAER'), 'PNH-Panel mit FLAER');
await seite.locator('#panel-eric-cll-mrd .bl').first().click();
await seite.waitForTimeout(350);
pruefe((await seite.locator('#content .ent-head').count()) === 1, '„Deckt ab"-Chip öffnet Entität');
await shot('6-panels');

/* --- Literatur --- */
await seite.evaluate(() => navigate('sec:lit'));
await seite.waitForTimeout(350);
const lit = await seite.locator('#content').textContent();
pruefe(lit.includes('Craig FE') && lit.includes('Bethesda') && lit.includes('ICCS/ESCCA'), 'Neue Quellen in der Literaturliste');

console.log('\nKonsole:');
pruefe(konsole.length === 0, 'Keine JavaScript-Fehler', konsole.slice(0, 3).join(' | '));

await browser.close();
console.log(`\n${fehlgeschlagen === 0 ? 'Alle Prüfungen bestanden.' : fehlgeschlagen + ' Prüfung(en) fehlgeschlagen.'}\n`);
process.exit(fehlgeschlagen ? 1 : 0);
