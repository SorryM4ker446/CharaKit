"""Build a local skills-only plugin ZIP; never include user artwork or metadata."""
import argparse
import json
from pathlib import Path
import zipfile


def build(root: Path, output: Path) -> dict:
    plugin = root / "plugins" / "charakit"
    manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
    files = sorted(path for path in plugin.rglob("*") if path.is_file()
                   and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"))
    required = {"plugin.json", "modules.json", "ROADMAP.md"}
    names = {path.relative_to(plugin).as_posix() for path in files}
    if not required.issubset(names):
        raise ValueError("Plugin manifest, module definitions, or roadmap is missing.")
    definitions = json.loads((plugin / "modules.json").read_text(encoding="utf-8"))
    available_skills = set()
    for module in definitions["modules"]:
        if module["status"] not in ("available", "planned"):
            raise ValueError("Module status must be available or planned.")
        if module["status"] == "available":
            skill_path = module.get("skill_path")
            if skill_path != f'skills/{module["skill_id"]}/SKILL.md' or skill_path not in names:
                raise ValueError("An available module must have a packaged Skill.")
            available_skills.add(skill_path)
    packaged_skills = {name for name in names if name.startswith("skills/") and name.endswith("/SKILL.md")}
    if not available_skills or packaged_skills != available_skills:
        raise ValueError("Packaged Skills must match the available module definitions.")
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
