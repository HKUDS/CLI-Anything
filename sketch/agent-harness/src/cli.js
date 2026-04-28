#!/usr/bin/env node

/**
 * sketch-cli — Generate Sketch files from JSON design specs.
 */

const { Command } = require('commander');
const path = require('path');
const fs = require('fs');
const { build } = require('./builder');

const program = new Command();

program
  .name('sketch-cli')
  .description('Generate .sketch files from JSON design specifications')
  .version('1.0.0');

program
  .command('build')
  .description('Build a .sketch file from a JSON design spec')
  .requiredOption('-i, --input <path>', 'Path to JSON design spec')
  .requiredOption('-o, --output <path>', 'Output .sketch file path')
  .option('-t, --tokens <path>', 'Custom design tokens file (overrides spec-level tokens)')
  .action(async (opts) => {
    try {
      const inputPath = path.resolve(opts.input);
      if (!fs.existsSync(inputPath)) {
        console.error(`Error: Input file not found: ${inputPath}`);
        process.exit(1);
      }

      console.log(`Building: ${opts.input} → ${opts.output}`);
      await build(inputPath, opts.output, { tokens: opts.tokens });
      console.log(`Done! Output: ${path.resolve(opts.output)}`);
    } catch (err) {
      console.error(`Build failed: ${err.message}`);
      if (process.env.DEBUG) console.error(err.stack);
      process.exit(1);
    }
  });

program
  .command('list-styles')
  .description('List all predefined styles in a tokens file')
  .option('-t, --tokens <path>', 'Tokens file path', path.resolve(__dirname, '..', 'tokens', 'default.json'))
  .action((opts) => {
    try {
      const tokensPath = path.resolve(opts.tokens);
      if (!fs.existsSync(tokensPath)) {
        console.error(`Tokens file not found: ${tokensPath}`);
        process.exit(1);
      }
      const tokens = JSON.parse(fs.readFileSync(tokensPath, 'utf-8'));
      const styles = tokens.styles || {};

      console.log('Available styles:\n');
      for (const [name, def] of Object.entries(styles)) {
        const props = Object.entries(def)
          .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
          .join(', ');
        console.log(`  ${name}  →  { ${props} }`);
      }
      console.log(`\nTotal: ${Object.keys(styles).length} styles`);
    } catch (err) {
      console.error(`Error: ${err.message}`);
      process.exit(1);
    }
  });

program.parse();
