"""Expressions entrypoint; shared file mechanics live inside the plugin."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "lib" / "studio_core.py"
_spec = importlib.util.spec_from_file_location("charakit_studio_core", _path)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
# Preserve the existing Python helper API as well as its CLI location.
globals().update({name: value for name, value in vars(_core).items() if not name.startswith("_")})

if __name__ == "__main__":
    raise SystemExit(main())
