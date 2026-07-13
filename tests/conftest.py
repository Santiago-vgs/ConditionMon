"""Test configuration: make the modules in src/ importable.

src modules use flat imports (`from features import ...`), matching how they're
run (`python src/etl.py`), so we add src/ to the path rather than importing as a
package.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
