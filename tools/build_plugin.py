"""Build a local skills-only plugin ZIP; never include user artwork or metadata."""
import argparse
import json
from pathlib import Path
import zipfile


def build(root: Path, output: Path) -> dict:
    plugin = root / "plugins" / "charakit-expressions"
    manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
    files = sorted(path for path in plugin.rglob("*") if path.is_file()
                   and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"))
    required = {"plugin.json", "skills/charakit-expressions/SKILL.md"}
    names = {path.relative_to(plugin).as_posix() for path in files}
    if not required.issubset(names):
        raise ValueError("Plugin manifest or Skill is missing.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(plugin).as_posix())
    return {"path": str(output.resolve()), "version": manifest["version"], "files": len(files)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1], args.output), ensure_ascii=False))
