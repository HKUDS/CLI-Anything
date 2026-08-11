/**
 * Erzeugt die eingebettete Fassung für Hosts, die den Seiteninhalt selbst in
 * ein Grundgerüst setzen (veröffentlichte Artifact-Seite): Titel + Stile +
 * Body-Inhalt, ohne eigenes html/head/body.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const wurzel = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(wurzel, 'haemflow.html'), 'utf8');

const titel = html.match(/<title>([\s\S]*?)<\/title>/)?.[1];
const stil = html.match(/<style>[\s\S]*?<\/style>/)?.[0];
const rumpf = html.match(/<body[^>]*>([\s\S]*)<\/body>/)?.[1];
if (!titel || !stil || !rumpf) throw new Error('Titel, Stil oder Rumpf nicht gefunden.');

const inhalt = `<title>${titel}</title>
${stil}
<style>
/* Eingebettet: der Host besitzt html/body. */
html,body{height:100%;margin:0}
</style>
${rumpf.trim()}
`;

for (const verboten of ['!doctype', 'html', 'head', 'body']) {
  if (new RegExp(`<${verboten}(?=[\\s>/])`, 'i').test(inhalt)) {
    throw new Error(`Eingebettete Fassung enthält unerlaubtes <${verboten}>.`);
  }
}

mkdirSync(join(wurzel, 'dist'), { recursive: true });
const ziel = join(wurzel, 'dist', 'haemflow-eingebettet.html');
writeFileSync(ziel, inhalt);
console.log(`dist/haemflow-eingebettet.html geschrieben (${(inhalt.length / 1024).toFixed(0)} kB)`);
