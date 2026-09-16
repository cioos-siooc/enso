"""Tests for `shared/`, run from the repo root: `uv run --project process pytest tests`.

`shared` is a package at the repo root that both images copy in as `/app/shared`;
putting the root on the path is the same arrangement, without a container.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
