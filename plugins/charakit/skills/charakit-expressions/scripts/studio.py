"""Local file helper for the Codex expression skill. Never generates or retouches art."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
import zipfile

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

EXPRESSION_PRESETS = {
    "neutral": {"name": "Neutral", "direction": "Calm; reuse the source when it already matches."},
    "happy": {"name": "Happy", "direction": "Moderate smile; no laughter by default."},
    "sad": {"name": "Sad", "direction": "Restrained disappointment; no tears by default."},
    "angry": {"name": "Angry", "direction": "Displeased brows, gaze, and mouth; no shouting by default."},
    "surprised": {"name": "Surprised", "direction": "Moderately widened eyes and a slightly open mouth."},
    "eyes_closed": {"name": "Eyes closed", "direction": "Natural closed eyes; preserve the original mouth unless requested otherwise."},
    "shy": {"name": "Shy", "direction": "Bashful gaze and a restrained mouth; subtle blush unless excluded."},
    "confused": {"name": "Confused", "direction": "Questioning brows, gaze, and mouth; distinguish from startled surprise."},
    "wry_smile": {"name": "Wry smile", "direction": "A restrained awkward or resigned smile; distinguish from happiness."},
    "worried": {"name": "Worried", "direction": "Concerned brows and a tense gaze or mouth; distinguish from sadness."},
    "confident": {"name": "Confident", "direction": "An assured gaze and restrained pleased smile suited to the character."},
    "crying": {"name": "Crying", "direction": "Visible tears with coordinated distressed brows and mouth; preserve eye detail."},
}
EXPRESSIONS = tuple(EXPRESSION_PRESETS)
MOUTH_PRESETS = {
    "default": {"name": "Unspecified", "direction": "Use the expression direction; do not infer open or closed from old assets."},
    "closed": {"name": "Mouth closed", "direction": "Closed lips suited to the emotion; retain its brows, eyes, and intensity."},
    "open": {"name": "Mouth open", "direction": "A small natural speaking opening suited to the emotion; not surprise, shouting, or a phoneme sequence."},
}
MOUTH_STATES = tuple(MOUTH_PRESETS)
MODES = ("transparent_sprite", "preserve_background")
MAX_BYTES = 50 * 1024 * 1024
MAX_PIXELS = 40_000_000


class StudioError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def image_info(path: Path) -> dict:
    if not path.is_file():
        raise StudioError("FILE_NOT_FOUND", f"Image does not exist: {path}")
    if path.stat().st_size > MAX_BYTES:
        raise StudioError("IMAGE_TOO_LARGE", "Image exceeds the 50 MiB file limit.")
    try:
        with Image.open(path) as image:
            if image.format not in ("PNG", "JPEG"):
                raise StudioError("INVALID_IMAGE", "Only actual PNG/JPEG images are supported.")
            if image.width * image.height > MAX_PIXELS:
                raise StudioError("IMAGE_TOO_LARGE", "Image exceeds the 40 million pixel limit.")
            if getattr(image, "n_frames", 1) != 1:
                raise StudioError("INVALID_IMAGE", "Animated images are not supported.")
            image.verify()
        with Image.open(path) as image:
            image.load()
            alpha_present = "A" in image.getbands() or "transparency" in image.info
            alpha = image.convert("RGBA").getchannel("A")
            histogram = alpha.histogram()
            total = image.width * image.height
            result = {
                "path": str(path.resolve()), "format": image.format,
                "width": image.width, "height": image.height, "mode": image.mode,
                "alpha_present": alpha_present,
                "transparent_pixels": histogram[0],
                "semi_transparent_pixels": sum(histogram[1:255]),
                "alpha_bounds": alpha.getbbox(),
                "alpha_range": alpha.getextrema(),
                "transparent_fraction": round(histogram[0] / total, 6),
                "sha256": digest(path),
            }
            return result
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise StudioError("INVALID_IMAGE", f"Cannot decode image: {path}") from exc


def validate_image(path: Path, canvas: dict, mode: str) -> dict:
    if mode not in MODES:
        raise StudioError("INVALID_BACKGROUND_MODE", "Unknown background mode.")
    info = image_info(path)
    errors, warnings = [], ["MANUAL_ART_REVIEW_REQUIRED"]
    if info["format"] != "PNG":
        errors.append("OUTPUT_NOT_PNG")
    if (info["width"], info["height"]) != (canvas["width"], canvas["height"]):
        errors.append("CANVAS_MISMATCH")
    if info["alpha_range"][1] == 0:
        errors.append("EMPTY_IMAGE")
    if mode == "transparent_sprite":
        if not info["alpha_present"] or info["transparent_pixels"] == 0:
            errors.append("NO_TRANSPARENCY")
        warnings.append("ALPHA_EDGES_REQUIRE_VISUAL_REVIEW")
    return {"passed": not errors, "errors": errors, "warnings": warnings, "image": info}


def contained(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise StudioError("INVALID_PATH", "Recorded paths must be relative to the project.")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise StudioError("INVALID_PATH", "Recorded path leaves the project directory.")
    return path


def asset_slot(asset: dict) -> str:
    """Keep legacy keys stable; explicit mouth states are independent resources."""
    mouth = asset.get("mouth_state", "default")
    return asset["expression"] if mouth == "default" else f'{asset["expression"]}_mouth_{mouth}'


def read_state(root: Path) -> dict:
    def require(condition: bool) -> None:
        if not condition:
            raise ValueError("Invalid project metadata.")

    try:
        state = json.loads((root / "run.json").read_text(encoding="utf-8"))
        require(state["schema_version"] in ("1.0", "1.1"))
        require(bool(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", state["character_key"])))
        require(state["background_mode"] in MODES)
        require(isinstance(state["assets"], list) and isinstance(state["selected"], dict))
        for dimension in ("width", "height"):
            require(type(state["canvas"][dimension]) is int and state["canvas"][dimension] > 0)
        ids = set()
        for asset in state["assets"]:
            require(asset["expression"] in EXPRESSIONS)
            require(asset.get("mouth_state", "default") in MOUTH_STATES)
            require(state["schema_version"] == "1.1" or asset.get("mouth_state", "default") == "default")
            require(type(asset["version"]) is int and asset["version"] > 0)
            require(asset["id"] == f'{asset_slot(asset)}_v{asset["version"]:03d}')
            require(asset["id"] not in ids)
            require(asset["art_review_status"] in ("unreviewed", "accepted", "rejected"))
            require(bool(re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])))
            contained(root, asset["path"])
            ids.add(asset["id"])
        by_id = {asset["id"]: asset for asset in state["assets"]}
        for slot, asset_id in state["selected"].items():
            require(isinstance(asset_id, str) and asset_id in by_id)
            require(slot == asset_slot(by_id[asset_id]))
            require(by_id[asset_id]["art_review_status"] == "accepted")
        source = contained(root, state["source"])
        require(bool(re.fullmatch(r"[0-9a-f]{64}", state["source_sha256"])))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StudioError("INVALID_PROJECT", "Missing or invalid run.json; initialize a project first.") from exc
    if not source.is_file() or digest(source) != state["source_sha256"]:
        raise StudioError("SOURCE_CHANGED", "Saved source is missing or has changed; keep it immutable.")
    return state


def write_state(root: Path, state: dict) -> None:
    state["updated_at"] = timestamp()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=root, suffix=".json", delete=False) as stream:
        temp = Path(stream.name)
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        os.replace(temp, root / "run.json")
    finally:
        temp.unlink(missing_ok=True)


def copy_exclusive(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)


def init_project(root: Path, source: Path, character: str, mode: str = "auto") -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", character):
        raise StudioError("INVALID_CHARACTER_KEY", "Use a lowercase filename key, e.g. angelina.")
    info = image_info(source)
    if info["alpha_range"][1] == 0:
        raise StudioError("EMPTY_IMAGE", "Source is fully transparent.")
    if mode == "auto":
        mode = "transparent_sprite" if info["transparent_pixels"] else "preserve_background"
    if mode not in MODES:
        raise StudioError("INVALID_BACKGROUND_MODE", "Unknown background mode.")
    if mode == "transparent_sprite" and not info["transparent_pixels"]:
        raise StudioError("NO_TRANSPARENCY", "Transparent mode requires a transparent source in this MVP.")
    root.mkdir(parents=True, exist_ok=True)
    target = root / ("source.png" if info["format"] == "PNG" else "source.jpg")
    if (root / "run.json").exists() or target.exists():
        raise StudioError("PROJECT_EXISTS", "Source or run.json already exists; use another output directory.")
    copy_exclusive(source, target)
    state = {
        "schema_version": "1.0", "character_key": character,
        "source": target.name, "source_sha256": info["sha256"],
        "canvas": {"width": info["width"], "height": info["height"]},
        "background_mode": mode, "assets": [], "selected": {}, "created_at": timestamp(),
    }
    write_state(root, state)
    return {"project": str(root.resolve()), "canvas": state["canvas"], "background_mode": mode}


def get_asset(state: dict, asset_id: str) -> dict:
    for asset in state["assets"]:
        if asset["id"] == asset_id:
            return asset
    raise StudioError("ASSET_NOT_FOUND", f"Unknown asset: {asset_id}")


def check_asset(root: Path, state: dict, asset: dict) -> dict:
    path = contained(root, asset["path"])
    try:
        report = validate_image(path, state["canvas"], state["background_mode"])
    except StudioError as exc:
        if exc.code not in ("FILE_NOT_FOUND", "INVALID_IMAGE", "IMAGE_TOO_LARGE"):
            raise
        return {"passed": False, "errors": [exc.code], "warnings": [], "image": None}
    if report["image"]["sha256"] != asset["sha256"]:
        report["errors"].append("ASSET_CHANGED")
        report["passed"] = False
    return report


def add_asset(root: Path, image: Path, expression: str, prompt_file: Path | None = None,
              mouth_state: str = "default") -> dict:
    state = read_state(root)
    if expression not in EXPRESSIONS:
        raise StudioError("INVALID_EXPRESSION", "Unknown standard expression.")
    if mouth_state not in MOUTH_STATES:
        raise StudioError("INVALID_MOUTH_STATE", "Use default, closed, or open.")
    report = validate_image(image, state["canvas"], state["background_mode"])
    prompt = prompt_file.read_text(encoding="utf-8") if prompt_file else None
    slot = asset_slot({"expression": expression, "mouth_state": mouth_state})
    previous = [a for a in state["assets"] if asset_slot(a) == slot]
    version = max((a["version"] for a in previous), default=0) + 1
    while (root / "candidates" / f"{slot}_v{version:03d}.png").exists():
        version += 1
    asset_id = f"{slot}_v{version:03d}"
    relative = f"candidates/{asset_id}.png"
    if mouth_state != "default" and state["schema_version"] == "1.0":
        # Preserve legacy metadata before importing the first explicit state.
        backup = root / "run.schema-1.0.backup.json"
        if backup.exists():
            if backup.read_bytes() != (root / "run.json").read_bytes():
                raise StudioError("MIGRATION_BACKUP_EXISTS", "Existing backup differs from run.json; preserve it and resolve the interrupted upgrade first.")
        else:
            copy_exclusive(root / "run.json", backup)
        state["schema_version"] = "1.1"
    copy_exclusive(image, contained(root, relative))
    asset = {
        "id": asset_id, "expression": expression, "version": version, "path": relative,
        "parent_asset_id": max(previous, key=lambda item: item["version"])["id"] if previous else None,
        "origin": "source_reuse" if report["image"]["sha256"] == state["source_sha256"] else "generated",
        "sha256": report["image"]["sha256"],
        "technical_status": "passed" if report["passed"] else "failed",
        "art_review_status": "unreviewed", "validation": report,
        "model": "unknown", "created_at": timestamp(),
    }
    if mouth_state != "default":
        asset["mouth_state"] = mouth_state
    if prompt is not None:
        relative_prompt = f"candidates/{asset_id}.prompt.txt"
        with contained(root, relative_prompt).open("x", encoding="utf-8") as stream:
            stream.write(prompt)
        asset["prompt_path"] = relative_prompt
    state["assets"].append(asset)
    write_state(root, state)
    return {"asset": asset, "passed": report["passed"]}


def review_asset(root: Path, asset_id: str, status: str, note: str = "") -> dict:
    state = read_state(root)
    asset = get_asset(state, asset_id)
    if status not in ("accepted", "rejected"):
        raise StudioError("INVALID_REVIEW", "Review must be accepted or rejected.")
    report = check_asset(root, state, asset)
    if status == "accepted" and not report["passed"]:
        raise StudioError("TECHNICAL_CHECK_FAILED", ", ".join(report["errors"]))
    asset.update({"art_review_status": status, "review_note": note, "reviewed_at": timestamp(),
                  "validation": report, "technical_status": "passed" if report["passed"] else "failed"})
    if status == "accepted":
        state["selected"][asset_slot(asset)] = asset_id
    elif state["selected"].get(asset_slot(asset)) == asset_id:
        del state["selected"][asset_slot(asset)]
    write_state(root, state)
    return {"asset_id": asset_id, "art_review_status": status, "selected": state["selected"]}


def select_asset(root: Path, asset_id: str) -> dict:
    state = read_state(root)
    asset = get_asset(state, asset_id)
    if asset["art_review_status"] != "accepted":
        raise StudioError("ART_REVIEW_REQUIRED", "Only explicitly accepted versions can be selected.")
    report = check_asset(root, state, asset)
    if not report["passed"]:
        raise StudioError("TECHNICAL_CHECK_FAILED", ", ".join(report["errors"]))
    state["selected"][asset_slot(asset)] = asset_id
    write_state(root, state)
    return {"selected": state["selected"]}


def font(size: int) -> ImageFont.ImageFont:
    for name in ("C:/Windows/Fonts/msyh.ttc", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def backdrop(size: tuple[int, int], mode: str) -> Image.Image:
    if mode != "checker":
        return Image.new("RGBA", size, "#fafafa" if mode == "light" else "#242424")
    canvas = Image.new("RGBA", size, "#eeeeee")
    draw = ImageDraw.Draw(canvas)
    for y in range(0, size[1], 20):
        for x in range(0, size[0], 20):
            if (x // 20 + y // 20) % 2:
                draw.rectangle((x, y, x + 19, y + 19), fill="#d6d6d6")
    return canvas


def load_preview_labels(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    try:
        labels = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(labels, dict) or not all(
            isinstance(key, str) and isinstance(value, str) and value.strip()
            and len(value) <= 120 and "\n" not in value and "\r" not in value
            for key, value in labels.items()
        ):
            raise ValueError("Expected short, single-line label strings.")
        return labels
    except (OSError, ValueError) as exc:
        raise StudioError("INVALID_PREVIEW_LABELS", "Labels must be a UTF-8 JSON object with short string values.") from exc


def make_preview(root: Path, output: Path, ids: list[str] | None = None,
                 face_box: list[int] | None = None, background: str = "checker",
                 labels: dict[str, str] | None = None, expression: str | None = None,
                 mouth_state: str | None = None) -> dict:
    state = read_state(root)
    labels = labels or {}
    if expression is not None and expression not in EXPRESSIONS:
        raise StudioError("INVALID_EXPRESSION", "Unknown standard expression.")
    if mouth_state is not None and mouth_state not in MOUTH_STATES:
        raise StudioError("INVALID_MOUTH_STATE", "Use default, closed, or open.")
    assets = [get_asset(state, item) for item in ids] if ids is not None else state["assets"]
    assets = [a for a in assets if (expression is None or a["expression"] == expression)
              and (mouth_state is None or a.get("mouth_state", "default") == mouth_state)]
    if not assets and (ids is not None or expression is not None or mouth_state is not None):
        raise StudioError("NO_MATCHING_ASSETS", "No candidates match the preview selection.")
    if background not in ("checker", "light", "dark"):
        raise StudioError("INVALID_BACKGROUND_MODE", "Unknown preview background.")
    if face_box:
        left, top, right, bottom = face_box
        if not (0 <= left < right <= state["canvas"]["width"] and 0 <= top < bottom <= state["canvas"]["height"]):
            raise StudioError("INVALID_FACE_BOX", "Face box must be inside the source canvas.")
    entries = [{"id": "SOURCE", "path": state["source"], "art_review_status": "reference"}] + assets
    card_width, picture_height, label_height = 360, 420, 100
    face_height = 250 if face_box else 0
    card_height = picture_height + label_height + face_height
    columns = min(3, len(entries))
    sheet = Image.new("RGB", (columns * card_width, math.ceil(len(entries) / columns) * card_height), "#ffffff")
    for index, entry in enumerate(entries):
        x, y = (index % columns) * card_width, (index // columns) * card_height
        path = contained(root, entry["path"])
        report = check_asset(root, state, entry) if entry["id"] != "SOURCE" else None
        with Image.open(path) as source:
            source.load()
            rgba = source.convert("RGBA")
        # Preview-only scaling; candidate files and export pixels remain untouched.
        thumbnail = rgba.copy()
        thumbnail.thumbnail((card_width - 20, picture_height - 20), Image.Resampling.LANCZOS)
        panel = backdrop((card_width, picture_height), background)
        panel.alpha_composite(thumbnail, ((card_width - thumbnail.width) // 2, (picture_height - thumbnail.height) // 2))
        sheet.paste(panel.convert("RGB"), (x, y))
        draw = ImageDraw.Draw(sheet)
        title = entry["id"]
        if entry["id"] == "SOURCE":
            title = labels.get("source", title)
        elif entry.get("mouth_state", "default") != "default":
            mouth_key = f'mouth_{entry["mouth_state"]}'
            title = f'{labels.get(entry["expression"], entry["expression"])} / {labels.get(mouth_key, entry["mouth_state"])} v{entry["version"]:03d}'
        elif entry["expression"] in labels:
            title = f'{labels[entry["expression"]]} v{entry["version"]:03d}'
        title_line = f'{title} | {rgba.width} x {rgba.height}'
        title_font = font(17)
        for size in range(16, 9, -1):
            if draw.textlength(title_line, font=title_font) <= card_width - 20:
                break
            title_font = font(size)
        draw.text((x + 10, y + picture_height + 7), title_line, fill="#222222", font=title_font)
        label = labels.get(entry["art_review_status"], entry["art_review_status"])
        if report:
            status_key = "technical_passed" if report["passed"] else "technical_failed"
            default_status = "technical: passed" if report["passed"] else "technical: FAILED"
            label += " | " + labels.get(status_key, default_status)
        draw.text((x + 10, y + picture_height + 31), label, fill="#222222", font=font(15))
        if report and report["errors"]:
            draw.text((x + 10, y + picture_height + 56), ", ".join(labels.get(code, code) for code in report["errors"]), fill="#b42318", font=font(14))
        if face_box:
            sx, sy = rgba.width / state["canvas"]["width"], rgba.height / state["canvas"]["height"]
            box = [round(face_box[0] * sx), round(face_box[1] * sy), round(face_box[2] * sx), round(face_box[3] * sy)]
            face = rgba.crop(tuple(box))
            scale = min((card_width - 20) / face.width, (face_height - 20) / face.height)
            face = face.resize((max(1, round(face.width * scale)), max(1, round(face.height * scale))), Image.Resampling.LANCZOS)
            panel = backdrop((card_width, face_height), background)
            panel.alpha_composite(face, ((card_width - face.width) // 2, (face_height - face.height) // 2))
            sheet.paste(panel.convert("RGB"), (x, y + picture_height + label_height))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        sheet.save(stream, format="PNG")
    return {"preview": str(output.resolve()), "size": list(sheet.size), "face_box": face_box,
            "asset_ids": [a["id"] for a in assets],
            "note": "Preview is scaled for inspection; this does not correct candidate alignment or dimensions."}


def export_pack(root: Path, output: Path | None = None, ids: list[str] | None = None,
                preview: Path | None = None) -> dict:
    state = read_state(root)
    chosen = ids if ids is not None else list(state["selected"].values())
    if not chosen:
        raise StudioError("NO_SELECTED_ASSETS", "Accept and select at least one candidate before export.")
    seen, payloads, sprites = set(), {}, []
    has_mouth_states = any(get_asset(state, item).get("mouth_state", "default") != "default" for item in chosen)
    for asset_id in chosen:
        asset = get_asset(state, asset_id)
        expression = asset["expression"]
        slot = asset_slot(asset)
        if slot in seen:
            code = "DUPLICATE_EXPRESSION" if asset.get("mouth_state", "default") == "default" else "DUPLICATE_STATE"
            raise StudioError(code, "Choose exactly one version per expression and mouth state.")
        if asset["art_review_status"] != "accepted":
            raise StudioError("ART_REVIEW_REQUIRED", f"User has not accepted {asset_id}.")
        report = check_asset(root, state, asset)
        if not report["passed"]:
            raise StudioError("TECHNICAL_CHECK_FAILED", f'{asset_id}: {", ".join(report["errors"])}')
        data = contained(root, asset["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != asset["sha256"]:
            raise StudioError("ASSET_CHANGED", f"File changed during export: {asset_id}")
        archive_path = f'sprites/{state["character_key"]}/{slot}.png'
        payloads[archive_path] = data
        sprites.append({"expression": expression, "path": archive_path, "asset_id": asset_id,
                        "source_version": asset["version"], "sha256": asset["sha256"],
                        "technical_status": "passed", "art_review_status": "accepted"})
        if has_mouth_states:
            sprites[-1]["mouth_state"] = asset.get("mouth_state", "default")
        seen.add(slot)
    manifest = {"schema_version": "1.1" if has_mouth_states else "1.0", "character_key": state["character_key"],
                "asset_kind": "full_character_expression", "background_mode": state["background_mode"],
                "canvas": state["canvas"], "sprites": sprites}
    payloads["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if preview:
        if image_info(preview)["format"] != "PNG":
            raise StudioError("INVALID_PREVIEW", "Preview must be a PNG.")
        payloads["preview/contact-sheet.png"] = preview.read_bytes()
    if output is None:
        version = 1
        output = root / "exports" / f'{state["character_key"]}-expressions-v{version:03d}.zip'
        while output.exists():
            version += 1
            output = output.with_name(f'{state["character_key"]}-expressions-v{version:03d}.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in payloads.items():
                archive.writestr(name, data)
    return {"export": str(output.resolve()), "asset_ids": chosen, "manifest": manifest}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("presets", help="List supported expression IDs and starting directions; no project required.")
    inspect = commands.add_parser("inspect", help="Inspect a PNG/JPEG without editing it.")
    inspect.add_argument("image", type=Path)
    validate = commands.add_parser("validate", help="Check a candidate against its source canvas.")
    validate.add_argument("--source", required=True, type=Path)
    validate.add_argument("--image", required=True, type=Path)
    validate.add_argument("--background", choices=MODES, required=True)
    for name in ("init", "add", "status", "review", "select", "preview", "export"):
        command = commands.add_parser(name)
        command.add_argument("--project", required=True, type=Path)
        if name == "init":
            command.add_argument("--source", required=True, type=Path)
            command.add_argument("--character", required=True)
            command.add_argument("--background", choices=("auto",) + MODES, default="auto")
        elif name == "add":
            command.add_argument("--image", required=True, type=Path)
            command.add_argument("--expression", choices=EXPRESSIONS, required=True)
            command.add_argument("--mouth-state", choices=MOUTH_STATES, default="default")
            command.add_argument("--prompt-file", type=Path)
        elif name in ("review", "select"):
            command.add_argument("--asset", required=True)
            if name == "review":
                command.add_argument("--status", choices=("accepted", "rejected"), required=True)
                command.add_argument("--note", default="")
        elif name in ("preview", "export"):
            command.add_argument("--asset", action="append", dest="ids")
            command.add_argument("--output", required=name == "preview", type=Path)
            if name == "preview":
                command.add_argument("--expression", choices=EXPRESSIONS, help="Show only this expression, retaining all versions and mouth states.")
                command.add_argument("--mouth-state", choices=MOUTH_STATES, help="Show only this mouth state.")
                command.add_argument("--face-box", type=int, nargs=4)
                command.add_argument("--background", choices=("checker", "light", "dark"), default="checker")
                command.add_argument("--labels-file", type=Path, help="UTF-8 JSON label overrides in the user's language.")
            else:
                command.add_argument("--preview", type=Path)
    return result


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    try:
        if args.command == "presets":
            result = {"presets": [{"id": key, **preset} for key, preset in EXPRESSION_PRESETS.items()],
                      "mouth_states": [{"id": key, **preset} for key, preset in MOUTH_PRESETS.items()]}
        elif args.command == "inspect":
            result = image_info(args.image)
        elif args.command == "validate":
            source = image_info(args.source)
            result = validate_image(args.image, source, args.background)
        elif args.command == "init":
            result = init_project(args.project, args.source, args.character, args.background)
        elif args.command == "add":
            result = add_asset(args.project, args.image, args.expression, args.prompt_file, args.mouth_state)
        elif args.command == "status":
            state = read_state(args.project)
            result = {"canvas": state["canvas"], "background_mode": state["background_mode"],
                      "selected": state["selected"], "assets": [
                          {**asset, "current_validation": check_asset(args.project, state, asset)} for asset in state["assets"]]}
        elif args.command == "review":
            result = review_asset(args.project, args.asset, args.status, args.note)
        elif args.command == "select":
            result = select_asset(args.project, args.asset)
        elif args.command == "preview":
            result = make_preview(args.project, args.output, args.ids, args.face_box, args.background,
                                  load_preview_labels(args.labels_file), args.expression, args.mouth_state)
        else:
            result = export_pack(args.project, args.output, args.ids, args.preview)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("passed", True) else 2
    except StudioError as exc:
        error = {"code": exc.code, "message": exc.message}
    except FileExistsError:
        error = {"code": "OUTPUT_EXISTS", "message": "Output already exists; choose a new filename."}
    except OSError as exc:
        error = {"code": "FILE_OPERATION_FAILED", "message": str(exc)}
    print(json.dumps({"error": error}, ensure_ascii=False), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
