/**
 * builder.js — Core builder: JSON design spec → .sketch file.
 *
 * Responsibilities:
 *   1. Load and merge design tokens
 *   2. Resolve $-references in styles
 *   3. Compute layout for each artboard
 *   4. Generate sketch-constructor layers
 *   5. Write .sketch file
 */

const fs = require('fs');
const path = require('path');
const JSZip = require('jszip');
const { Sketch, Page, Artboard } = require('sketch-constructor');
const { computeLayout } = require('./layout');
const primitives = require('./primitives');

// ---------------------------------------------------------------------------
// Custom build: bypass sketch-constructor's JsonStreamStringify (corrupts CJK)
// ---------------------------------------------------------------------------

/**
 * buildSketchFile — serialize Sketch object to .sketch ZIP with proper UTF-8.
 * sketch-constructor's built-in build() uses json-stream-stringify which
 * corrupts multi-byte characters (Chinese, Japanese, Korean).
 * We use JSON.stringify + Buffer.from to guarantee correct encoding.
 */
async function buildSketchFile(sketch, outputPath) {
  const zip = new JSZip();

  // Write top-level JSON files as UTF-8 buffers
  zip.file('meta.json', Buffer.from(JSON.stringify(sketch.meta), 'utf8'));
  zip.file('user.json', Buffer.from(JSON.stringify(sketch.user), 'utf8'));
  zip.file('document.json', Buffer.from(JSON.stringify(sketch.document), 'utf8'));

  // Pages
  zip.folder('pages');
  for (const page of sketch.pages) {
    zip.file(
      `pages/${page.do_objectID}.json`,
      Buffer.from(JSON.stringify(page), 'utf8')
    );
  }

  // Previews folder (required by some viewers)
  zip.folder('previews');

  // Write ZIP to file
  const buf = await zip.generateAsync({
    type: 'nodebuffer',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  });
  fs.writeFileSync(outputPath, buf);
}

// ---------------------------------------------------------------------------
// Token resolution
// ---------------------------------------------------------------------------

function loadTokens(specTokensPath, cliTokensPath, specDir) {
  const defaultTokensPath = path.resolve(__dirname, '..', 'tokens', 'default.json');
  let tokensPath = defaultTokensPath;

  if (cliTokensPath) {
    tokensPath = path.resolve(cliTokensPath);
  } else if (specTokensPath) {
    tokensPath = path.resolve(specDir, specTokensPath);
  }

  if (!fs.existsSync(tokensPath)) {
    console.warn(`Tokens file not found: ${tokensPath}, using defaults`);
    tokensPath = defaultTokensPath;
  }

  return JSON.parse(fs.readFileSync(tokensPath, 'utf-8'));
}

/**
 * Resolve a single $-reference value against the token bank.
 * "$primary" → tokens.colors.primary
 * "$md" in radius context → tokens.radius.md
 */
function resolveTokenValue(val, tokens, context) {
  if (typeof val !== 'string' || !val.startsWith('$')) return val;

  const key = val.slice(1); // strip $

  // Color reference
  if (tokens.colors && tokens.colors[key]) return tokens.colors[key];
  // Radius reference
  if (tokens.radius && tokens.radius[key] !== undefined) return tokens.radius[key];
  // Spacing reference
  if (tokens.spacing && tokens.spacing[key] !== undefined) return tokens.spacing[key];
  // Shadow reference
  if (tokens.shadows && tokens.shadows[key]) return tokens.shadows[key];

  return val; // unchanged
}

/**
 * Recursively resolve all $-refs inside an object.
 */
function resolveRefs(obj, tokens) {
  if (typeof obj === 'string') return resolveTokenValue(obj, tokens);
  if (typeof obj !== 'object' || obj === null) return obj;
  if (Array.isArray(obj)) return obj.map((v) => resolveRefs(v, tokens));

  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    out[k] = resolveRefs(v, tokens);
  }
  return out;
}

/**
 * Resolve the style field on a layer. It may be:
 *   - "$styleName" → lookup in tokens.styles, then resolve recursively
 *   - an inline object → resolve recursively
 *   - absent → {}
 */
function resolveStyle(style, tokens) {
  if (!style) return {};

  if (typeof style === 'string' && style.startsWith('$')) {
    const def = tokens.styles && tokens.styles[style];
    if (!def) {
      console.warn(`Unknown style token: ${style}`);
      return {};
    }
    return resolveRefs(def, tokens);
  }

  if (typeof style === 'object') {
    return resolveRefs(style, tokens);
  }

  return {};
}

// ---------------------------------------------------------------------------
// Layer generation (recursive)
// ---------------------------------------------------------------------------

/**
 * Build a single Sketch layer from a spec node + computed frame.
 */
function buildLayer(spec, frame, tokens) {
  const resolved = spec._resolvedStyle || {};

  const props = {
    name: spec.name || spec.type,
    x: frame.x,
    y: frame.y,
    width: frame.width,
    height: frame.height,
    // Style props
    backgroundColor: resolved.backgroundColor,
    borderColor: resolved.borderColor,
    borderWidth: resolved.borderWidth,
    cornerRadius: resolved.cornerRadius || 0,
    shadow: resolved.shadow,
    // Text props
    value: spec.value,
    fontSize: resolved.fontSize || spec.fontSize,
    fontWeight: resolved.fontWeight || spec.fontWeight,
    fontFamily: resolved.fontFamily || tokens.typography?.fontFamily,
    color: resolved.color || spec.color,
    textAlign: resolved.textAlign || spec.textAlign,
    lineHeight: resolved.lineHeight || spec.lineHeight,
  };

  switch (spec.type) {
    case 'rectangle': {
      if (spec.label) {
        const labelStyle = resolveStyle(spec.label.style, tokens);
        return primitives.createLabeledRectangle(props, {
          value: spec.label.value,
          fontSize: labelStyle.fontSize || 16,
          fontWeight: labelStyle.fontWeight,
          fontFamily: labelStyle.fontFamily || tokens.typography?.fontFamily,
          color: labelStyle.color || '#000000',
          textAlign: labelStyle.textAlign || 'center',
        });
      }
      return primitives.createRectangle(props);
    }

    case 'oval':
      return primitives.createOval(props);

    case 'text':
      return primitives.createText(props);

    case 'line':
      return primitives.createLine(props);

    case 'spacer':
      // Spacers are invisible — create a transparent rectangle as placeholder
      return primitives.createRectangle({
        ...props,
        name: spec.name || 'Spacer',
        backgroundColor: undefined,
      });

    case 'group': {
      const children = buildLayerTree(spec.children || [], spec._childLayout || [], tokens);

      // If the group has a background/border style, insert a bg rect first
      const groupChildren = [];
      if (resolved.backgroundColor || resolved.borderColor) {
        groupChildren.push(
          primitives.createRectangle({
            name: (spec.name || 'Group') + '_bg',
            x: 0,
            y: 0,
            width: frame.width,
            height: frame.height,
            backgroundColor: resolved.backgroundColor,
            borderColor: resolved.borderColor,
            borderWidth: resolved.borderWidth,
            cornerRadius: resolved.cornerRadius || 0,
          })
        );
      }
      groupChildren.push(...children);

      return primitives.createGroup(props, groupChildren);
    }

    default:
      console.warn(`Unknown layer type: ${spec.type}`);
      return primitives.createRectangle(props);
  }
}

/**
 * Given parallel arrays of specs and layout results, build layer tree.
 */
function buildLayerTree(specs, layoutResults, tokens) {
  const layers = [];
  for (let i = 0; i < specs.length; i++) {
    const spec = specs[i];
    const frame = layoutResults[i] || { x: 0, y: 0, width: 100, height: 40 };
    layers.push(buildLayer(spec, frame, tokens));
  }
  return layers;
}

// ---------------------------------------------------------------------------
// Pre-processing: resolve styles & attach to specs
// ---------------------------------------------------------------------------

function preprocessLayers(layers, tokens) {
  for (const layer of layers) {
    layer._resolvedStyle = resolveStyle(layer.style, tokens);

    // Merge explicit props with resolved style for sizing
    if (layer.width === 'fill' || layer._resolvedStyle.width === 'fill') {
      layer._resolvedStyle.width = 'fill';
    }

    if (layer.children) {
      preprocessLayers(layer.children, tokens);
    }

    if (layer.label) {
      layer.label._resolvedStyle = resolveStyle(layer.label.style, tokens);
    }
  }
}

// ---------------------------------------------------------------------------
// Main build function
// ---------------------------------------------------------------------------

/**
 * build — parse JSON spec, compute layout, generate .sketch file.
 *
 * @param {string} inputPath  - path to JSON spec file
 * @param {string} outputPath - path for output .sketch
 * @param {object} options    - { tokens: optional override path }
 */
async function build(inputPath, outputPath, options = {}) {
  const specRaw = fs.readFileSync(inputPath, 'utf-8');
  // Strip JSONC comments (// style)
  const specClean = specRaw.replace(/\/\/.*$/gm, '');
  const spec = JSON.parse(specClean);
  const specDir = path.dirname(path.resolve(inputPath));

  // Load tokens
  const tokens = loadTokens(spec.tokens, options.tokens, specDir);

  // Create sketch document
  const sketch = new Sketch();

  for (const pageSpec of spec.pages) {
    const page = new Page({ name: pageSpec.name || 'Page' });

    for (const abSpec of pageSpec.artboards) {
      const artboard = new Artboard({
        name: abSpec.name || 'Artboard',
        frame: {
          x: 0,
          y: 0,
          width: abSpec.width || 375,
          height: abSpec.height || 812,
        },
        backgroundColor: abSpec.backgroundColor || '#FFFFFF',
      });

      // Pre-process: resolve token references in styles
      const layers = abSpec.layers || [];
      preprocessLayers(layers, tokens);

      // Compute layout
      const layout = abSpec.layout || { type: 'absolute' };
      const layoutResults = computeLayout(
        layers,
        layout,
        abSpec.width || 375,
        abSpec.height || 812
      );

      // Build sketch layers
      const sketchLayers = buildLayerTree(layers, layoutResults, tokens);
      for (const sl of sketchLayers) {
        artboard.addLayer(sl);
      }

      page.addArtboard(artboard);
    }

    sketch.addPage(page);
  }

  // Ensure output directory exists
  const outDir = path.dirname(path.resolve(outputPath));
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  await buildSketchFile(sketch, path.resolve(outputPath));
  return outputPath;
}

module.exports = { build, resolveStyle, resolveTokenValue, loadTokens };
