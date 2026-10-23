"""Build a local skills-only plugin ZIP; never include user artwork or metadata."""
import argparse
import json
from pathlib import Path
import zipfile


def build(root: Path, output: Path, marketplace: bool = False) -> dict:
    plugin = root / "plugins" / "charakit"
    manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
    files = sorted(path for path in plugin.rglob("*") if path.is_file()
                   and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"))
    required = {"plugin.json", "modules.json", "ROADMAP.md", "LICENSE", "RELEASE_NOTES.md", "lib/studio_core.py",
                "lib/delivery_report.py", "lib/localization.py", "lib/task_localization.py", "lib/text_layout.py",
                "locales/en.json", "locales/zh-CN.json",
                "references/delivery-report.md", "references/localization.md", "references/qa-methods.md",
                "lib/edit_references.py", "references/edit-references.md",
                "skills/charakit-outfits/references/replacement-guide.md",
                "skills/charakit-outfits/references/full-outfit-guide.md",
                "skills/charakit-outfits/references/prop-edit-guide.md",
                "skills/charakit-poses/scripts/studio.py",
                "skills/charakit-poses/references/pose-guide.md"}
    names = {path.relative_to(plugin).as_posix() for path in files}
    html_files = sorted(name for name in names if Path(name).suffix.lower() in ('.html', '.htm'))
    if html_files:
        raise ValueError('Plugin pages must be rendered from Python; standalone HTML files cannot be packaged: '
                         + ', '.join(html_files))
    if not required.issubset(names):
        raise ValueError("Plugin manifest, module definitions, roadmap, or shared file helper is missing.")
    if (plugin / 'LICENSE').read_bytes() != (root / 'LICENSE').read_bytes():
        raise ValueError('Repository and bundled plugin licenses must match.')
    if manifest['version'] not in (plugin / 'RELEASE_NOTES.md').read_text(encoding='utf-8'):
        raise ValueError('Bundled release notes must describe the plugin version.')
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
    extra = []
    if marketplace:
        catalog_path = root / '.agents/plugins/marketplace.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        entries = catalog.get('plugins', [])
        if len(entries) != 1 or entries[0]['name'] != manifest['name'] or entries[0]['source'] != {
                'source': 'local', 'path': './plugins/charakit'}:
            raise ValueError('Release marketplace must point to the bundled CharaKit plugin.')
        extra = [(catalog_path, '.agents/plugins/marketplace.json')]
        extra += [(root / name, name) for name in ('LICENSE', 'README.md', 'README.zh-CN.md', 'RELEASES.md', 'docs/qa.md')]
        if any(not path.is_file() for path, name in extra):
            raise ValueError('Release marketplace documentation is missing.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                name = path.relative_to(plugin).as_posix()
                archive.write(path, 'plugins/charakit/' + name if marketplace else name)
            for path, name in extra:
                archive.write(path, name)
    return {"path": str(output.resolve()), "version": manifest["version"], "files": len(files) + len(extra),
            "format": "marketplace" if marketplace else "plugin"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--marketplace", action="store_true", help="Include the marketplace catalog and release documentation.")
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1], args.output, args.marketplace), ensure_ascii=False))
