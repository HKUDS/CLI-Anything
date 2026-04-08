/**
 * CLI-Anything Extension for Pi Coding Agent
 *
 * Provides 5 slash commands that inject HARNESS.md methodology + command specs
 * into the agent session via pi.sendUserMessage(), enabling the agent to build
 * CLI harnesses for any GUI application.
 *
 * Commands:
 *   /cli-anything <path-or-repo>       - Build a complete CLI harness
 *   /cli-anything:refine <path> [focus] - Refine an existing CLI harness
 *   /cli-anything:test <path-or-repo>  - Run tests for a CLI harness
 *   /cli-anything:validate <path-or-repo> - Validate a CLI harness
 *   /cli-anything:list [options]       - List all CLI-Anything tools
 *
 * Asset files are self-contained in the extension directory.
 */

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

// Resolve extension directory for asset loading
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Read an asset file relative to the extension directory.
 * All assets must be present alongside index.ts (via install.sh or manual copy).
 */
function readAsset(...paths: string[]): string {
	const fullPath = join(__dirname, ...paths);
	try {
		return readFileSync(fullPath, "utf-8");
	} catch (err) {
		throw new Error(
			`CLI-Anything extension: failed to read asset "${join(...paths)}" at "${fullPath}": ${err instanceof Error ? err.message : String(err)}`
		);
	}
}

/**
 * Construct the message payload injected into the agent session.
 * Bundles HARNESS.md + command spec + user args into a single user message.
 */
function buildCommandMessage(
	commandName: string,
	commandMd: string,
	userArgs: string,
): string {
	const harnessMd = readAsset("HARNESS.md");

	const guidesDir = join(__dirname, "guides");
	const scriptsDir = join(__dirname, "scripts");
	const templatesDir = join(__dirname, "templates");

	return `[CLI-Anything Command: ${commandName}]

## CRITICAL: HARNESS.md — Read First
${harnessMd}

## Command Specification: ${commandName}
${commandMd}

## User Arguments
\`${userArgs}\`

## Extension Asset Paths
The following resources are available on this system. Use the \`read\` tool to access them when needed:
- Guides directory: \`${guidesDir}/\` — when HARNESS.md references guides (e.g. "See guides/session-locking.md"), read them from here
- Scripts directory: \`${scriptsDir}/\` — contains \`skill_generator.py\`
- Templates directory: \`${templatesDir}/\` — contains \`SKILL.md.template\`

## Path Remapping Rules
The command specs and HARNESS.md were written for a containerized environment. Apply these remapping rules:
1. \`/root/cli-anything/<software>/\` → use the current working directory (\`cwd\`). The software source is wherever the user specified in the arguments.
2. \`cli-anything-plugin/repl_skin.py\` → use \`${scriptsDir}/repl_skin.py\`
3. \`cli-anything-plugin/skill_generator.py\` → use \`${scriptsDir}/skill_generator.py\`
4. \`~/.claude/plugins/cli-anything/\` → use \`${__dirname}/\`
5. All relative paths in HARNESS.md (e.g. \`guides/...\`, \`templates/...\`) resolve against the asset paths above, NOT the working directory.

---

You are executing the /${commandName} command. Follow the HARNESS.md methodology and command specification precisely. Read HARNESS.md FIRST before taking any action. When you encounter references to guides, scripts, or templates, read them from the directories listed above. Apply the Path Remapping Rules for any hardcoded paths found in the specs.`;
}

/**
 * Inject command context into the agent session via sendUserMessage.
 * This triggers a full agent turn with access to all tools.
 */
function injectCommandContext(
	pi: ExtensionAPI,
	commandName: string,
	commandMdPath: string,
	userArgs: string,
): void {
	const commandMd = readAsset("commands", commandMdPath);
	const message = buildCommandMessage(commandName, commandMd, userArgs);
	pi.sendUserMessage(message);
}

export default function cliAnythingExtension(pi: ExtensionAPI) {
	// ─── /cli-anything <path-or-repo> ─────────────────────────────────
	pi.registerCommand("cli-anything", {
		description: "Build a complete CLI harness for any GUI application",
		handler: async (args, ctx) => {
			const trimmed = args.trim();
			if (!trimmed) {
				ctx.ui.notify(
					"Usage: /cli-anything <path-or-repo>\n\nProvide a local path to software source code or a GitHub repository URL.",
					"warning",
				);
				return;
			}

			injectCommandContext(pi, "cli-anything", "cli-anything.md", trimmed);
		},
	});

	// ─── /cli-anything:refine <path> [focus] ──────────────────────────
	pi.registerCommand("cli-anything:refine", {
		description: "Refine an existing CLI harness to improve coverage",
		handler: async (args, ctx) => {
			const trimmed = args.trim();
			if (!trimmed) {
				ctx.ui.notify(
					'Usage: /cli-anything:refine <software-path> [focus]\n\nExample: /cli-anything:refine /home/user/gimp "batch processing filters"',
					"warning",
				);
				return;
			}

			injectCommandContext(pi, "cli-anything:refine", "refine.md", trimmed);
		},
	});

	// ─── /cli-anything:test <path-or-repo> ────────────────────────────
	pi.registerCommand("cli-anything:test", {
		description: "Run tests for a CLI harness and update TEST.md",
		handler: async (args, ctx) => {
			const trimmed = args.trim();
			if (!trimmed) {
				ctx.ui.notify(
					"Usage: /cli-anything:test <software-path-or-repo>\n\nProvide a local path to software source code or a GitHub repository URL.",
					"warning",
				);
				return;
			}

			injectCommandContext(pi, "cli-anything:test", "test.md", trimmed);
		},
	});

	// ─── /cli-anything:validate <path-or-repo> ────────────────────────
	pi.registerCommand("cli-anything:validate", {
		description: "Validate a CLI harness against HARNESS.md standards",
		handler: async (args, ctx) => {
			const trimmed = args.trim();
			if (!trimmed) {
				ctx.ui.notify(
					"Usage: /cli-anything:validate <software-path-or-repo>\n\nProvide a local path to software source code or a GitHub repository URL.",
					"warning",
				);
				return;
			}

			injectCommandContext(pi, "cli-anything:validate", "validate.md", trimmed);
		},
	});

	// ─── /cli-anything:list [--path] [--depth] [--json] ───────────────
	pi.registerCommand("cli-anything:list", {
		description: "List all CLI-Anything tools (installed and generated)",
		getArgumentCompletions: (prefix: string) => {
			const flags = ["--json", "--path ", "--depth "];
			const filtered = flags.filter((f) => f.startsWith(prefix));
			return filtered.length > 0 ? filtered.map((f) => ({ value: f, label: f })) : null;
		},
		handler: async (args, ctx) => {
			// Parse optional flags, pass everything to the agent
			const trimmed = args.trim();
			// No validation needed — the agent handles --path, --depth, --json parsing
			injectCommandContext(pi, "cli-anything:list", "list.md", trimmed || "(no arguments — scan current directory)");
		},
	});
}
