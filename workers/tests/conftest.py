import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKERS_ROOT = Path(__file__).resolve().parents[1]
for root in (str(REPO_ROOT), str(WORKERS_ROOT)):
    if root not in sys.path:
        sys.path.insert(0, root)
