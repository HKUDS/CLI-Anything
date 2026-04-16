/**
 * primitives.js — Shape factory functions wrapping sketch-constructor models.
 *
 * Every function accepts { x, y, width, height, ...styleProps } and returns
 * a sketch-constructor Layer instance ready to be added to an Artboard or Group.
 */

const {
  Rectangle,
  Oval,
  Text,
  Group,
  ShapePath,
  CurvePoint,
  Color,
} = require('sketch-constructor');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildStyle(props) {
  const style = {};

  // Fills
  if (props.backgroundColor) {
    style.fills = [{ color: props.backgroundColor }];
  }

  // Borders
  if (props.borderColor) {
    style.borders = [
      {
        color: props.borderColor,
        thickness: props.borderWidth || 1,
        position: 'Inside',
      },
    ];
  }

  // Shadows
  if (props.shadow) {
    const s = props.shadow;
    style.shadows = [
      {
        color: s.color || '#00000026',
        blurRadius: s.blurRadius || 4,
        offsetX: s.offsetX || 0,
        offsetY: s.offsetY || 2,
        spread: s.spread || 0,
      },
    ];
  }

  return style;
}

/**
 * Map font family + weight to a valid PostScript font name.
 * sketch-constructor requires PostScript names (no spaces).
 */
const FONT_PS_MAP = {
  'PingFang SC': { regular: 'PingFangSC-Regular', bold: 'PingFangSC-Semibold' },
  'Helvetica Neue': { regular: 'HelveticaNeue', bold: 'HelveticaNeue-Bold' },
  'Helvetica': { regular: 'Helvetica', bold: 'Helvetica-Bold' },
};

function fontName(fontFamily, fontWeight) {
  const family = fontFamily || 'Helvetica Neue';
  const map = FONT_PS_MAP[family];
  if (map) {
    return fontWeight === 'bold' ? map.bold : map.regular;
  }
  // Fallback: remove spaces and append weight
  const base = family.replace(/\s+/g, '');
  return fontWeight === 'bold' ? `${base}-Bold` : base;
}

// ---------------------------------------------------------------------------
// Public factories
// ---------------------------------------------------------------------------

/**
 * createRectangle — rectangle with optional fill, border, cornerRadius, shadow.
 */
function createRectangle(props) {
  const style = buildStyle(props);
  const rect = new Rectangle({
    name: props.name || 'Rectangle',
    x: props.x || 0,
    y: props.y || 0,
    width: props.width || 100,
    height: props.height || 100,
    cornerRadius: props.cornerRadius || 0,
    style,
  });
  return rect;
}

/**
 * createOval — circle / ellipse.
 */
function createOval(props) {
  const style = buildStyle(props);
  return new Oval({
    name: props.name || 'Oval',
    x: props.x || 0,
    y: props.y || 0,
    width: props.width || 100,
    height: props.height || 100,
    style,
  });
}

/**
 * createText — text layer with font, color, alignment.
 *
 * Workaround for two sketch-constructor bugs:
 *   1. Text uses args.frame (not top-level x/y/width/height)
 *   2. Style.TextStyle double-wraps TextStyle, losing font/color — fix manually
 */
function createText(props) {
  const fn = fontName(props.fontFamily, props.fontWeight);
  const fs = props.fontSize || 14;
  const clr = props.color || '#000000';

  const text = new Text({
    string: props.value || props.string || '',
    name: props.name || 'Text',
    frame: {
      x: props.x || 0,
      y: props.y || 0,
      width: props.width || 200,
      height: props.height || 30,
    },
    fontSize: fs,
    fontName: fn,
    color: clr,
    alignment: props.textAlign || 'left',
    lineHeight: props.lineHeight || undefined,
    textBehaviour: 'fixed',
  });

  // Fix style.textStyle — sketch-constructor's Style constructor double-wraps
  // the TextStyle, causing it to fall back to Helvetica/16/black.
  // Copy the correct values from attributedString into style.textStyle.
  const ea = text.style.textStyle.encodedAttributes;
  ea.MSAttributedStringFontAttribute = {
    _class: 'fontDescriptor',
    attributes: { name: fn, size: fs },
  };
  ea.MSAttributedStringColorAttribute = new Color(clr);

  return text;
}

/**
 * createLine — a straight line from (0,0) to (width, 0) inside its frame.
 */
function createLine(props) {
  const w = props.width || 100;
  const style = {};
  style.borders = [
    {
      color: props.color || props.borderColor || '#000000',
      thickness: props.thickness || props.borderWidth || 1,
    },
  ];

  return new ShapePath({
    name: props.name || 'Line',
    frame: {
      x: props.x || 0,
      y: props.y || 0,
      width: w,
      height: 1,
    },
    points: [
      new CurvePoint({
        point: '{0, 0.5}',
        curveFrom: '{0, 0.5}',
        curveTo: '{0, 0.5}',
      }),
      new CurvePoint({
        point: '{1, 0.5}',
        curveFrom: '{1, 0.5}',
        curveTo: '{1, 0.5}',
      }),
    ],
    style,
    isClosed: false,
  });
}

/**
 * createGroup — wraps child layers.
 */
function createGroup(props, children) {
  const group = new Group({
    name: props.name || 'Group',
    frame: {
      x: props.x || 0,
      y: props.y || 0,
      width: props.width || 100,
      height: props.height || 100,
    },
  });

  if (children && children.length) {
    for (const child of children) {
      group.addLayer(child);
    }
  }

  return group;
}

/**
 * createLabeledRectangle — rectangle with centered text overlay.
 * Returns a Group containing the rect + text.
 */
function createLabeledRectangle(props, labelProps) {
  const rect = createRectangle({
    ...props,
    x: 0,
    y: 0,
    name: (props.name || 'Button') + '_bg',
  });

  const textHeight = (labelProps.fontSize || 16) * 1.4;
  const textY = ((props.height || 48) - textHeight) / 2;

  const text = createText({
    ...labelProps,
    x: 0,
    y: textY,
    width: props.width || 100,
    height: textHeight,
    name: (props.name || 'Button') + '_label',
    textAlign: labelProps.textAlign || 'center',
  });

  return createGroup(
    {
      name: props.name || 'LabeledRect',
      x: props.x || 0,
      y: props.y || 0,
      width: props.width || 100,
      height: props.height || 48,
    },
    [rect, text]
  );
}

module.exports = {
  createRectangle,
  createOval,
  createText,
  createLine,
  createGroup,
  createLabeledRectangle,
};
