const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const labeler = require("../pr-labeler.js");
const fixtures = require("./pr-labeler-fixtures.json");

const REPO_ROOT = path.resolve(__dirname, "../../..");
const LABELER_CONFIG_PATH = path.join(REPO_ROOT, ".github/labeler.yml");
const EXPECTED_LABELS = [
  "cli-anything-hub",
  "cli-anything-skill",
  "documentation",
  "existing-cli-fix",
  "github-actions",
  "new-cli",
];

function normalizeLabels(labels) {
  return [...labels].sort();
}

function sameLabels(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function loadLabelerPatterns() {
  const patternsByLabel = new Map();
  let currentLabel = null;

  for (const line of fs.readFileSync(LABELER_CONFIG_PATH, "utf8").split(/\r?\n/)) {
    const labelMatch = line.match(/^([a-z0-9-]+):$/);
    if (labelMatch) {
      currentLabel = labelMatch[1];
      patternsByLabel.set(currentLabel, []);
      continue;
    }

    const patternMatch = line.match(/-\s+"([^"]+)"/);
    if (currentLabel && patternMatch) {
      patternsByLabel.get(currentLabel).push(patternMatch[1]);
    }
  }

  return patternsByLabel;
}

function globToRegex(pattern) {
  let regex = "^";

  for (let index = 0; index < pattern.length; index += 1) {
    const char = pattern[index];
    const next = pattern[index + 1];
    const afterNext = pattern[index + 2];

    if (char === "*" && next === "*" && afterNext === "/") {
      regex += "(?:.*/)?";
      index += 2;
      continue;
    }

    if (char === "*" && next === "*") {
      regex += ".*";
      index += 1;
      continue;
    }

    if (char === "*") {
      regex += "[^/]*";
      continue;
    }

    regex += char.replace(/[|\\{}()[\]^$+?.]/g, "\\$&");
  }

  regex += "$";
  return new RegExp(regex);
}

function computePathLabels(files) {
  const labels = new Set();
  const patternsByLabel = loadLabelerPatterns();

  for (const [label, patterns] of patternsByLabel.entries()) {
    const regexes = patterns.map(globToRegex);
    if (files.some((file) => regexes.some((regex) => regex.test(file.filename)))) {
      labels.add(label);
    }
  }

  return labels;
}

function computeAllLabels(sample) {
  const labels = new Set(labeler.computeScriptLabels(sample.files, sample.title));
  for (const pathLabel of computePathLabels(sample.files)) {
    labels.add(pathLabel);
  }
  return normalizeLabels(labels);
}

function summarizeMetrics(results) {
  const labels = new Set(EXPECTED_LABELS);
  for (const result of results) {
    for (const label of result.expected) labels.add(label);
    for (const label of result.predicted) labels.add(label);
  }

  const perLabel = {};
  for (const label of labels) {
    let truePositive = 0;
    let falsePositive = 0;
    let falseNegative = 0;

    for (const result of results) {
      const expected = new Set(result.expected);
      const predicted = new Set(result.predicted);

      if (expected.has(label) && predicted.has(label)) truePositive += 1;
      if (!expected.has(label) && predicted.has(label)) falsePositive += 1;
      if (expected.has(label) && !predicted.has(label)) falseNegative += 1;
    }

    const precisionDenominator = truePositive + falsePositive;
    const recallDenominator = truePositive + falseNegative;

    perLabel[label] = {
      truePositive,
      falsePositive,
      falseNegative,
      precision: precisionDenominator === 0 ? 1 : truePositive / precisionDenominator,
      recall: recallDenominator === 0 ? 1 : truePositive / recallDenominator,
    };
  }

  const exactMatches = results.filter((result) => sameLabels(result.predicted, result.expected)).length;

  return {
    exactAccuracy: exactMatches / results.length,
    perLabel,
  };
}

test("real PR fixture label accuracy and recall", () => {
  const results = fixtures.map((sample) => ({
    number: sample.number,
    title: sample.title,
    expected: normalizeLabels(sample.expected),
    predicted: computeAllLabels(sample),
  }));

  const mismatches = results.filter((result) => {
    return !sameLabels(result.predicted, result.expected);
  });

  const metrics = summarizeMetrics(results);

  assert.deepStrictEqual(mismatches, [], JSON.stringify({mismatches, metrics}, null, 2));
  assert.equal(metrics.exactAccuracy, 1);

  for (const [label, metric] of Object.entries(metrics.perLabel)) {
    assert.equal(metric.precision, 1, `${label} precision: ${JSON.stringify(metric)}`);
    assert.equal(metric.recall, 1, `${label} recall: ${JSON.stringify(metric)}`);
  }
});

test("labeler config and script agree on the supported label set", () => {
  const configLabels = new Set(loadLabelerPatterns().keys());
  const scriptLabels = new Set(Object.keys(labeler.LABELS));
  for (const label of EXPECTED_LABELS) {
    assert(scriptLabels.has(label), `${label} must be creatable by pr-labeler.js`);
  }

  assert(configLabels.has("cli-anything-hub"));
  assert(configLabels.has("cli-anything-skill"));
  assert(configLabels.has("github-actions"));
});

test("registry-only maintenance is not treated as a new CLI", () => {
  const labels = computeAllLabels({
    title: "Update registry dates",
    files: [{filename: "registry.json", status: "modified"}],
  });

  assert.deepStrictEqual(labels, ["cli-anything-hub"]);
});

test("mixed README and harness changes are not documentation-only", () => {
  const labels = computeAllLabels({
    title: "fix(blender): update docs and render behavior",
    files: [
      {filename: "README.md", status: "modified"},
      {filename: "blender/agent-harness/cli_anything/blender/core/render.py", status: "modified"},
    ],
  });

  assert.deepStrictEqual(labels, ["existing-cli-fix"]);
});
