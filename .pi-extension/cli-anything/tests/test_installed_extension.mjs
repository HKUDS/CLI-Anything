import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const installed = process.argv[2];
const { default: register } = await import(pathToFileURL(join(installed, "index.ts")));
const commands = new Map();
const messages = [];
register({
  registerCommand(name, command) { commands.set(name, command); },
  sendUserMessage(message) { messages.push(message); },
});
assert.equal(commands.size, 5);
for (const [name, command] of commands) {
  await command.handler(name.endsWith(":list") ? "" : "/tmp/software", {
    ui: { notify() { throw new Error("Unexpected usage warning"); } },
  });
  const message = messages.at(-1);
  for (const asset of ["docs/PREVIEW_PROTOCOL.md", "scripts/preview_bundle.py"]) {
    assert.ok(existsSync(join(installed, asset)), `Missing installed ${asset}`);
    assert.ok(message.includes(join(installed, asset)), `Missing remapping for ${asset}`);
  }
}
assert.equal(messages.length, 5);
console.log("PASS: all five installed commands resolve their preview resources");
