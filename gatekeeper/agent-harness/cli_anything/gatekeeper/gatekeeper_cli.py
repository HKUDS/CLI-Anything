"""gatekeeper_cli.py — agent-native CLI for Gatekeeper AI (gatekeeper.blog).

Gatekeeper evaluates supplier bids against an RFP: compliance matrix,
pricing arithmetic, risk flags, weighted ranking and an award recommendation.

Usage (non-interactive):
    cli-anything-gatekeeper health
    cli-anything-gatekeeper auth login you@company.com
    cli-anything-gatekeeper auth complete --link "<link from the email>"
    cli-anything-gatekeeper extract ./tender/
    cli-anything-gatekeeper --json evaluate ./tender/ -o report.json
    cli-anything-gatekeeper report summary report.json
    cli-anything-gatekeeper report compliance report.json --status FAIL --mandatory
    cli-anything-gatekeeper reports list

Usage (interactive REPL):
    cli-anything-gatekeeper
"""

from __future__ import annotations

import functools
import json
import os
import sys
from typing import Any

import click

from cli_anything.gatekeeper import __version__
from cli_anything.gatekeeper.core import evaluate as eval_core
from cli_anything.gatekeeper.core import extract as extract_core
from cli_anything.gatekeeper.core import report as report_core
from cli_anything.gatekeeper.core import session
from cli_anything.gatekeeper.utils import gk_backend as gk

_json_output = False
_in_repl = False


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _out(data: Any, human=None) -> None:
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str, ensure_ascii=False))
    elif human:
        human(data)
    else:
        _kv(data)


def _kv(data: Any, indent: int = 0) -> None:
    pad = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                click.echo(f"{pad}{k}:")
                _kv(v, indent + 1)
            else:
                click.echo(f"{pad}{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                click.echo(f"{pad}- " + ", ".join(f"{k}={v}" for k, v in item.items() if v not in (None, "")))
            else:
                click.echo(f"{pad}- {item}")
    else:
        click.echo(f"{pad}{data}")


def _table(headers: list[str], rows: list[list[Any]]) -> None:
    rows = [["" if c is None else str(c) for c in r] for r in rows]
    widths = [min(max([len(h)] + [len(r[i]) for r in rows]), 60) for i, h in enumerate(headers)]
    line = lambda cells: "  ".join(c[:w].ljust(w) for c, w in zip(cells, widths))  # noqa: E731
    click.echo(line(headers))
    click.echo("  ".join("─" * w for w in widths))
    for r in rows:
        click.echo(line(r))


def _fail(msg: str, code: int = 1, status: int | None = None) -> None:
    if _json_output:
        click.echo(json.dumps({"error": msg, "http_status": status, "exit_code": code}))
    else:
        click.echo(f"Error: {msg}", err=True)
    if _in_repl:
        return
    sys.exit(code)


def _handle(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except gk.GatekeeperError as exc:
            code = {401: eval_core.EXIT_AUTH, 402: eval_core.EXIT_QUOTA}.get(exc.status, 1)
            _fail(str(exc), code, exc.status)
        except (extract_core.ExtractError, ValueError, FileNotFoundError) as exc:
            _fail(str(exc), 1)
    return wrapper


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Machine-readable JSON output.")
@click.option("--url", default=None, help="Gatekeeper base URL (default https://www.gatekeeper.blog; env GATEKEEPER_URL).")
@click.version_option(__version__, prog_name="cli-anything-gatekeeper")
@click.pass_context
def cli(ctx: click.Context, use_json: bool, url: str | None) -> None:
    """Gatekeeper AI — evaluate supplier bids against an RFP from the command line.

    Exit codes: 0 ok · 1 error · 2 sign-in required · 3 plan limit (upgrade).
    """
    global _json_output
    _json_output = use_json or _json_output
    if url:
        os.environ["GATEKEEPER_URL"] = url
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

@cli.command("health")
@_handle
def health_cmd() -> None:
    """Check the live Gatekeeper service is up (no sign-in, no credits)."""
    r = gk.health()
    try:
        cfg = gk.get_config()
        r["billing_available"] = cfg.get("billingAvailable")
    except gk.GatekeeperError:
        r["billing_available"] = None
    if not r["ok"]:
        # One JSON document only: fold the error into the health object.
        r.update({"error": "Gatekeeper health check failed", "exit_code": 1})
    _out(r, lambda d: click.echo(
        f"[{'OK' if d['ok'] else 'DOWN'}] {d['url']}  HTTP {d['http_status']}  {json.dumps(d['response'])}"))
    if not r["ok"] and not _in_repl:
        sys.exit(1)


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------

@cli.group("auth")
def auth_group() -> None:
    """Sign in with the same email magic link the website uses."""


@auth_group.command("login")
@click.argument("email")
@_handle
def auth_login(email: str) -> None:
    """Email a sign-in link/code to EMAIL. Then run `auth complete`."""
    r = gk.send_magic_link(email)
    r["next"] = ("Copy the sign-in link from the email WITHOUT clicking it and run: "
                 f'auth complete --link "<link>"   (or, if the email shows a code: '
                 f"auth complete --email {email} --code 123456)")
    _out(r, lambda d: click.echo(f"Sign-in email sent to {email}.\n{d['next']}"))


@auth_group.command("complete")
@click.option("--link", default=None, help="Magic link from the email, or the URL you landed on after clicking it.")
@click.option("--email", default=None, help="Email the code was sent to (with --code).")
@click.option("--code", default=None, help="6-digit code from the email.")
@_handle
def auth_complete(link: str | None, email: str | None, code: str | None) -> None:
    """Finish sign-in and store the session (~/.cli-anything-gatekeeper/session.json, 0600)."""
    if link:
        tokens = gk.resolve_magic_link(link)
    elif email and code:
        tokens = gk.verify_code(email, code.strip())
    else:
        raise ValueError("Pass --link, or --email with --code.")
    s = session.save(tokens, email=email)
    r = {"signed_in": True, "email": s["email"], "expires_at": s["expires_at"],
         "refreshable": bool(s["refresh_token"])}
    _out(r, lambda d: click.echo(f"Signed in as {d['email']}."))


@auth_group.command("token")
@click.argument("access_token")
@click.option("--refresh-token", default="", help="Optional refresh token for auto-renewal.")
@_handle
def auth_token(access_token: str, refresh_token: str) -> None:
    """Store a raw Supabase access token (e.g. copied from the browser)."""
    gk.get_user(access_token)  # validates
    s = session.save({"access_token": access_token, "refresh_token": refresh_token})
    _out({"signed_in": True, "email": s["email"], "expires_at": s["expires_at"]},
         lambda d: click.echo(f"Token stored for {d['email']}."))


@auth_group.command("status")
@click.option("--verify", is_flag=True, help="Also validate the token with the server.")
@_handle
def auth_status(verify: bool) -> None:
    """Show who is signed in and when the session expires."""
    st = session.status()
    if verify and st["signed_in"]:
        u = gk.get_user(session.get_token())
        st["verified"] = True
        st["email"] = u.get("email", st.get("email"))
    _out(st, lambda d: click.echo(
        f"Signed in as {d.get('email')} (expires in {max(d.get('expires_in_s') or 0, 0) // 60} min, "
        f"source {d['source']})" if d["signed_in"] else "Not signed in. Run `auth login <email>`."))


@auth_group.command("logout")
def auth_logout() -> None:
    """Delete the stored session."""
    removed = session.clear()
    _out({"signed_out": True, "removed_session_file": removed},
         lambda d: click.echo("Signed out."))


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

@cli.command("extract")
@click.argument("paths", nargs=-1, required=True)
@click.option("--text", "show_text", is_flag=True, help="Include extracted text in the output.")
@_handle
def extract_cmd(paths: tuple[str, ...], show_text: bool) -> None:
    """Preview what Gatekeeper will read from PATHS (files or a folder). Free, local."""
    entries = extract_core.extract_many(list(paths))
    r = extract_core.summarize(entries)
    if show_text:
        r["documents"] = [{"name": e["name"], "content": e["content"]} for e in entries]

    def human(d):
        _table(["File", "Type", "KB", "Chars", "Warning"],
               [[f["name"], f["ext"], f["size"] // 1024, f["chars"], f.get("warn") or ""] for f in d["files"]])
        click.echo(f"\nTotal {d['total_chars']:,} chars · {'ready to evaluate' if d['ready'] else 'NOT READY: ' + ', '.join(d['unreadable'])}")
        for doc in d.get("documents", []):
            click.echo(f"\n===== {doc['name']} =====\n{doc['content']}")
    _out(r, human)


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

def _print_summary(s: dict[str, Any]) -> None:
    p = s["project"]
    click.echo(f"Project: {p.get('name') or '—'}   RFP: {p.get('rfp_number') or '—'}   Buyer: {p.get('buyer') or '—'}")
    click.echo(f"Recommended: {s['recommended_vendor'] or 'No award recommended'}\n")
    _table(["#", "Vendor", "Score", "Status", f"Bid {p.get('currency') or ''}".strip(), "Wks", "Fail reason"],
           [[v["rank"], v["name"], v["total_score"], v["status"], report_core._fmt(v["bid_amount"]),
             v["delivery_weeks"], v["fail_reason"] or ""] for v in s["vendors"]])
    c = s["counts"]
    click.echo(f"\n{c['requirements']} requirements · {c['mandatory_fail_cells']} mandatory FAIL cells · "
               f"{c['risk_flags']} risk flags · {c['pricing_rows']} pricing rows")
    if s.get("rationale"):
        click.echo(f"\nRationale: {s['rationale']}")
    if s.get("platform_adjustments"):
        click.echo(f"Platform adjustments: {len(s['platform_adjustments'])} (mandatory PARTIAL → FAIL gate)")


@cli.command("evaluate")
@click.argument("paths", nargs=-1, required=True)
@click.option("-w", "--weights", default=None,
              help="Override scoring weights, e.g. 'technical=30,pricing=15' (six criteria must sum to 100).")
@click.option("-o", "--output", default=None, help="Save the full report JSON here (recommended).")
@click.option("--dry-run", is_flag=True, help="Extract and validate only; don't call the API or use a credit.")
@click.option("--timeout", type=float, default=None, help="Seconds to wait (default 300).")
@_handle
def evaluate_cmd(paths: tuple[str, ...], weights: str | None, output: str | None,
                 dry_run: bool, timeout: float | None) -> None:
    """Run a Gatekeeper evaluation on the RFP + supplier bids in PATHS. Uses one credit."""
    if dry_run:
        entries = extract_core.extract_many(list(paths))
        eval_core.build_payload(entries)
        r = {"dry_run": True, "weights": eval_core.parse_weights(weights) or eval_core.DEFAULT_WEIGHTS,
             **extract_core.summarize(entries), "signed_in": session.status()["signed_in"]}
        _out(r, lambda d: click.echo(
            f"Dry run OK: {len(d['files'])} files, {d['total_chars']:,} chars, signed_in={d['signed_in']}. Nothing sent."))
        return
    def started(n: int) -> None:
        if not _json_output:
            click.echo(f"Evaluating {n} documents… (typically 60-90 s)", err=True)
    data = eval_core.run(list(paths), weights, output, timeout, on_start=started)
    if _json_output:
        _out(data)
        return
    _print_summary(report_core.summary(data["evaluation"], {"model": data.get("model"), "plan": data.get("plan")}))
    click.echo(f"\n{data.get('processingTime', 0) / 1000:.1f}s · model {data.get('model') or '—'} · plan {data.get('plan') or '—'}")
    if data["cli"].get("saved_to"):
        click.echo(f"Saved: {data['cli']['saved_to']}")
    else:
        click.echo("Tip: add -o report.json to keep the full report for `report …` commands.")


# ---------------------------------------------------------------------------
# reports (server history)
# ---------------------------------------------------------------------------

@cli.group("reports")
def reports_group() -> None:
    """Your saved reports on gatekeeper.blog (opening one uses no credits)."""


@reports_group.command("list")
@click.option("--limit", default=20, show_default=True)
@click.option("--offset", default=0, show_default=True)
@_handle
def reports_list(limit: int, offset: int) -> None:
    """List completed evaluations, newest first."""
    r = report_core.list_saved(limit, offset)

    def human(d):
        if not d["reports"]:
            click.echo("No completed reports yet.")
            return
        _table(["ID", "Completed", "Vendors", "Files"],
               [[x["id"], (x.get("completed_at") or "")[:16], x.get("vendor_count"),
                 ", ".join(x.get("file_names") or [])] for x in d["reports"]])
    _out(r, human)


@reports_group.command("get")
@click.argument("report_id")
@click.option("-o", "--output", default=None, help="Save the report JSON here.")
@_handle
def reports_get(report_id: str, output: str | None) -> None:
    """Fetch one saved report."""
    data = report_core.get_saved(report_id, output)
    if _json_output:
        _out(data)
        return
    _print_summary(report_core.summary(data["evaluation"], {"model": data.get("model")}))
    if data.get("saved_to"):
        click.echo(f"\nSaved: {data['saved_to']}")


# ---------------------------------------------------------------------------
# report (offline views)
# ---------------------------------------------------------------------------

@cli.group("report")
def report_group() -> None:
    """Slice a saved report JSON offline (no network, no credits)."""


@report_group.command("summary")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@_handle
def report_summary(path: str) -> None:
    """Ranking, recommendation and headline counts."""
    ev, meta = report_core.load(path)
    _out(report_core.summary(ev, meta), _print_summary)


@report_group.command("compliance")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--status", type=click.Choice(["PASS", "FAIL", "PARTIAL", "N/A"], case_sensitive=False), default=None)
@click.option("--mandatory", is_flag=True, help="Mandatory requirements only.")
@click.option("--vendor", default=None, help="Filter by vendor name (substring).")
@_handle
def report_compliance(path: str, status: str | None, mandatory: bool, vendor: str | None) -> None:
    """Compliance cells with the quoted evidence."""
    ev, _ = report_core.load(path)
    r = report_core.compliance(ev, status, mandatory, vendor)
    _out(r, lambda d: _table(["Req", "M", "Vendor", "Status", "Requirement", "Evidence"],
                             [[c["id"], "M" if c["mandatory"] else "", c["vendor"], c["status"],
                               c["requirement"], c["evidence"]] for c in d["cells"]]))


@report_group.command("pricing")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@_handle
def report_pricing(path: str) -> None:
    """Quoted totals vs line-item sums, discrepancies and commercial terms."""
    ev, _ = report_core.load(path)
    r = report_core.pricing(ev)
    f = report_core._fmt
    _out(r, lambda d: _table(["Vendor", "Quoted", "Line sum", "Discrepancy", "Terms", "Validity", "Retention %"],
                             [[x.get("vendor"), f(x.get("quoted_total")), f(x.get("line_item_sum")),
                               f(x.get("discrepancy")), x.get("payment_terms"), x.get("validity_days"),
                               x.get("retention_pct")] for x in d["rows"]]))


@report_group.command("risks")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@_handle
def report_risks(path: str) -> None:
    """Risk flags and missing documents per vendor."""
    ev, _ = report_core.load(path)
    _out(report_core.risks(ev), lambda d: [click.echo(
        f"- {x['vendor']}: {x.get('flag') or x.get('description') or x.get('risk') or json.dumps(x)}"
        + (f" [{x['severity']}]" if x.get("severity") else "")) for x in d["risks"]] or click.echo("No risk flags."))


@report_group.command("markdown")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", default=None, help="Write to a .md file instead of stdout.")
@_handle
def report_markdown(path: str, output: str | None) -> None:
    """Render the full report as Markdown (for docs, emails, PRs)."""
    ev, meta = report_core.load(path)
    md = report_core.to_markdown(ev, meta)
    if output:
        with open(os.path.expanduser(output), "w", encoding="utf-8") as fh:
            fh.write(md)
        _out({"saved_to": os.path.abspath(os.path.expanduser(output)), "chars": len(md)},
             lambda d: click.echo(f"Saved: {d['saved_to']}"))
    elif _json_output:
        _out({"markdown": md})
    else:
        click.echo(md)


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

REPL_HELP = {
    "health": "Check the live service",
    "auth login <email> | complete | status | logout": "Sign in via email link",
    "extract <files|dir>": "Preview extracted text (free)",
    "evaluate <files|dir> -o r.json": "Run an evaluation (1 credit)",
    "reports list | get <id>": "Saved reports on gatekeeper.blog",
    "report summary|compliance|pricing|risks|markdown <r.json>": "Offline views",
    "json on|off": "Toggle JSON output",
    "exit": "Quit",
}


@cli.command("repl")
def repl() -> None:
    """Interactive REPL (default when no subcommand is given)."""
    import shlex

    from cli_anything.gatekeeper.utils.repl_skin import ReplSkin

    global _in_repl, _json_output
    _in_repl = True
    skin = ReplSkin("gatekeeper", version=__version__)
    skin.print_banner()
    st = session.status()
    skin.status("Service", gk.base_url())
    skin.status("Signed in", st.get("email") if st["signed_in"] else "no — `auth login <email>`")
    pt = skin.create_prompt_session()
    while True:
        try:
            line = skin.get_input(pt, project_name=(st.get("email") or "") if st["signed_in"] else "").strip()
        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            skin.print_goodbye()
            break
        if line == "help":
            skin.help(REPL_HELP)
            continue
        if line.startswith("json "):
            _json_output = line.split()[1] == "on"
            skin.info(f"JSON output {'on' if _json_output else 'off'}")
            continue
        try:
            cli.main(args=shlex.split(line), standalone_mode=False)
        except SystemExit:
            pass
        except click.ClickException as exc:
            skin.error(exc.format_message())
        except Exception as exc:  # noqa: BLE001
            skin.error(str(exc))
        st = session.status()
    _in_repl = False


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
