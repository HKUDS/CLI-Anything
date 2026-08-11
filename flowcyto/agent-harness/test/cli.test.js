/**
 * Tests der Kommandozeilenschnittstelle.
 *
 * Wichtigste Zusicherung: CLI und Oberflaeche liefern dieselben Zahlen, weil
 * beide dieselben Module nutzen. Der Vergleich wird hier ausdruecklich geprueft.
 */

import { test, expect, describe, beforeAll, afterAll } from 'bun:test';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';

import { makeTBNKSample } from './helpers.js';

const tmp = '/tmp/flowcyto-cli-test';
const cli = join(import.meta.dir, '..', 'cli.mjs');
let soll;

async function lauf(...args) {
  const proc = Bun.spawn(['bun', cli, ...args], { stdout: 'pipe', stderr: 'pipe' });
  const [stdout, stderr] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
  ]);
  const code = await proc.exited;
  return { stdout, stderr, code };
}

beforeAll(async () => {
  await mkdir(tmp, { recursive: true });
  const a = makeTBNKSample(30000, 21);
  soll = a.soll;
  await writeFile(join(tmp, 'a.fcs'), Buffer.from(a.buffer));
  await writeFile(join(tmp, 'b.fcs'), Buffer.from(makeTBNKSample(25000, 44).buffer));
  await writeFile(join(tmp, 'kaputt.fcs'), 'das ist keine FCS-Datei, sondern reiner Text.');
});

afterAll(async () => {
  await rm(tmp, { recursive: true, force: true });
});

describe('CLI', () => {
  test('Hilfe ohne Argumente', async () => {
    const { stdout, code } = await lauf();
    expect(code).toBe(0);
    expect(stdout).toContain('FlowCyto');
    expect(stdout).toContain('analyse');
    expect(stdout).toContain('batch');
  });

  test('info liefert Metadaten, Kanäle und Spillover', async () => {
    const { stdout, code } = await lauf('info', join(tmp, 'a.fcs'));
    expect(code).toBe(0);
    expect(stdout).toContain('FCS3.1');
    expect(stdout).toContain('Testzytometer');
    expect(stdout).toContain('30.000');
    expect(stdout).toContain('CD45');
    expect(stdout).toContain('Spillover-Matrix');
  });

  test('qc bewertet die Messung', async () => {
    const { stdout, code } = await lauf('qc', join(tmp, 'a.fcs'));
    expect(code).toBe(0);
    expect(stdout).toContain('Flussratenstabilität');
    expect(stdout).toMatch(/Gesamtbewertung: (ok|warnung|kritisch)/);
  });

  test('qc als JSON', async () => {
    const { stdout, code } = await lauf('qc', join(tmp, 'a.fcs'), '--format', 'json');
    expect(code).toBe(0);
    const daten = JSON.parse(stdout);
    expect(daten.checks.length).toBeGreaterThanOrEqual(6);
    expect(daten.overall).toBeTruthy();
  });

  test('analyse trifft die bekannte Zusammensetzung', async () => {
    const { stdout, code } = await lauf('analyse', join(tmp, 'a.fcs'), '--panel', 'tbnk', '--alter', '45', '--format', 'json');
    expect(code).toBe(0);
    const befund = JSON.parse(stdout);
    const wert = (name) => befund.ergebnisse.find((e) => e.name === name)?.wert;

    expect(Math.abs(wert('T-Zellen') - soll.tPct)).toBeLessThan(6);
    expect(Math.abs(wert('B-Zellen') - soll.bPct)).toBeLessThan(5);
    expect(Math.abs(wert('NK-Zellen') - soll.nkPct)).toBeLessThan(5);
    expect(Math.abs(wert('Summe T + B + NK') - 100)).toBeLessThan(6);
    expect(befund.kopf.alterJahre).toBe(45);
  });

  test('Panel wird ohne Angabe automatisch gewählt', async () => {
    const { stderr, code } = await lauf('analyse', join(tmp, 'a.fcs'), '--format', 'csv');
    expect(code).toBe(0);
    expect(stderr).toContain('Panel automatisch gewählt');
    expect(stderr).toContain('TBNK');
  });

  test('Textbefund enthält die Pflichtabschnitte', async () => {
    const { stdout } = await lauf('analyse', join(tmp, 'a.fcs'), '--panel', 'tbnk', '--pseudonym', 'CLI-001');
    expect(stdout).toContain('DURCHFLUSSZYTOMETRISCHER BEFUND');
    expect(stdout).toContain('CLI-001');
    expect(stdout).toContain('GATING-STRATEGIE');
    expect(stdout).toContain('QUALITÄTSKONTROLLE');
    expect(stdout).toContain('LIMITATIONEN');
    expect(stdout).toContain('In-vitro-Diagnostikum');
  });

  test('FHIR-Ausgabe ist ein gültiges Bundle', async () => {
    const { stdout, code } = await lauf('analyse', join(tmp, 'a.fcs'), '--panel', 'tbnk', '--format', 'fhir');
    expect(code).toBe(0);
    const bundle = JSON.parse(stdout);
    expect(bundle.resourceType).toBe('Bundle');
    expect(bundle.entry.some((e) => e.resource.resourceType === 'DiagnosticReport')).toBe(true);
    expect(bundle.entry.some((e) => e.resource.resourceType === 'Observation')).toBe(true);
  });

  test('Absolutzahlen über das Blutbild', async () => {
    const { stdout } = await lauf('analyse', join(tmp, 'a.fcs'), '--panel', 'tbnk', '--blutbild', 'lymph,2000', '--format', 'json');
    const befund = JSON.parse(stdout);
    const t = befund.ergebnisse.find((e) => e.name === 'T-Zellen');
    expect(Number.isFinite(t.absolut)).toBe(true);
    expect(t.absolut).toBeCloseTo((t.wert / 100) * 2000, 0);
  });

  test('batch erzeugt eine Vergleichstabelle', async () => {
    const { stdout, code } = await lauf('batch', join(tmp, 'a.fcs'), join(tmp, 'b.fcs'), '--panel', 'tbnk');
    expect(code).toBe(0);
    const zeilen = stdout.trim().split('\n');
    expect(zeilen.length).toBe(3); // Kopf + zwei Proben
    expect(zeilen[0]).toContain('T-Zellen');
    expect(zeilen[1]).toContain('a.fcs');
    expect(zeilen[2]).toContain('b.fcs');
  });

  test('batch überspringt fehlerhafte Dateien, ohne abzubrechen', async () => {
    const { stdout, stderr, code } = await lauf('batch', join(tmp, 'a.fcs'), join(tmp, 'kaputt.fcs'), '--panel', 'tbnk');
    expect(code).toBe(0);
    expect(stderr).toContain('kaputt.fcs');
    expect(stdout).toContain('Fehler');
    expect(stdout).toContain('a.fcs');
  });

  test('panels listet die Vorlagen und bewertet die Passung', async () => {
    const { stdout } = await lauf('panels', '--marker', 'CD45,CD3,CD4,CD8,CD19,CD16,CD56');
    expect(stdout).toContain('tbnk');
    expect(stdout).toContain('Passung: 100 %');
  });

  test('marker schlägt im Lexikon nach', async () => {
    const { stdout } = await lauf('marker', 'CD5');
    expect(stdout).toContain('CD5');
    expect(stdout).toContain('Mantelzelllymphom');
  });

  test('unbekannter Marker meldet Ähnliches statt zu scheitern', async () => {
    const { stdout, code } = await lauf('marker', 'CD1');
    expect(code).toBe(0);
    expect(stdout).toMatch(/nicht gefunden|CD1a/);
  });

  test('fehlerhafte Datei liefert Rückgabewert 1 und eine klare Meldung', async () => {
    const { stderr, code } = await lauf('info', join(tmp, 'kaputt.fcs'));
    expect(code).toBe(1);
    expect(stderr).toContain('Fehler:');
  });

  test('unbekanntes Panel wird abgewiesen', async () => {
    const { stderr, code } = await lauf('analyse', join(tmp, 'a.fcs'), '--panel', 'gibtsnicht');
    expect(code).toBe(1);
    expect(stderr).toContain('Unbekanntes Panel');
  });

  test('unbekannter Befehl wird abgewiesen', async () => {
    const { stderr, code } = await lauf('quatsch');
    expect(code).toBe(1);
    expect(stderr).toContain('Unbekannter Befehl');
  });

  test('CLI und Bibliothek liefern identische Zahlen', async () => {
    // Dieselbe Probe einmal ueber die CLI und einmal direkt ueber die Module
    const { stdout } = await lauf('analyse', join(tmp, 'a.fcs'), '--panel', 'tbnk', '--alter', '45', '--format', 'json');
    const ausCLI = JSON.parse(stdout);

    const { resetWorkspace, state, addSample } = await import('../src/core/store.js');
    const { parseFCS } = await import('../src/core/fcs.js');
    const { invalidateSample } = await import('../src/core/data.js');
    const { applyPanel, evaluateMetrics } = await import('../src/core/strategy.js');
    const { autoMapMarkers } = await import('../src/knowledge/markers.js');
    const { panelById } = await import('../src/knowledge/panels.js');

    resetWorkspace();
    const puffer = await Bun.file(join(tmp, 'a.fcs')).arrayBuffer();
    const probe = parseFCS(puffer, 'a.fcs');
    invalidateSample(probe);
    addSample(probe);
    state.markerMap = autoMapMarkers(probe);
    const panel = panelById('tbnk');
    const { stepGates } = applyPanel(probe, panel, { markerMap: state.markerMap });
    const { metriken } = evaluateMetrics(probe, panel, stepGates, state.markerMap);

    for (const m of metriken) {
      const cliWert = ausCLI.ergebnisse.find((e) => e.id === m.id)?.wert;
      if (Number.isFinite(m.wert)) expect(cliWert).toBeCloseTo(m.wert, 8);
    }
  });
});
