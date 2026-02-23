"""Text-to-SQL agent package.

Sets up sys.path so that eval infrastructure modules (agentx, evaluation)
are importable from any submodule without each file needing its own path
manipulation.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EVAL_SRC = str(_PROJECT_ROOT / "eval" / "src")
_EVAL_ROOT = str(_PROJECT_ROOT / "eval")

for _path in (_EVAL_SRC, _EVAL_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)
