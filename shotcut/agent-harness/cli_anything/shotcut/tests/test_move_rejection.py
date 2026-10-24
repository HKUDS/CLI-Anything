"""Rejected moves must not destroy clips, transitions or edit history."""

import xml.etree.ElementTree as ET

import pytest
from click.testing import CliRunner

from cli_anything.shotcut.core import timeline, transitions
from cli_anything.shotcut.shotcut_cli import cli


@pytest.mark.parametrize("destination", [-1, 99])
def test_invalid_destination_preserves_transitioned_clip(
    session_with_three_clips, destination
):
    session = session_with_three_clips
    transitions.add_transition(
        session, "dissolve", track_index=1, clip_a_index=0, duration_frames=14
    )
    # Keep a real redo entry to detect accidental checkpoint side effects.
    timeline.set_track_name(session, 1, "Renamed")
    assert session.undo()
    before = ET.tostring(session.root)
    undo_before = list(session._undo_stack)
    redo_before = list(session._redo_stack)
    modified_before = session.is_modified

    with pytest.raises(IndexError, match="Track index"):
        timeline.move_clip(session, 1, 0, destination)

    assert ET.tostring(session.root) == before
    assert session._undo_stack == undo_before
    assert session._redo_stack == redo_before
    assert session.is_modified == modified_before
    assert session.redo()
    assert timeline.list_tracks(session)[1]["name"] == "Renamed"


def test_rejected_cli_move_does_not_autosave_clip_loss(session_with_clip, tmp_path):
    path = tmp_path / "project.mlt"
    session_with_clip.save_project(str(path))
    before = path.read_bytes()

    result = CliRunner().invoke(
        cli,
        [
            "--json",
            "--project",
            str(path),
            "timeline",
            "move-clip",
            "1",
            "0",
            "--to-track",
            "99",
        ],
    )

    assert result.exit_code == 1
    assert "Track index 99 out of range" in result.output
    assert path.read_bytes() == before


@pytest.mark.parametrize("source, clip", [(99, 0), (1, 99), (1, -1)])
def test_invalid_source_preserves_edit_history(session_with_clip, source, clip):
    session = session_with_clip
    before = ET.tostring(session.root)
    undo_before = list(session._undo_stack)
    with pytest.raises(IndexError):
        timeline.move_clip(session, source, clip, 1)
    assert ET.tostring(session.root) == before
    assert session._undo_stack == undo_before
