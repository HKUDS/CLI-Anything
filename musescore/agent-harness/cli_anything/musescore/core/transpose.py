"""Transposition logic — by key, by interval, diatonic."""

from pathlib import Path

from cli_anything.musescore.utils import musescore_backend as backend
from cli_anything.musescore.utils.mscx_xml import key_name_to_int


# ── Interval enum mapping (from MuseScore source) ────────────────────
# The transposeInterval field is an index into this enum, NOT semitones.
# Index: (name, semitones)
INTERVAL_ENUM = [
    ("Perfect Unison", 0),
    ("Minor Second", 1),
    ("Major Second", 2),
    ("Minor Third", 3),
    ("Major Third", 4),
    ("Perfect Fourth", 5),
    ("Augmented Fourth", 6),
    ("Perfect Fifth", 7),
    ("Minor Sixth", 8),
    ("Major Sixth", 9),
    ("Minor Seventh", 10),
    ("Major Seventh", 11),
    ("Perfect Octave", 12),
    ("Minor Ninth", 13),
    ("Major Ninth", 14),
    ("Minor Tenth", 15),
    ("Major Tenth", 16),
    ("Perfect Eleventh", 17),
    ("Augmented Eleventh", 18),
    ("Perfect Twelfth", 19),
    ("Minor Thirteenth", 20),
    ("Major Thirteenth", 21),
    ("Minor Fourteenth", 22),
    ("Major Fourteenth", 23),
    ("Perfect Fifteenth", 24),
    ("Double Augmented Unison", 25),
]

# Semitone → best-fit interval index (first match)
_SEMITONES_TO_INTERVAL = {}
for _idx, (_name, _semi) in enumerate(INTERVAL_ENUM):
    if _semi not in _SEMITONES_TO_INTERVAL:
        _SEMITONES_TO_INTERVAL[_semi] = _idx


def semitones_to_interval_index(semitones: int) -> int:
    """Convert a semitone count to the mscore transposeInterval index.

    Args:
        semitones: Number of semitones (0-24).

    Returns:
        Index into the MuseScore interval enum.
    """
    abs_semi = abs(semitones) % 25
    if abs_semi in _SEMITONES_TO_INTERVAL:
        return _SEMITONES_TO_INTERVAL[abs_semi]
    raise ValueError(f"No interval mapping for {semitones} semitones")


def transpose_by_key(input_path: str, output_path: str, *,
                     target_key: str,
                     direction: str = "closest",
                     transpose_key_signatures: bool = True,
                     transpose_chord_names: bool = True,
                     use_double_sharps_flats: bool = False) -> dict:
    """Transpose a score to a target key.

    Args:
        input_path: Path to input score.
        output_path: Path to output score.
        target_key: Key name (e.g., "C major", "Db", "Am").
        direction: "up", "down", or "closest".
        transpose_key_signatures: Whether to transpose key signatures.
        transpose_chord_names: Whether to transpose chord names.
        use_double_sharps_flats: Whether to use double sharps/flats.

    Returns:
        Dict with result info.
    """
    key_int = key_name_to_int(target_key)

    opts = {
        "mode": "to_key",
        "direction": direction,
        "targetKey": key_int,
        "transposeKeySignatures": transpose_key_signatures,
        "transposeChordNames": transpose_chord_names,
        "useDoubleSharpsFlats": use_double_sharps_flats,
    }

    result_path = backend.transpose_score(input_path, output_path, opts)

    return {
        "input": input_path,
        "output": str(result_path),
        "mode": "to_key",
        "target_key": target_key,
        "target_key_int": key_int,
        "direction": direction,
    }


def transpose_by_interval(input_path: str, output_path: str, *,
                          semitones: int | None = None,
                          interval_index: int | None = None,
                          direction: str = "up",
                          transpose_key_signatures: bool = True,
                          transpose_chord_names: bool = True,
                          use_double_sharps_flats: bool = False) -> dict:
    """Transpose a score by a chromatic interval.

    Specify either semitones or interval_index (not both).

    Args:
        semitones: Number of semitones to transpose.
        interval_index: Direct mscore interval enum index (0-25).
        direction: "up" or "down".
    """
    if semitones is not None and interval_index is not None:
        raise ValueError("Specify either semitones or interval_index, not both.")
    if semitones is None and interval_index is None:
        raise ValueError("Must specify either semitones or interval_index.")

    if semitones is not None:
        if semitones < 0:
            direction = "down"
            semitones = abs(semitones)
        idx = semitones_to_interval_index(semitones)
    else:
        idx = interval_index

    opts = {
        "mode": "by_interval",
        "direction": direction,
        "transposeInterval": idx,
        "transposeKeySignatures": transpose_key_signatures,
        "transposeChordNames": transpose_chord_names,
        "useDoubleSharpsFlats": use_double_sharps_flats,
    }

    result_path = backend.transpose_score(input_path, output_path, opts)

    return {
        "input": input_path,
        "output": str(result_path),
        "mode": "by_interval",
        "interval_index": idx,
        "direction": direction,
    }


def transpose_diatonic(input_path: str, output_path: str, *,
                       steps: int,
                       direction: str = "up",
                       transpose_key_signatures: bool = True,
                       transpose_chord_names: bool = True,
                       use_double_sharps_flats: bool = False) -> dict:
    """Transpose a score diatonically by a number of steps.

    Args:
        steps: Number of diatonic steps.
        direction: "up" or "down".
    """
    if steps < 0:
        direction = "down"
        steps = abs(steps)

    opts = {
        "mode": "diatonically",
        "direction": direction,
        "transposeInterval": steps,
        "transposeKeySignatures": transpose_key_signatures,
        "transposeChordNames": transpose_chord_names,
        "useDoubleSharpsFlats": use_double_sharps_flats,
    }

    result_path = backend.transpose_score(input_path, output_path, opts)

    return {
        "input": input_path,
        "output": str(result_path),
        "mode": "diatonically",
        "steps": steps,
        "direction": direction,
    }
