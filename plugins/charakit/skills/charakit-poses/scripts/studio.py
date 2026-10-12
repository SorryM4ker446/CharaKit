"""Poses entrypoint; shared file mechanics live inside the plugin."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "lib" / "studio_core.py"
_spec = importlib.util.spec_from_file_location("charakit_studio_core", _path)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
globals().update({name: value for name, value in vars(_core).items() if not name.startswith("_")})


def init_project(root, source, character, mode="auto"):
    return _core.init_project(root, source, character, mode, module="poses")


def add_asset(root, image, pose_id, prompt_file=None, brief_file=None, references=None):
    return _core.add_pose(root, image, pose_id, prompt_file, brief_file, references)


def main():
    return _core.main(module="poses")


if __name__ == "__main__":
    raise SystemExit(main())
