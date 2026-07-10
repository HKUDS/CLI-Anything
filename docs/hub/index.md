# CLI-Anything Hub

CLI-Anything Hub is an agent-friendly registry and package manager for CLI tools that let AI agents operate GUI applications, developer tools, creative software, web APIs, and public SaaS platforms.

Canonical site: https://clianything.cc

Repository: https://github.com/HKUDS/CLI-Anything

PyPI package: https://pypi.org/project/cli-anything-hub/

## Install

```bash
pip install cli-anything-hub
```

## Agent Skill

```bash
npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y
```

## Commands

```bash
cli-hub list
cli-hub search <query>
cli-hub info <name>
cli-hub install <name>
cli-hub uninstall <name>
cli-hub update <name>
cli-hub launch <name> [args...]
```

## Machine-Readable Resources

- `https://clianything.cc/llms.txt`
- `https://clianything.cc/llms-full.txt`
- `https://clianything.cc/pricing.md`
- `https://clianything.cc/registry.json`
- `https://clianything.cc/public_registry.json`
- `https://clianything.cc/openapi.json`
- `https://clianything.cc/.well-known/agent.json`
- `https://clianything.cc/.well-known/agent-card.json`
- `https://clianything.cc/.well-known/ai-plugin.json`
- `https://clianything.cc/.well-known/agent-skills/index.json`
- `https://reeceyang.sgp1.cdn.digitaloceanspaces.com/SKILL.md`

## Copyright

Copyright: HKUDS. Lead author: Yuhao Yang (yuhao.page).
