/**
 * Syntaxprüfung: extrahiert alle <script>-Blöcke der Einzeldatei und prüft
 * jeden einzeln mit new Function (Parse-Test ohne Ausführung).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const wurzel = dirname(dirname(fileURLToPath(import.meta.url)));
const html = readFileSync(join(wurzel, 'haemflow.html'), 'utf8');

const bloecke = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
if (!bloecke.length) {
  console.error('Keine <script>-Blöcke gefunden.');
  process.exit(1);
}

let fehler = 0;
bloecke.forEach((code, i) => {
  try {
    new Function(code);
    console.log(`Block ${i + 1}: Syntax ok (${(code.length / 1024).toFixed(0)} kB)`);
  } catch (err) {
    fehler++;
    console.error(`Block ${i + 1}: SYNTAXFEHLER — ${err.message}`);
    const m = /<anonymous>:(\d+)/.exec(err.stack || '');
    if (m) {
      const zeilen = code.split('\n');
      const z = +m[1] - 1;
      for (let k = Math.max(0, z - 3); k < Math.min(zeilen.length, z + 2); k++) {
        console.error(`  ${k + 1}: ${zeilen[k]}`);
      }
    }
  }
});
process.exit(fehler ? 1 : 0);
