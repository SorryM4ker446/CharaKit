"""Outfits entrypoint; shared file mechanics live inside the plugin."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "lib" / "studio_core.py"
_spec = importlib.util.spec_from_file_location("charakit_studio_core", _path)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
globals().update({name: value for name, value in vars(_core).items() if not name.startswith("_")})


def init_project(root, source, character, mode="auto"):
    return _core.init_project(root, source, character, mode, module="outfits")


def add_asset(root, image, outfit_id, target, color=None, prompt_file=None, brief_file=None,
              edit_type=None, replacement=None):
    return _core.add_outfit(root, image, outfit_id, target, color, prompt_file, brief_file,
                            edit_type, replacement)


def main():
    return _core.main(module="outfits")


if __name__ == "__main__":
    raise SystemExit(main())
