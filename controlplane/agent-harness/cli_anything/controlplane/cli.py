"""cli-anything-controlplane — agent-native CLI for infrastructure repos.

Reads a compose-based infrastructure repo (root `docker-compose.yml` with
`include:`) plus its Caddyfile and reports stacks, services, published ports,
site routing and static validation issues. Purely file-based: no Docker
daemon, no SSH, no mutation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from cli_anything.controlplane.core import caddyfile as caddy_mod
from cli_anything.controlplane.core import compose as compose_mod


class Ctx:
    def __init__(self, repo: Path, json_output: bool, caddyfile: Path | None):
        self.repo = repo
        self.json_output = json_output
        self.caddyfile_path = caddyfile

    def emit(self, payload, human: str) -> None:
        if self.json_output:
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            click.echo(human)

    def load_caddyfile(self) -> caddy_mod.Caddyfile:
        path = self.caddyfile_path or self.repo / "caddy" / "Caddyfile"
        if not path.is_file():
            raise click.ClickException(f"no Caddyfile at {path} (use --caddyfile)")
        return caddy_mod.load(path)


def _detect_repo(repo: str) -> Path:
    start = Path(repo).expanduser() if repo else Path.cwd()
    if not start.exists():
        raise click.ClickException(f"repo path does not exist: {start}")
    return compose_mod.repo_root(start)


@click.group()
@click.option("--repo", default="", help="Infrastructure repo root (default: detect from cwd)")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON")
@click.option("--caddyfile", default="", help="Path to the Caddyfile (default: <repo>/caddy/Caddyfile)")
@click.pass_context
def cli(ctx: click.Context, repo: str, json_output: bool, caddyfile: str):
    """Inspect an infrastructure repo: compose stacks, services, Caddy routing."""
    root = _detect_repo(repo)
    ctx.obj = Ctx(root, json_output, Path(caddyfile) if caddyfile else None)


# ── stack ──────────────────────────────────────────────────────────────


@cli.group()
def stack():
    """Inspect compose stacks."""


@stack.command("list")
@click.pass_obj
def stack_list(ctx: Ctx):
    """List stacks (directories containing a compose file)."""
    stacks = compose_mod.list_stacks(ctx.repo)
    payload = [
        {
            "name": s.path.name,
            "compose_name": s.name,
            "dir": s.path.name,
            "compose_file": str(s.compose_file),
            "services": len(s.services),
            "includes": s.includes,
        }
        for s in stacks
    ]
    lines = [f"{'STACK':<24} {'SERVICES':<9} COMPOSE NAME"]
    lines.append("-" * 78)
    for entry in payload:
        lines.append(f"{entry['name']:<24} {entry['services']:<9} {entry['compose_name']}")
    ctx.emit(payload, "\n".join(lines))


@stack.command("show")
@click.argument("name")
@click.pass_obj
def stack_show(ctx: Ctx, name: str):
    """Show one stack with its services and ports."""
    stacks = {s.name: s for s in compose_mod.list_stacks(ctx.repo)}
    stacks.update({s.path.name: s for s in compose_mod.list_stacks(ctx.repo)})
    target = stacks.get(name)
    if target is None:
        raise click.ClickException(
            f"unknown stack '{name}'. Known: {', '.join(sorted(stacks))}"
        )
    lines = [f"{target.name}  ({target.compose_file})", ""]
    for service in target.services:
        ports = ", ".join(
            f"{p.host}->{p.container}/{p.protocol}" if p.host else f"{p.container}/{p.protocol}"
            for p in service.ports
        )
        lines.append(f"  {service.name:<24} {service.image or '(build)':<32} {ports}")
    ctx.emit(target.as_dict(), "\n".join(lines))


@stack.command("validate")
@click.pass_obj
def stack_validate(ctx: Ctx):
    """Run static checks across every stack."""
    issues = compose_mod.validate(ctx.repo)
    errors = [i for i in issues if i["level"] == "error"]
    human = "\n".join(
        f"[{i['level']}] {i['file']}: {i['message']}" for i in issues
    ) or "no issues found"
    ctx.emit({"issues": issues, "errors": len(errors)}, human)
    if errors:
        sys.exit(1)


@cli.group()
def service():
    """Inspect services across stacks."""


@service.command("list")
@click.pass_obj
def service_list(ctx: Ctx):
    """List every service with image and published ports."""
    rows = []
    for stack_obj in compose_mod.list_stacks(ctx.repo):
        for svc in stack_obj.services:
            rows.append({
                "stack": stack_obj.name,
                "service": svc.name,
                "image": svc.image,
                "build": svc.build,
                "container_name": svc.container_name,
                "ports": [p.as_dict() for p in svc.ports],
            })
    lines = [f"{'STACK':<22} {'SERVICE':<24} {'IMAGE':<38} PORTS"]
    lines.append("-" * 110)
    for row in rows:
        ports = ", ".join(
            f"{p['host']}:{p['container']}" if p["host"] else p["container"]
            for p in row["ports"]
        )
        lines.append(f"{row['stack']:<22} {row['service']:<24} {(row['image'] or '(build)'):<38} {ports}")
    ctx.emit(rows, "\n".join(lines))


# ── caddy ──────────────────────────────────────────────────────────────


@cli.group()
def caddy():
    """Inspect the Caddyfile (static parse, no Caddy binary needed)."""


@caddy.command("sites")
@click.pass_obj
def caddy_sites(ctx: Ctx):
    """List site blocks with kind and upstreams."""
    cf = ctx.load_caddyfile()
    lines = [f"{'ADDRESS':<44} {'KIND':<14} UPSTREAM"]
    lines.append("-" * 110)
    for site in cf.sites:
        lines.append(
            f"{', '.join(site.addresses):<44} {site.kind():<14} {', '.join(site.upstreams())}"
        )
    ctx.emit([s.as_dict() for s in cf.sites], "\n".join(lines))


@caddy.command("hosts")
@click.pass_obj
def caddy_hosts(ctx: Ctx):
    """List every configured address."""
    cf = ctx.load_caddyfile()
    hosts = sorted({address for site in cf.sites for address in site.addresses})
    ctx.emit(hosts, "\n".join(hosts))


@caddy.command("find")
@click.argument("domain")
@click.pass_obj
def caddy_find(ctx: Ctx, domain: str):
    """Show the site block(s) that serve a domain."""
    cf = ctx.load_caddyfile()
    matches = cf.find(domain)
    if not matches:
        raise click.ClickException(f"no site block serves '{domain}'")
    lines = []
    for site in matches:
        lines.append(f"{', '.join(site.addresses)}  (line {site.line})")
        lines.append(f"  kind:      {site.kind()}")
        lines.append(f"  upstreams: {', '.join(site.upstreams()) or '-'}")
        for handler in site.handlers:
            args = " ".join(handler.args)
            lines.append(f"  - {handler.type} {args}".rstrip())
    ctx.emit([s.as_dict() for s in matches], "\n".join(lines))


@caddy.command("validate")
@click.pass_obj
def caddy_validate(ctx: Ctx):
    """Structural validation of the Caddyfile."""
    cf = ctx.load_caddyfile()
    issues = caddy_mod.validate(cf)
    errors = [i for i in issues if i["level"] == "error"]
    human = "\n".join(f"[{i['level']}] {i['message']}" for i in issues) or "no issues found"
    ctx.emit({"issues": issues, "sites": len(cf.sites), "errors": len(errors)}, human)
    if errors:
        sys.exit(1)


# ── doctor ─────────────────────────────────────────────────────────────


@cli.command()
@click.pass_obj
def doctor(ctx: Ctx):
    """Preflight the repo: layout, compose files, Caddyfile, routing gaps."""
    report: dict[str, object] = {"repo": str(ctx.repo)}
    problems: list[str] = []
    notices: list[str] = []

    stacks = compose_mod.list_stacks(ctx.repo)
    report["stacks"] = len(stacks)
    report["services"] = sum(len(s.services) for s in stacks)
    if not stacks:
        problems.append("no stacks found")

    compose_issues = compose_mod.validate(ctx.repo)
    report["compose_issues"] = compose_issues
    problems.extend(
        f"compose: {i['message']}" for i in compose_issues if i["level"] == "error"
    )

    path = ctx.caddyfile_path or ctx.repo / "caddy" / "Caddyfile"
    if path.is_file():
        cf = caddy_mod.load(path)
        caddy_issues = caddy_mod.validate(cf)
        report["caddyfile"] = str(path)
        report["sites"] = len(cf.sites)
        report["caddy_issues"] = caddy_issues
        problems.extend(
            f"caddy: {i['message']}" for i in caddy_issues if i["level"] == "error"
        )

        # Routing gap: a published container port that no site proxies to.
        proxied = {u.split(":")[0] for site in cf.sites for u in site.upstreams()}
        proxied_ports = {u for site in cf.sites for u in site.upstreams()}
        unproxied = []
        for stack_obj in stacks:
            for svc in stack_obj.services:
                if not svc.ports:
                    continue
                candidates = {svc.name, svc.container_name}
                if not (candidates & proxied) and not any(
                    any(f":{p.container}" in u for u in proxied_ports) for p in svc.ports
                ):
                    unproxied.append(f"{stack_obj.name}/{svc.name}")
        report["unproxied_services"] = unproxied
        if unproxied:
            notices.append(
                f"{len(unproxied)} published service(s) not referenced by any site block "
                "(fine for non-HTTP services such as RDP, DNS or tunnels)"
            )
    else:
        report["caddyfile"] = None
        problems.append(f"no Caddyfile at {path}")

    report["ok"] = not problems
    report["problems"] = problems
    report["notices"] = notices
    human = "\n".join(
        [f"[problem] {p}" for p in problems] + [f"[notice] {n}" for n in notices]
    ) or "doctor: all checks passed"
    ctx.emit(report, human)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    cli()
