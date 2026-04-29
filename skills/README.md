# CLI-Anything Skills

This directory is the canonical `npx skills` surface for in-repo CLI-Anything
harnesses.

Layout:

```text
skills/
  cli-anything-audacity/SKILL.md
  cli-anything-blender/SKILL.md
  ...
```

Typical usage:

```bash
npx skills add HKUDS/CLI-Anything --list
npx skills add HKUDS/CLI-Anything --skill cli-anything-audacity -g -y
```

The `SKILL.md` files here are the canonical repo-root copies. Installed harness
packages still ship compatibility copies inside `cli_anything/<software>/skills/`
for local runtime discovery.

CI rule:

- If a harness keeps a deep packaged `SKILL.md`, it must also have a matching
  repo-root `skills/<skill-id>/SKILL.md`.
- A future harness that only defines its canonical skill directly in `skills/`
  is also valid.
