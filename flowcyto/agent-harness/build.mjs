#!/usr/bin/env bun
/**
 * Baut die Anwendung zu einer einzigen, in sich geschlossenen HTML-Datei.
 *
 * Warum: In der Routine soll das Werkzeug ohne Server, ohne Installation und
 * ohne Netzverbindung laufen -- Messdaten duerfen den Rechner nicht verlassen.
 * Eine einzelne HTML-Datei laesst sich per Doppelklick oeffnen und liegt auf
 * jedem Laborrechner. Deshalb werden alle Module gebuendelt und samt CSS in
 * die Datei eingebettet.
 */

import { mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const wurzel = dirname(fileURLToPath(import.meta.url));
const dist = join(wurzel, 'dist');

async function bauen() {
  await mkdir(dist, { recursive: true });

  const ergebnis = await Bun.build({
    entrypoints: [join(wurzel, 'src/ui/main.js')],
    target: 'browser',
    format: 'esm',
    minify: false,
    sourcemap: 'none',
  });

  if (!ergebnis.success) {
    for (const log of ergebnis.logs) console.error(log);
    throw new Error('Bündeln fehlgeschlagen.');
  }

  const bundle = await ergebnis.outputs[0].text();
  const html = await readFile(join(wurzel, 'index.html'), 'utf8');

  const einzeldatei = html.replace(
    /<script type="module" src="\.\/src\/ui\/main\.js"><\/script>/,
    () => `<script type="module">\n${bundle}\n</script>`,
  );

  if (einzeldatei === html) throw new Error('Einbindungspunkt für das Bundle nicht gefunden.');

  const ziel = join(dist, 'flowcyto.html');
  await writeFile(ziel, einzeldatei, 'utf8');

  const groesse = (einzeldatei.length / 1024).toFixed(0);
  console.log(`dist/flowcyto.html geschrieben (${groesse} kB, keine externen Abhängigkeiten)`);

  // Prüfen, dass wirklich nichts nachgeladen wird
  const externe = [...einzeldatei.matchAll(/(?:src|href)="(https?:)?\/\//g)];
  if (externe.length) {
    throw new Error(`Die Datei verweist auf ${externe.length} externe Ressource(n) — sie wäre offline nicht lauffähig.`);
  }

  await artefaktFassung(einzeldatei);
}

/**
 * Zusätzliche Fassung für Hosts, die den Seiteninhalt selbst in ein
 * Grundgerüst einbetten (z. B. eine veröffentlichte Artifact-Seite). Dort darf
 * die Datei kein eigenes <html>, <head> oder <body> mitbringen; Titel und
 * Farbschema steuert der Host.
 */
async function artefaktFassung(einzeldatei) {
  const stil = einzeldatei.match(/<style>[\s\S]*?<\/style>/)?.[0];
  const titel = einzeldatei.match(/<title>([\s\S]*?)<\/title>/)?.[1] ?? 'FlowCyto';
  const rumpf = einzeldatei.match(/<body>([\s\S]*)<\/body>/)?.[1];
  if (!stil || !rumpf) throw new Error('Stil oder Rumpf für die eingebettete Fassung nicht gefunden.');

  // Die App belegt die volle Höhe des Einbettungsrahmens.
  const anpassung = `<style>
/* In eine fremde Seite eingebettet: der Host besitzt html/body. */
html, body { height: 100%; margin: 0; overflow: hidden; }
</style>`;

  const inhalt = `<title>${titel}</title>\n${stil}\n${anpassung}\n${rumpf.trim()}\n`;
  const ziel = join(dist, 'flowcyto-eingebettet.html');
  await writeFile(ziel, inhalt, 'utf8');

  // Auf echte Tag-Grenzen prüfen: <header> darf nicht als <head> gelten.
  for (const verboten of ['!doctype', 'html', 'head', 'body']) {
    if (new RegExp(`<${verboten}(?=[\\s>/])`, 'i').test(inhalt)) {
      throw new Error(`Die eingebettete Fassung enthält unerlaubtes <${verboten}>.`);
    }
  }
  console.log(`dist/flowcyto-eingebettet.html geschrieben (${(inhalt.length / 1024).toFixed(0)} kB, nur Seiteninhalt)`);
}

if (process.argv.includes('--clean')) await rm(dist, { recursive: true, force: true });
await bauen();
