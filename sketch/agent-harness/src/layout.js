/**
 * layout.js — Layout engine that computes { x, y, width, height } for layers.
 *
 * Supported layout types:
 *   - vertical-stack   : children flow top→bottom
 *   - horizontal-stack : children flow left→right
 *   - absolute         : children positioned by their own x/y
 */

// ---------------------------------------------------------------------------
// Text size estimation
// ---------------------------------------------------------------------------

function estimateTextSize(layer) {
  const fontSize = resolveFontSize(layer);
  const lineHeight = layer.lineHeight
    || layer._resolvedStyle?.lineHeight
    || (layer.style && typeof layer.style === 'object' ? layer.style.lineHeight : undefined)
    || fontSize * 1.4;
  const text = layer.value || '';
  // rough: each character ~ 0.55 * fontSize wide (CJK ~ 1.0)
  const cjkCount = (text.match(/[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]/g) || []).length;
  const asciiCount = text.length - cjkCount;
  const estWidth = (asciiCount * 0.55 + cjkCount * 1.0) * fontSize;
  const estHeight = lineHeight;
  return { width: Math.ceil(estWidth) + 4, height: Math.ceil(estHeight) };
}

function resolveFontSize(layer) {
  if (layer.fontSize) return layer.fontSize;
  if (layer._resolvedStyle?.fontSize) return layer._resolvedStyle.fontSize;
  if (layer.style && typeof layer.style === 'object' && layer.style.fontSize) return layer.style.fontSize;
  return 14;
}

// ---------------------------------------------------------------------------
// Resolve intrinsic size of a single layer spec
// ---------------------------------------------------------------------------

function intrinsicSize(layer, parentWidth) {
  // Spacer
  if (layer.type === 'spacer') {
    return {
      width: layer.width || parentWidth || 0,
      height: layer.height || 0,
    };
  }

  let w = layer.width;
  let h = layer.height;

  // "fill" means match parent
  if (w === 'fill') w = parentWidth || 300;

  // Resolve from resolved style
  if (!w && layer._resolvedStyle?.width === 'fill') w = parentWidth || 300;
  if (!w && layer._resolvedStyle?.width) w = layer._resolvedStyle.width;
  if (!h && layer._resolvedStyle?.height) h = layer._resolvedStyle.height;

  // Text auto-size
  if (layer.type === 'text' && (!w || !h)) {
    const est = estimateTextSize(layer);
    if (!w) w = est.width;
    if (!h) h = est.height;
  }

  // Group / rectangle defaults
  if (!w) w = 100;
  if (!h) h = layer.type === 'group' ? 0 : 40; // group height computed from children

  return { width: w, height: h };
}

// ---------------------------------------------------------------------------
// Layout algorithms
// ---------------------------------------------------------------------------

function layoutVerticalStack(layers, config, containerWidth, containerHeight) {
  const padTop = config.paddingTop || config.paddingVertical || 0;
  const padBottom = config.paddingBottom || config.paddingVertical || 0;
  const padH = config.paddingHorizontal || 0;
  const padLeft = config.paddingLeft || padH;
  const padRight = config.paddingRight || padH;
  const gap = config.gap || 0;
  const align = config.alignItems || 'left';

  const availableWidth = containerWidth - padLeft - padRight;
  let cursorY = padTop;

  const results = [];

  for (let i = 0; i < layers.length; i++) {
    const layer = layers[i];
    const size = intrinsicSize(layer, availableWidth);

    // If group, recursively lay out children to get real height
    if (layer.type === 'group' && layer.children && layer.layout) {
      const childResults = computeLayout(layer.children, layer.layout, size.width, size.height);
      // Update group height based on children
      let maxBottom = 0;
      for (const cr of childResults) {
        const bot = cr.y + cr.height;
        if (bot > maxBottom) maxBottom = bot;
      }
      if (size.height === 0 || layer._resolvedStyle?.height === undefined) {
        const groupPadBottom = layer.layout.paddingBottom || layer.layout.paddingVertical || 0;
        size.height = maxBottom + groupPadBottom;
      }
      layer._childLayout = childResults;
    } else if (layer.type === 'group' && layer.children && !layer.layout) {
      // absolute positioning, estimate from children
      layer._childLayout = computeLayout(layer.children, { type: 'absolute' }, size.width, size.height);
    }

    let x = padLeft;
    if (align === 'center') x = padLeft + (availableWidth - size.width) / 2;
    else if (align === 'right') x = padLeft + availableWidth - size.width;

    results.push({
      index: i,
      x,
      y: cursorY,
      width: size.width,
      height: size.height,
    });

    cursorY += size.height + gap;
  }

  return results;
}

function layoutHorizontalStack(layers, config, containerWidth, containerHeight) {
  const padH = config.paddingHorizontal || 0;
  const padLeft = config.paddingLeft || padH;
  const padRight = config.paddingRight || padH;
  const padTop = config.paddingTop || config.paddingVertical || 0;
  const gap = config.gap || 0;
  const justify = config.justifyContent || 'start';
  const alignItems = config.alignItems || 'top';

  const availableWidth = containerWidth - padLeft - padRight;

  // First pass — measure all children
  const sizes = layers.map((l) => intrinsicSize(l, undefined));

  // Recursively lay out child groups
  for (let i = 0; i < layers.length; i++) {
    const layer = layers[i];
    if (layer.type === 'group' && layer.children) {
      const lo = layer.layout || { type: 'absolute' };
      layer._childLayout = computeLayout(layer.children, lo, sizes[i].width, sizes[i].height);
      // Recalculate height from children if needed
      if (sizes[i].height === 0) {
        let maxBot = 0;
        for (const cr of layer._childLayout) {
          const bot = cr.y + cr.height;
          if (bot > maxBot) maxBot = bot;
        }
        sizes[i].height = maxBot;
      }
    }
  }

  const totalChildWidth = sizes.reduce((s, sz) => s + sz.width, 0);
  const totalGaps = (layers.length - 1) * gap;
  const maxChildHeight = Math.max(...sizes.map((s) => s.height), 0);

  // Determine starting X and gap override for justify
  let startX = padLeft;
  let effectiveGap = gap;

  if (justify === 'center') {
    startX = padLeft + (availableWidth - totalChildWidth - totalGaps) / 2;
  } else if (justify === 'end') {
    startX = padLeft + availableWidth - totalChildWidth - totalGaps;
  } else if (justify === 'space-between' && layers.length > 1) {
    effectiveGap = (availableWidth - totalChildWidth) / (layers.length - 1);
  }

  let cursorX = startX;
  const results = [];

  for (let i = 0; i < layers.length; i++) {
    const sz = sizes[i];
    let y = padTop;
    if (alignItems === 'center') y = padTop + (maxChildHeight - sz.height) / 2;
    else if (alignItems === 'bottom') y = padTop + maxChildHeight - sz.height;

    results.push({
      index: i,
      x: cursorX,
      y,
      width: sz.width,
      height: sz.height,
    });

    cursorX += sz.width + effectiveGap;
  }

  return results;
}

function layoutAbsolute(layers, config, containerWidth, containerHeight) {
  return layers.map((layer, i) => {
    const size = intrinsicSize(layer, containerWidth);
    if (layer.type === 'group' && layer.children) {
      const lo = layer.layout || { type: 'absolute' };
      layer._childLayout = computeLayout(layer.children, lo, size.width, size.height);
    }
    return {
      index: i,
      x: layer.x || 0,
      y: layer.y || 0,
      width: size.width,
      height: size.height,
    };
  });
}

// ---------------------------------------------------------------------------
// Main entry
// ---------------------------------------------------------------------------

/**
 * computeLayout — compute positions for an array of layer specs.
 *
 * @param {Array} layers  - layer spec objects from the JSON
 * @param {Object} layout - { type, gap, padding*, alignItems, justifyContent }
 * @param {number} containerWidth
 * @param {number} containerHeight
 * @returns {Array<{ index, x, y, width, height }>}
 */
function computeLayout(layers, layout, containerWidth, containerHeight) {
  if (!layout || !layout.type || layout.type === 'absolute') {
    return layoutAbsolute(layers, layout || {}, containerWidth, containerHeight);
  }
  if (layout.type === 'vertical-stack') {
    return layoutVerticalStack(layers, layout, containerWidth, containerHeight);
  }
  if (layout.type === 'horizontal-stack') {
    return layoutHorizontalStack(layers, layout, containerWidth, containerHeight);
  }
  // Fallback
  return layoutAbsolute(layers, layout, containerWidth, containerHeight);
}

module.exports = { computeLayout, estimateTextSize, intrinsicSize };
