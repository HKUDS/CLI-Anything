const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { promisify } = require('util');
const { exec } = require('child_process');
const execAsync = promisify(exec);

const ROOT = path.resolve(__dirname, '..');
const CLI = path.join(ROOT, 'src', 'cli.js');
const OUTPUT_DIR = path.join(ROOT, 'output', 'test');

const EXAMPLES = ['login-page', 'dashboard', 'card-list'];

beforeAll(() => {
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }
});

afterAll(() => {
  // Clean up test outputs
  for (const name of EXAMPLES) {
    const p = path.join(OUTPUT_DIR, `${name}.sketch`);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
  if (fs.existsSync(OUTPUT_DIR)) {
    try { fs.rmdirSync(OUTPUT_DIR); } catch (_) { /* ignore */ }
  }
});

describe('sketch-cli build', () => {
  for (const name of EXAMPLES) {
    describe(`example: ${name}`, () => {
      const inputPath = path.join(ROOT, 'examples', `${name}.json`);
      const outputPath = path.join(OUTPUT_DIR, `${name}.sketch`);

      test('input JSON exists', () => {
        expect(fs.existsSync(inputPath)).toBe(true);
      });

      test('builds without errors', () => {
        const result = execSync(
          `node "${CLI}" build --input "${inputPath}" --output "${outputPath}"`,
          { encoding: 'utf-8', cwd: ROOT }
        );
        expect(result).toContain('Done!');
      });

      test('output file exists', () => {
        expect(fs.existsSync(outputPath)).toBe(true);
      });

      test('output is a valid ZIP file (PK magic bytes)', () => {
        const buf = fs.readFileSync(outputPath);
        // ZIP magic: 0x50 0x4B (PK)
        expect(buf[0]).toBe(0x50);
        expect(buf[1]).toBe(0x4b);
      });

      test('ZIP contains required Sketch structure', () => {
        const result = execSync(`unzip -l "${outputPath}"`, { encoding: 'utf-8' });
        expect(result).toContain('meta.json');
        expect(result).toContain('document.json');
        expect(result).toContain('pages/');
      });

      test('ZIP contains at least one page JSON', () => {
        const result = execSync(`unzip -l "${outputPath}"`, { encoding: 'utf-8' });
        // pages/ directory should have at least one .json file
        const pageFiles = result.split('\n').filter(
          (line) => line.includes('pages/') && line.includes('.json')
        );
        expect(pageFiles.length).toBeGreaterThan(0);
      });
    });
  }
});

describe('sketch-cli list-styles', () => {
  test('lists styles from default tokens', () => {
    const result = execSync(`node "${CLI}" list-styles`, {
      encoding: 'utf-8',
      cwd: ROOT,
    });
    expect(result).toContain('$heading1');
    expect(result).toContain('$primaryButton');
    expect(result).toContain('Total:');
  });
});
