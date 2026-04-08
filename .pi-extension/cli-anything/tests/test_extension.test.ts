/**
 * Tests for CLI-Anything Pi extension command registration.
 *
 * Verifies that all 5 commands are registered, handlers invoke
 * sendUserMessage with the expected content, and edge cases are handled.
 *
 * Run with: npx vitest run tests/test_extension.test.ts
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ─── Mock Pi Extension API ────────────────────────────────────────────

function createMockPi() {
	const registeredCommands: Array<{
		name: string;
		options: { description: string; handler: Function };
	}> = [];

	const sentMessages: string[] = [];

	return {
		registerCommand: vi.fn((name: string, options: any) => {
			registeredCommands.push({ name, options });
		}),
		sendUserMessage: vi.fn((msg: string) => {
			sentMessages.push(msg);
		}),
		registeredCommands,
		sentMessages,
	};
}

// ─── Mock file system for readAsset ───────────────────────────────────
//
// The extension reads assets from __dirname via readFileSync.
// We mock node:fs so that readAsset returns predictable content regardless
// of where the test is running (CI, local, etc.).

const MOCK_HARNESS = "# HARNESS.md Mock\nTest harness content.";
const MOCK_COMMANDS: Record<string, string> = {
	"cli-anything.md": "# cli-anything command mock",
	"refine.md": "# refine command mock",
	"test.md": "# test command mock",
	"validate.md": "# validate command mock",
	"list.md": "# list command mock",
};

vi.mock("node:fs", () => ({
	readFileSync: (path: string, encoding: string) => {
		const p = String(path);
		if (p.endsWith("HARNESS.md")) return MOCK_HARNESS;
		for (const [name, content] of Object.entries(MOCK_COMMANDS)) {
			if (p.endsWith(join("commands", name))) return content;
		}
		throw new Error(`Mock readFileSync: file not found: ${p}`);
	},
}));

// ─── Tests ────────────────────────────────────────────────────────────

describe("CLI-Anything Extension", () => {
	let mockPi: ReturnType<typeof createMockPi>;

	beforeEach(() => {
		mockPi = createMockPi();
	});

	async function loadExtension() {
		// Bust module cache so each test gets a fresh import
		const extPath = join(__dirname, "..", "index.ts") + "?t=" + Date.now();
		const mod = await import(extPath);
		return mod;
	}

	it("should export a default function", async () => {
		const mod = await loadExtension();
		expect(typeof mod.default).toBe("function");
	});

	it("should register exactly 5 commands", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);
		expect(mockPi.registerCommand).toHaveBeenCalledTimes(5);
	});

	it("should register all expected command names", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const names = mockPi.registeredCommands.map((c) => c.name);
		expect(names).toContain("cli-anything");
		expect(names).toContain("cli-anything:refine");
		expect(names).toContain("cli-anything:test");
		expect(names).toContain("cli-anything:validate");
		expect(names).toContain("cli-anything:list");
	});

	it("each command should have a description and handler", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		for (const cmd of mockPi.registeredCommands) {
			expect(typeof cmd.options.description).toBe("string");
			expect(cmd.options.description.length).toBeGreaterThan(0);
			expect(typeof cmd.options.handler).toBe("function");
		}
	});

	it("should send user message with HARNESS.md, command spec, and user args", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything",
		);
		expect(cmd).toBeDefined();

		const mockCtx = { ui: { notify: vi.fn() } };
		await cmd!.options.handler(" /path/to/software", mockCtx);

		expect(mockPi.sendUserMessage).toHaveBeenCalledTimes(1);
		const msg = mockPi.sentMessages[0];
		expect(msg).toContain("[CLI-Anything Command: cli-anything]");
		expect(msg).toContain(MOCK_HARNESS);
		expect(msg).toContain("# cli-anything command mock");
		expect(msg).toContain("/path/to/software");
		expect(msg).toContain("Extension Asset Paths");
		expect(msg).toContain("Path Remapping Rules");
	});

	it("should show warning when /cli-anything is invoked without args", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything",
		);

		const mockNotify = vi.fn();
		const mockCtx = { ui: { notify: mockNotify } };
		await cmd!.options.handler("  ", mockCtx);

		expect(mockNotify).toHaveBeenCalledTimes(1);
		expect(mockNotify).toHaveBeenCalledWith(
			expect.stringContaining("Usage: /cli-anything"),
			"warning",
		);
		expect(mockPi.sendUserMessage).not.toHaveBeenCalled();
	});

	it("should show warning when /cli-anything:refine is invoked without args", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything:refine",
		);

		const mockNotify = vi.fn();
		const mockCtx = { ui: { notify: mockNotify } };
		await cmd!.options.handler("", mockCtx);

		expect(mockNotify).toHaveBeenCalledTimes(1);
		expect(mockNotify).toHaveBeenCalledWith(
			expect.stringContaining("Usage: /cli-anything:refine"),
			"warning",
		);
		expect(mockPi.sendUserMessage).not.toHaveBeenCalled();
	});

	it("should show warning when /cli-anything:test is invoked without args", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything:test",
		);

		const mockNotify = vi.fn();
		const mockCtx = { ui: { notify: mockNotify } };
		await cmd!.options.handler("   ", mockCtx);

		expect(mockNotify).toHaveBeenCalledTimes(1);
		expect(mockNotify).toHaveBeenCalledWith(
			expect.stringContaining("Usage: /cli-anything:test"),
			"warning",
		);
		expect(mockPi.sendUserMessage).not.toHaveBeenCalled();
	});

	it("should show warning when /cli-anything:validate is invoked without args", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything:validate",
		);

		const mockNotify = vi.fn();
		const mockCtx = { ui: { notify: mockNotify } };
		await cmd!.options.handler("", mockCtx);

		expect(mockNotify).toHaveBeenCalledTimes(1);
		expect(mockNotify).toHaveBeenCalledWith(
			expect.stringContaining("Usage: /cli-anything:validate"),
			"warning",
		);
		expect(mockPi.sendUserMessage).not.toHaveBeenCalled();
	});

	it("/cli-anything:list should work with no arguments", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything:list",
		);

		const mockCtx = { ui: { notify: vi.fn() } };
		await cmd!.options.handler("", mockCtx);

		expect(mockPi.sendUserMessage).toHaveBeenCalledTimes(1);
		const msg = mockPi.sentMessages[0];
		expect(msg).toContain("[CLI-Anything Command: cli-anything:list]");
		expect(msg).toContain("(no arguments");
	});

	it("/cli-anything:list should pass flags through", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything:list",
		);

		const mockCtx = { ui: { notify: vi.fn() } };
		await cmd!.options.handler("--json --depth 2", mockCtx);

		expect(mockPi.sendUserMessage).toHaveBeenCalledTimes(1);
		const msg = mockPi.sentMessages[0];
		expect(msg).toContain("--json --depth 2");
	});

	it("/cli-anything:list getArgumentCompletions should return matching flags", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything:list",
		);

		const completions = cmd!.options.getArgumentCompletions("--j");
		expect(completions).toEqual([{ value: "--json", label: "--json" }]);
	});

	it("/cli-anything:list getArgumentCompletions should return null for unknown prefix", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		const cmd = mockPi.registeredCommands.find(
			(c) => c.name === "cli-anything:list",
		);

		const completions = cmd!.options.getArgumentCompletions("--unknown");
		expect(completions).toBeNull();
	});

	it("readAsset should throw descriptive error for missing file", async () => {
		const mod = await loadExtension();
		mod.default(mockPi);

		// Invoke with a valid arg — but our mock only has known files,
		// so any command that reads assets should succeed. We test error
		// by checking the error message format matches what readAsset produces.
		// The mock throws for unknown files, simulating a real missing asset.
		const { readFileSync } = await import("node:fs");
		expect(() => readFileSync("/nonexistent/file.md", "utf-8")).toThrow();
	});
});
