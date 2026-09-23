"""Make the harness importable when pytest is invoked from the repository root.

The tests import ``cli_anything.orcarouter`` and use package-relative imports,
so the harness directory has to be on ``sys.path``. Running pytest from inside
``orcarouter/agent-harness/`` already works because ``python -m pytest`` adds
the working directory; this conftest makes the same command work from the
repository root without changing any test.
"""

from __future__ import annotations

import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))
