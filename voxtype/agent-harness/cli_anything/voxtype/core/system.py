"""Install/runtime introspection (`voxtype info ...`) and setup actions."""

from typing import Optional

from cli_anything.voxtype.utils import voxtype_backend as backend

INFO_TOPICS = ("engines", "models", "devices", "variants", "styles")


def info(topic: str, config_path: Optional[str] = None, **kw):
    if topic not in INFO_TOPICS:
        raise ValueError(f"Unknown info topic '{topic}'. Valid: {', '.join(INFO_TOPICS)}")
    args = ["info", topic, "--json"]
    if topic == "models":
        if kw.get("engine"):
            args += ["--engine", kw["engine"]]
        if kw.get("verify"):
            args.append("--verify")
    return backend.run_json(args, config_path, timeout=1800 if kw.get("verify") else 120)


def installed_models(config_path: Optional[str] = None, engine: Optional[str] = None) -> list[dict]:
    data = info("models", config_path, engine=engine)
    out = []
    for eng, block in sorted(data.get("engines", {}).items()):
        for m in block.get("models", []):
            if m.get("installed"):
                out.append({"engine": eng, **m})
    return out


def version_info() -> dict:
    return {"voxtype": backend.version(), "binary": backend.find_voxtype()}


def check(config_path: Optional[str] = None) -> dict:
    """`voxtype setup check` — human report; exit status reflects health."""
    proc = backend.run(["setup", "check"], config_path, check=False, timeout=120)
    report = proc.stdout.strip()
    return {"ok": proc.returncode == 0, "returncode": proc.returncode, "report": report,
            "stderr": proc.stderr.strip()}


def download_model(name: str, activate: bool = False, config_path: Optional[str] = None) -> dict:
    args = ["setup", "--download", "--model", name, "--no-post-install",
            "--progress-format", "json"]
    if activate:
        args.append("--activate")
    events, _ = backend.run_ndjson(args, config_path, timeout=7200)
    kinds = [e.get("event") for e in events]
    return {"model": name, "activated": activate, "events": len(events),
            "last_event": events[-1] if events else None, "event_kinds": sorted(set(k for k in kinds if k))}


def set_model(name: str, restart: bool = False, config_path: Optional[str] = None) -> dict:
    args = ["setup", "model", "--set", name]
    if restart:
        args.append("--restart")
    proc = backend.run(args, config_path, timeout=120)
    return {"model": name, "restart": restart, "message": proc.stdout.strip()}


def download_vad(config_path: Optional[str] = None) -> dict:
    proc = backend.run(["setup", "vad"], config_path, timeout=1800)
    return {"message": proc.stdout.strip()}
