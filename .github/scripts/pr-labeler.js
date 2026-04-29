const LABELS = {
  "new-cli": {
    color: "0E8A16",
    description: "Adds a new CLI or generated harness",
  },
  "existing-cli-fix": {
    color: "1D76DB",
    description: "Fixes or improves an existing CLI harness",
  },
  "cli-anything-skill": {
    color: "5319E7",
    description: "Changes CLI-Anything plugin or skill files",
  },
  "cli-anything-hub": {
    color: "FBCA04",
    description: "Changes CLI-Hub, registries, or hub docs",
  },
  "documentation": {
    color: "0075CA",
    description: "Documentation issue or improvement",
  },
  "github-actions": {
    color: "6F42C1",
    description: "Changes GitHub Actions or automation",
  },
};

const SCRIPT_MANAGED_LABELS = ["new-cli", "existing-cli-fix", "documentation"];
const REGISTRY_FILES = new Set([
  "registry.json",
  "public_registry.json",
  "matrix_registry.json",
]);

function isHarnessFile(path) {
  return /^[^/]+\/agent-harness\//.test(path);
}

function isNewHarnessManifest(file) {
  return (
    file.status === "added" &&
    /^[^/]+\/agent-harness\/(setup\.py|pyproject\.toml)$/.test(file.filename)
  );
}

function isDocumentationFile(path) {
  if (/(^|\/)SKILL\.md$/i.test(path)) {
    return false;
  }

  return (
    /^README(?:_[A-Z]+)?\.md$/.test(path) ||
    /^(CONTRIBUTING|SECURITY)\.md$/.test(path) ||
    /^docs\//.test(path) ||
    /^[^/]+\.md$/i.test(path)
  );
}

function titleLooksLikeRegistryCli(title) {
  return /\b(add|introduce|new)\b/i.test(title) && /\b(cli|harness|registry)\b/i.test(title);
}

function computeScriptLabels(files, title) {
  const paths = files.map((file) => file.filename);
  const labelsToApply = new Set();

  const hasHarnessChange = paths.some(isHarnessFile);
  const hasNewHarness = files.some(isNewHarnessManifest);
  const registryOnly = paths.length > 0 && paths.every((path) => REGISTRY_FILES.has(path));
  const registryNewCli = registryOnly && titleLooksLikeRegistryCli(title || "");
  const documentationOnly = paths.length > 0 && paths.every(isDocumentationFile);

  if (hasNewHarness || registryNewCli) {
    labelsToApply.add("new-cli");
  } else if (hasHarnessChange) {
    labelsToApply.add("existing-cli-fix");
  }

  if (documentationOnly) {
    labelsToApply.add("documentation");
  }

  return labelsToApply;
}

async function ensureLabels(github, owner, repo, core) {
  const existing = await github.paginate(github.rest.issues.listLabelsForRepo, {
    owner,
    repo,
    per_page: 100,
  });
  const existingNames = new Set(existing.map((label) => label.name));

  for (const [name, definition] of Object.entries(LABELS)) {
    if (existingNames.has(name)) {
      continue;
    }

    core.info(`Creating missing label: ${name}`);
    await github.rest.issues.createLabel({
      owner,
      repo,
      name,
      color: definition.color,
      description: definition.description,
    });
  }
}

async function syncScriptLabels(github, owner, repo, pullNumber, currentLabels, labelsToApply, core) {
  for (const label of labelsToApply) {
    if (currentLabels.has(label)) {
      continue;
    }

    core.info(`Adding label: ${label}`);
    await github.rest.issues.addLabels({
      owner,
      repo,
      issue_number: pullNumber,
      labels: [label],
    });
  }

  for (const label of SCRIPT_MANAGED_LABELS) {
    if (!currentLabels.has(label) || labelsToApply.has(label)) {
      continue;
    }

    core.info(`Removing label: ${label}`);
    try {
      await github.rest.issues.removeLabel({
        owner,
        repo,
        issue_number: pullNumber,
        name: label,
      });
    } catch (error) {
      if (error.status !== 404) {
        throw error;
      }
    }
  }
}

module.exports = async ({ github, context, core }) => {
  const pullRequest = context.payload.pull_request;
  if (!pullRequest) {
    core.info("No pull_request payload found; skipping PR labeling.");
    return;
  }

  const { owner, repo } = context.repo;
  const pullNumber = pullRequest.number;

  await ensureLabels(github, owner, repo, core);

  const files = await github.paginate(github.rest.pulls.listFiles, {
    owner,
    repo,
    pull_number: pullNumber,
    per_page: 100,
  });

  const labelsToApply = computeScriptLabels(files, pullRequest.title);

  const currentLabels = new Set((pullRequest.labels || []).map((label) => label.name));
  await syncScriptLabels(github, owner, repo, pullNumber, currentLabels, labelsToApply, core);
};

module.exports.computeScriptLabels = computeScriptLabels;
module.exports.LABELS = LABELS;
module.exports.SCRIPT_MANAGED_LABELS = SCRIPT_MANAGED_LABELS;
