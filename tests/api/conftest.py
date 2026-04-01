"""Configure sys.path so tests can import from src/."""
import sys
import os

# Add src/ to the front of sys.path so that `import api.main` works
_src = os.path.join(os.path.dirname(__file__), "..", "..", "src")
_src = os.path.abspath(_src)
if _src not in sys.path:
    sys.path.insert(0, _src)
