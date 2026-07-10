from __future__ import annotations

import sys
from pathlib import Path


HARNESS_ROOT = Path(__file__).resolve().parents[3]
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))
