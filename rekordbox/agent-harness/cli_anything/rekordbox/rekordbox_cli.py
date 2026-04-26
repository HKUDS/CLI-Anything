#!/usr/bin/env python3
"""
cli-anything-rekordbox — Click-based CLI for Pioneer Rekordbox.

Combines:
  - Direct master.db SQLCipher access (via pyrekordbox)
  - Virtual MIDI control (mido)
  - Bunker.midi.csv mapping installer

JSON output via --json for agent consumption.
"""
from __future__ import annotations
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import click

PKG_DIR = Path(__file__).parent
DATA_DIR = PKG_DIR / "data"
SKILL_DIR = PKG_DIR / "skills"


# ---------------------------------------------------------------- helpers

def _emit(ctx: click.Context, payload):
    """Emit either JSON (when --json) or human-readable text."""
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, default=str, indent=2))
    else:
        if isinstance(payload, dict):
            for k, v in payload.items():
                click.echo(f"{k}: {v}")
        elif isinstance(payload, list):
            for item in payload:
                click.echo(item)
        else:
            click.echo(payload)


def _open_db():
    """Open rekordbox master.db. Bypasses 'rekordbox is running' safety on commits."""
    try:
        from pyrekordbox import Rekordbox6Database
    except ImportError:
        raise click.ClickException("pyrekordbox not installed. Run: pip install pyrekordbox")
    import warnings
    warnings.filterwarnings("ignore")
    return Rekordbox6Database(unlock=True)


def _commit_force(db):
    """Bypass pyrekordbox's running-rekordbox check."""
    db.registry.autoincrement_local_update_count(set_row_usn=True)
    db.session.commit()
    db.registry.clear_buffer()


def _open_midi(port_substr: str):
    """Find + open MIDI port containing port_substr (case-insensitive)."""
    import mido
    candidates = [n for n in mido.get_output_names() if port_substr.lower() in n.lower()]
    if not candidates:
        raise click.ClickException(
            f"No MIDI output port matching {port_substr!r}. Available: {mido.get_output_names()}"
        )
    return mido.open_output(candidates[0])


# ---------------------------------------------------------------- CLI root

@click.group(invoke_without_command=True)
@click.option("--json", "json_out", is_flag=True, help="Emit JSON output (for agents).")
@click.version_option()
@click.pass_context
def cli(ctx: click.Context, json_out: bool):
    """Pioneer Rekordbox 6/7 CLI — library writes + live-deck mixing."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_out
    if ctx.invoked_subcommand is None:
        # REPL mode
        try:
            from prompt_toolkit import PromptSession
            session = PromptSession(message="rekordbox> ")
            click.echo("cli-anything-rekordbox REPL — type 'help' for commands, Ctrl-D to exit.")
            while True:
                try:
                    line = session.prompt().strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not line:
                    continue
                if line in ("exit", "quit"):
                    break
                if line == "help":
                    click.echo(cli.get_help(ctx))
                    continue
                try:
                    cli.main(args=line.split(), standalone_mode=False, obj=ctx.obj)
                except SystemExit:
                    pass
                except Exception as e:
                    click.echo(f"error: {e}", err=True)
        except ImportError:
            click.echo(cli.get_help(ctx))


# ---------------------------------------------------------------- library

@cli.group()
def library():
    """Library inspection commands."""


@library.command("count")
@click.pass_context
def library_count(ctx):
    """Total tracks in master.db."""
    db = _open_db()
    n = sum(1 for _ in db.get_content())
    _emit(ctx, {"track_count": n})


@library.command("search")
@click.argument("query")
@click.option("--limit", default=20)
@click.pass_context
def library_search(ctx, query: str, limit: int):
    """Find tracks by title/artist substring."""
    db = _open_db()
    out = []
    for c in db.get_content():
        title = c.Title or ""
        artist = c.ArtistName or ""
        if query.lower() in title.lower() or query.lower() in artist.lower():
            out.append({
                "id": c.ID,
                "title": title,
                "artist": artist,
                "bpm": (c.BPM / 100.0) if c.BPM else None,
                "genre": getattr(getattr(c, "Genre", None), "Name", None),
            })
            if len(out) >= limit:
                break
    _emit(ctx, out)


@library.command("info")
@click.argument("track_id", type=int)
@click.pass_context
def library_info(ctx, track_id: int):
    """Show full metadata for a track."""
    db = _open_db()
    c = next((c for c in db.get_content() if c.ID == track_id), None)
    if not c:
        raise click.ClickException(f"track {track_id} not found")
    _emit(ctx, {
        "id": c.ID, "title": c.Title, "artist": c.ArtistName,
        "bpm": (c.BPM / 100.0) if c.BPM else None,
        "key": getattr(getattr(c, "Key", None), "Name", None),
        "duration_ms": c.Length,
        "file": c.FolderPath,
    })


@library.command("dump")
@click.option("--out", "out_path", default="rekordbox_library.json", type=click.Path())
@click.pass_context
def library_dump(ctx, out_path: str):
    """Export full library as JSON."""
    db = _open_db()
    rows = []
    for c in db.get_content():
        rows.append({
            "id": c.ID, "title": c.Title, "artist": c.ArtistName,
            "bpm": (c.BPM / 100.0) if c.BPM else None,
            "file": c.FolderPath,
        })
    Path(out_path).write_text(json.dumps(rows, indent=2))
    _emit(ctx, {"wrote": out_path, "tracks": len(rows)})


# ---------------------------------------------------------------- playlist

@cli.group()
def playlist():
    """Playlist commands."""


@playlist.command("list")
@click.pass_context
def playlist_list(ctx):
    """List all playlists."""
    db = _open_db()
    out = [{"id": p.ID, "name": p.Name, "song_count": len(list(p.Songs))}
           for p in db.get_playlist()]
    _emit(ctx, out)


@playlist.command("create")
@click.argument("name")
@click.pass_context
def playlist_create(ctx, name: str):
    """Create a new playlist."""
    db = _open_db()
    existing = [p for p in db.get_playlist() if p.Name == name]
    if existing:
        _emit(ctx, {"playlist": name, "id": existing[0].ID, "status": "already exists"})
        return
    pl = db.create_playlist(name)
    _commit_force(db)
    _emit(ctx, {"playlist": name, "id": pl.ID, "status": "created"})


@playlist.command("add")
@click.argument("playlist_name")
@click.option("--track-title", required=True, help="Track title to search + add")
@click.option("--track-id", type=int, help="Track ID (skips title search)")
@click.pass_context
def playlist_add(ctx, playlist_name: str, track_title: str, track_id: Optional[int]):
    """Add a track to a playlist."""
    db = _open_db()
    pl = next((p for p in db.get_playlist() if p.Name == playlist_name), None)
    if not pl:
        raise click.ClickException(f"playlist {playlist_name!r} not found")
    if track_id:
        track = next((c for c in db.get_content() if c.ID == track_id), None)
    else:
        track = next((c for c in db.get_content() if c.Title and track_title.lower() in c.Title.lower()), None)
    if not track:
        raise click.ClickException(f"track not found")
    db.add_to_playlist(pl, track)
    _commit_force(db)
    _emit(ctx, {"playlist": playlist_name, "added_track_id": track.ID, "title": track.Title})


@playlist.command("clear")
@click.argument("name")
@click.pass_context
def playlist_clear(ctx, name: str):
    """Remove all tracks from a playlist."""
    db = _open_db()
    pl = next((p for p in db.get_playlist() if p.Name == name), None)
    if not pl:
        raise click.ClickException(f"playlist {name!r} not found")
    n = 0
    for sp in list(pl.Songs):
        db.remove_from_playlist(pl, sp)
        n += 1
    _commit_force(db)
    _emit(ctx, {"playlist": name, "removed": n})


# ---------------------------------------------------------------- deck (MIDI)

@cli.group()
def deck():
    """Live deck control via virtual MIDI."""


def _btn(ch, note, velocity=127):
    import mido
    return mido.Message("note_on", channel=ch, note=note, velocity=velocity)


def _cc14(ch, msb_cc, lsb_cc, value14):
    import mido
    value14 = max(0, min(16383, value14))
    return [
        mido.Message("control_change", channel=ch, control=msb_cc, value=(value14 >> 7) & 0x7F),
        mido.Message("control_change", channel=ch, control=lsb_cc, value=value14 & 0x7F),
    ]


def _tap(port, ch, note, hold_ms=30):
    port.send(_btn(ch, note, 127))
    time.sleep(hold_ms / 1000)
    port.send(_btn(ch, note, 0))


@deck.command("play")
@click.option("--deck", "deck_n", type=int, required=True)
@click.option("--port", default="LoopBe")
@click.pass_context
def deck_play(ctx, deck_n: int, port: str):
    """Toggle play/pause on a deck."""
    if deck_n not in (1, 2):
        raise click.ClickException("deck must be 1 or 2")
    p = _open_midi(port)
    _tap(p, deck_n - 1, 0x0B)
    p.close()
    _emit(ctx, {"deck": deck_n, "action": "play_pause"})


@deck.command("sync")
@click.option("--deck", "deck_n", type=int, required=True)
@click.option("--port", default="LoopBe")
@click.pass_context
def deck_sync(ctx, deck_n: int, port: str):
    """Tempo-sync deck to master."""
    if deck_n not in (1, 2):
        raise click.ClickException("deck must be 1 or 2")
    p = _open_midi(port)
    _tap(p, deck_n - 1, 0x58)
    p.close()
    _emit(ctx, {"deck": deck_n, "action": "sync"})


@deck.command("crossfade")
@click.argument("from_deck", type=int)
@click.argument("to_deck", type=int)
@click.option("--secs", type=float, default=8.0)
@click.option("--steps", type=int, default=64)
@click.option("--port", default="LoopBe")
@click.pass_context
def deck_crossfade(ctx, from_deck: int, to_deck: int, secs: float, steps: int, port: str):
    """Smooth crossfade between decks."""
    if from_deck == to_deck:
        raise click.ClickException("from_deck == to_deck")
    p = _open_midi(port)
    start = -1.0 if from_deck == 1 else 1.0
    end = 1.0 if to_deck == 2 else -1.0
    for i in range(steps + 1):
        pos = start + (end - start) * i / steps
        v14 = int((pos + 1.0) / 2.0 * 16383)
        for msg in _cc14(6, 0x1F, 0x3F, v14):
            p.send(msg)
        time.sleep(secs / steps)
    p.close()
    _emit(ctx, {"crossfade": f"{from_deck}->{to_deck}", "secs": secs})


@deck.command("eq")
@click.option("--deck", "deck_n", type=int, required=True)
@click.option("--hi", type=float)
@click.option("--mid", type=float)
@click.option("--lo", type=float)
@click.option("--port", default="LoopBe")
@click.pass_context
def deck_eq(ctx, deck_n: int, hi: Optional[float], mid: Optional[float], lo: Optional[float], port: str):
    """Set EQ values (0..1; 0.5 = unity)."""
    if deck_n not in (1, 2):
        raise click.ClickException("deck must be 1 or 2")
    p = _open_midi(port)
    ch = deck_n - 1
    if hi is not None:
        for m in _cc14(ch, 0x07, 0x27, int(hi * 16383)): p.send(m)
    if mid is not None:
        for m in _cc14(ch, 0x0B, 0x2B, int(mid * 16383)): p.send(m)
    if lo is not None:
        for m in _cc14(ch, 0x0F, 0x2F, int(lo * 16383)): p.send(m)
    p.close()
    _emit(ctx, {"deck": deck_n, "hi": hi, "mid": mid, "lo": lo})


@deck.command("hot-cue")
@click.option("--deck", "deck_n", type=int, required=True)
@click.option("--slot", type=int, required=True, help="1..8")
@click.option("--port", default="LoopBe")
@click.pass_context
def deck_hot_cue(ctx, deck_n: int, slot: int, port: str):
    """Trigger hot cue 1-8."""
    if not 1 <= slot <= 8:
        raise click.ClickException("slot must be 1..8")
    if deck_n not in (1, 2):
        raise click.ClickException("deck must be 1 or 2")
    import mido
    p = _open_midi(port)
    ch = deck_n - 1
    note = slot - 1
    p.send(mido.Message("note_on", channel=ch, note=note, velocity=7))
    time.sleep(0.04)
    p.send(mido.Message("note_on", channel=ch, note=note, velocity=0))
    p.close()
    _emit(ctx, {"deck": deck_n, "hot_cue": slot})


# ---------------------------------------------------------------- top-level

@cli.command()
@click.pass_context
def status(ctx):
    """Report rekordbox runtime + DB + MIDI state."""
    import mido
    out = {"midi_outputs": mido.get_output_names()}
    try:
        db = _open_db()
        out["db_path"] = str(db.engine.url.database)
        out["track_count"] = sum(1 for _ in db.get_content())
        out["playlist_count"] = sum(1 for _ in db.get_playlist())
    except Exception as e:
        out["db_error"] = str(e)
    _emit(ctx, out)


@cli.command("install-mapping")
@click.option("--rekordbox-dir", default=None,
              help="Path to rekordbox install (auto-detects on Windows).")
@click.pass_context
def install_mapping(ctx, rekordbox_dir: Optional[str]):
    """Drop Bunker.midi.csv into rekordbox's MidiMappings folder."""
    src = DATA_DIR / "Bunker.midi.csv"
    if not src.exists():
        raise click.ClickException(f"bundled mapping not found at {src}")
    candidates = []
    if rekordbox_dir:
        candidates.append(Path(rekordbox_dir) / "MidiMappings")
    if sys.platform == "win32":
        for v in ["7.2.8", "7.2.7", "7.2.6", "6.8.6"]:
            candidates.append(Path(rf"C:\Program Files\rekordbox\rekordbox {v}\MidiMappings"))
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/rekordbox 7/rekordbox.app/Contents/Resources/MidiMappings"))
    written = []
    for d in candidates:
        if d.exists():
            for name in ["LoopBe Internal MIDI.midi.csv", "Bunker.midi.csv"]:
                dst = d / name
                try:
                    shutil.copy(str(src), str(dst))
                    if name.startswith("LoopBe"):
                        # rename @file header inside the CSV to match device name
                        text = dst.read_text(encoding="utf-8")
                        text = text.replace("@file,1,Bunker", "@file,1,LoopBe Internal MIDI", 1)
                        dst.write_text(text, encoding="utf-8")
                    written.append(str(dst))
                except PermissionError:
                    written.append(f"PERMISSION_DENIED:{dst}")
    _emit(ctx, {"installed_to": written, "next_step": "In rekordbox: Preferences -> Controller -> MIDI -> enable LoopBe Internal MIDI"})


@cli.command("mix")
@click.argument("track_a")
@click.argument("track_b")
@click.option("--secs", type=float, default=16.0, help="Crossfade duration")
@click.option("--port", default="LoopBe")
@click.pass_context
def mix(ctx, track_a: str, track_b: str, secs: float, port: str):
    """End-to-end: load track A on deck 1, load track B on deck 2, sync, crossfade."""
    # Library lookup
    db = _open_db()
    ta = next((c for c in db.get_content() if c.Title and track_a.lower() in c.Title.lower()), None)
    tb = next((c for c in db.get_content() if c.Title and track_b.lower() in c.Title.lower()), None)
    if not ta:
        raise click.ClickException(f"track A {track_a!r} not found in library")
    if not tb:
        raise click.ClickException(f"track B {track_b!r} not found in library")
    _emit(ctx, {"track_a": ta.Title, "track_b": tb.Title, "transition_secs": secs,
                "next": "ensure both tracks are loaded on decks 1 + 2 (manual via rekordbox UI), then run: cli-anything-rekordbox deck crossfade 1 2 --secs " + str(secs)})


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
