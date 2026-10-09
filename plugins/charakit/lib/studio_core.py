"""Shared local file workflow for CharaKit. Never generates or retouches art."""
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
    if "outfit_id" in asset:
        return asset["outfit_id"]
    mouth = asset.get("mouth_state", "default")
    return asset["expression"] if mouth == "default" else f'{asset["expression"]}_mouth_{mouth}'


def read_state(root: Path) -> dict:
    def require(condition: bool) -> None:
        if not condition:
            raise ValueError("Invalid project metadata.")

    try:
        state = json.loads((root / "run.json").read_text(encoding="utf-8"))
        require(state["schema_version"] in ("1.0", "1.1", "1.2"))
        module = state.get("module", "expressions")
        require(module in ("expressions", "outfits"))
        require((module == "outfits") == (state["schema_version"] == "1.2"))
        require(bool(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", state["character_key"])))
        require(state["background_mode"] in MODES)
        require(isinstance(state["assets"], list) and isinstance(state["selected"], dict))
        for dimension in ("width", "height"):
            require(type(state["canvas"][dimension]) is int and state["canvas"][dimension] > 0)
        ids = set()
        outfit_targets = {}
        for asset in state["assets"]:
            if module == "outfits":
                require("expression" not in asset and "mouth_state" not in asset)
                require(valid_outfit_id(asset["outfit_id"]))
                require(asset["edit_type"] == "recolor")
                require(valid_edit_text(asset["target"], 200) and valid_edit_text(asset["color"], 120))
                definition = (asset["target"], asset["color"])
                require(outfit_targets.setdefault(asset["outfit_id"], definition) == definition)
                if "edit_brief" in asset:
                    try:
                        validate_edit_brief(root, state, asset["edit_brief"], check_reference=False)
                    except StudioError as exc:
                        raise ValueError("Invalid edit brief.") from exc
                    require(all(asset["edit_brief"][key] == asset[key] for key in ("outfit_id", "target", "color")))
                if "fidelity_review" in asset:
                    review = asset["fidelity_review"]
                    require(isinstance(review, dict))
                    require(review["target_check"] in FIDELITY_CHECKS and review["protection_check"] in FIDELITY_CHECKS)
                    require(review["basis"] in ("assistant", "user") and valid_edit_text(review["note"], 1000))
                    require(review["asset_sha256"] == asset["sha256"] and review["source_sha256"] == state["source_sha256"])
            else:
                require("outfit_id" not in asset)
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


def valid_outfit_id(value) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value))


def valid_edit_text(value, limit: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and len(value) <= limit and not any(ord(c) < 32 for c in value)


def require_module(state: dict, module: str) -> None:
    if state.get("module", "expressions") != module:
        raise StudioError("WRONG_MODULE", f"Use a separate {module} project; this project belongs to another module.")


FIDELITY_CHECKS = ("passed", "failed", "uncertain")


def valid_source_box(box, canvas: dict) -> bool:
    return (isinstance(box, list) and len(box) == 4 and all(type(n) is int for n in box)
            and 0 <= box[0] < box[2] <= canvas["width"]
            and 0 <= box[1] < box[3] <= canvas["height"])


def validate_edit_brief(root: Path, state: dict, brief: dict, check_reference: bool = True) -> None:
    try:
        valid = (isinstance(brief, dict) and brief["schema_version"] == "1.0"
                 and brief["source_sha256"] == state["source_sha256"]
                 and valid_outfit_id(brief["outfit_id"])
                 and valid_edit_text(brief["target"], 200) and valid_edit_text(brief["color"], 120)
                 and valid_edit_text(brief["boundary"], 1000)
                 and isinstance(brief["protected_regions"], list) and 1 <= len(brief["protected_regions"]) <= 20
                 and all(valid_edit_text(region, 200) for region in brief["protected_regions"])
                 and valid_source_box(brief["target_box"], state["canvas"]))
        if not valid:
            raise ValueError("Invalid scope.")
        reference = contained(root, brief["reference"]["path"])
        if not re.fullmatch(r"[0-9a-f]{64}", brief["reference"]["sha256"]):
            raise ValueError("Invalid reference fingerprint.")
    except (KeyError, TypeError, ValueError) as exc:
        raise StudioError("INVALID_EDIT_BRIEF", "Use a prepared brief with source coordinates, boundary, and protected regions.") from exc
    if check_reference and (not reference.is_file() or digest(reference) != brief["reference"]["sha256"]):
        raise StudioError("REFERENCE_CHANGED", "The source detail reference is missing or changed; prepare a new brief.")


def prepare_outfit(root: Path, outfit_id: str, target: str, color: str, boundary: str,
                   protected_regions: list[str], target_box: list[int]) -> dict:
    """Save a scope brief and source-only detail reference; never edits a candidate."""
    state = read_state(root)
    require_module(state, "outfits")
    if not valid_outfit_id(outfit_id):
        raise StudioError("INVALID_OUTFIT_ID", "Use a lowercase filename key.")
    if not (valid_edit_text(target, 200) and valid_edit_text(color, 120)
            and valid_edit_text(boundary, 1000) and isinstance(protected_regions, list)
            and 1 <= len(protected_regions) <= 20
            and all(valid_edit_text(region, 200) for region in protected_regions)):
        raise StudioError("INVALID_EDIT_BRIEF", "Specify a garment, color, boundary, and protected regions as short text.")
    if not valid_source_box(target_box, state["canvas"]):
        raise StudioError("INVALID_TARGET_BOX", "Target detail box must be inside the source canvas.")
    if any((a["target"], a["color"]) != (target, color) for a in state["assets"] if a["outfit_id"] == outfit_id):
        raise StudioError("OUTFIT_DEFINITION_CHANGED", "Use a new outfit ID when changing the garment or requested color.")
    version = 1
    while True:
        brief_path = root / "briefs" / f"{outfit_id}_v{version:03d}.json"
        reference_path = root / "references" / f"{outfit_id}_target_v{version:03d}.png"
        if not brief_path.exists() and not reference_path.exists():
            break
        version += 1
    with Image.open(contained(root, state["source"])) as source:
        source.load()
        detail = source.convert("RGBA").crop(tuple(target_box))
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    with reference_path.open("xb") as stream:
        detail.save(stream, format="PNG")
    brief = {"schema_version": "1.0", "outfit_id": outfit_id, "target": target, "color": color,
             "boundary": boundary, "protected_regions": protected_regions, "target_box": target_box,
             "source_sha256": state["source_sha256"],
             "reference": {"path": reference_path.relative_to(root).as_posix(), "sha256": digest(reference_path)},
             "created_at": timestamp()}
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    with brief_path.open("x", encoding="utf-8") as stream:
        json.dump(brief, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"brief_file": str(brief_path.resolve()), "source_reference": str(contained(root, state["source"])),
            "detail_reference": str(reference_path.resolve()), "edit_brief": brief,
            "note": "Detail reference identifies the target; it is not an edit mask or a final asset. Use the full source as the primary reference."}


def fidelity_status(asset: dict) -> str:
    review = asset.get("fidelity_review")
    if review is None:
        return "pending" if "edit_brief" in asset else "unrecorded"
    if "failed" in (review["target_check"], review["protection_check"]):
        return "failed"
    return "passed" if review["target_check"] == review["protection_check"] == "passed" else "uncertain"


def require_fidelity(asset: dict) -> None:
    status = fidelity_status(asset)
    if status not in ("passed", "unrecorded"):
        code = "FIDELITY_REVIEW_REQUIRED" if status == "pending" else "FIDELITY_CHECK_FAILED"
        raise StudioError(code, f'{asset["id"]}: inspect the target and protected regions before accepting, selecting, or exporting.')


def record_fidelity(root: Path, asset_id: str, target_check: str, protection_check: str,
                    note: str, basis: str = "assistant") -> dict:
    state = read_state(root)
    require_module(state, "outfits")
    asset = get_asset(state, asset_id)
    if (target_check not in FIDELITY_CHECKS or protection_check not in FIDELITY_CHECKS
            or basis not in ("assistant", "user") or not valid_edit_text(note, 1000)):
        raise StudioError("INVALID_FIDELITY_REVIEW", "Record observed target/protection results, their basis, and a short factual note.")
    report = check_asset(root, state, asset)
    if report["image"] is None or "ASSET_CHANGED" in report["errors"]:
        raise StudioError("TECHNICAL_CHECK_FAILED", ", ".join(report["errors"]))
    asset["fidelity_review"] = {"target_check": target_check, "protection_check": protection_check,
                                "basis": basis, "note": note, "checked_at": timestamp(),
                                "asset_sha256": asset["sha256"], "source_sha256": state["source_sha256"]}
    if fidelity_status(asset) != "passed" and state["selected"].get(asset_slot(asset)) == asset_id:
        del state["selected"][asset_slot(asset)]
    write_state(root, state)
    return {"asset_id": asset_id, "fidelity_status": fidelity_status(asset),
            "fidelity_review": asset["fidelity_review"], "art_review_status": asset["art_review_status"],
            "technical_passed": report["passed"], "selected": state["selected"]}


def init_project(root: Path, source: Path, character: str, mode: str = "auto",
                 module: str = "expressions") -> dict:
    if module not in ("expressions", "outfits"):
        raise StudioError("INVALID_MODULE", "Use expressions or outfits.")
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
    if module == "outfits":
        state.update({"schema_version": "1.2", "module": "outfits"})
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
    require_module(state, "expressions")
    if expression not in EXPRESSIONS:
        raise StudioError("INVALID_EXPRESSION", "Unknown standard expression.")
    if mouth_state not in MOUTH_STATES:
        raise StudioError("INVALID_MOUTH_STATE", "Use default, closed, or open.")
    report = validate_image(image, state["canvas"], state["background_mode"])
    prompt = prompt_file.read_text(encoding="utf-8") if prompt_file else None
    if mouth_state != "default" and state["schema_version"] == "1.0":
        # Preserve legacy metadata before importing the first explicit state.
        backup = root / "run.schema-1.0.backup.json"
        if backup.exists():
            if backup.read_bytes() != (root / "run.json").read_bytes():
                raise StudioError("MIGRATION_BACKUP_EXISTS", "Existing backup differs from run.json; preserve it and resolve the interrupted upgrade first.")
        else:
            copy_exclusive(root / "run.json", backup)
        state["schema_version"] = "1.1"
    fields = {"expression": expression}
    if mouth_state != "default":
        fields["mouth_state"] = mouth_state
    return save_candidate(root, state, image, fields, report, prompt)


def add_outfit(root: Path, image: Path, outfit_id: str, target: str, color: str,
               prompt_file: Path | None = None, brief_file: Path | None = None) -> dict:
    state = read_state(root)
    require_module(state, "outfits")
    if not valid_outfit_id(outfit_id):
        raise StudioError("INVALID_OUTFIT_ID", "Use a lowercase filename key, e.g. coat_navy.")
    if not isinstance(target, str) or not isinstance(color, str):
        raise StudioError("INVALID_RECOLOR", "Specify one garment target and its color as text.")
    target, color = target.strip(), color.strip()
    if not valid_edit_text(target, 200) or not valid_edit_text(color, 120):
        raise StudioError("INVALID_RECOLOR", "Specify one garment target and its color as short single-line text.")
    previous = [a for a in state["assets"] if a["outfit_id"] == outfit_id]
    if any((a["target"], a["color"]) != (target, color) for a in previous):
        raise StudioError("OUTFIT_DEFINITION_CHANGED", "Use a new outfit ID when changing the garment or requested color.")
    report = validate_image(image, state["canvas"], state["background_mode"])
    prompt = prompt_file.read_text(encoding="utf-8") if prompt_file else None
    fields = {"outfit_id": outfit_id, "edit_type": "recolor", "target": target, "color": color}
    inherited = next((a["edit_brief"] for a in sorted(previous, key=lambda a: a["version"], reverse=True) if "edit_brief" in a), None)
    if brief_file is not None or inherited is not None:
        try:
            brief = json.loads(brief_file.read_text(encoding="utf-8")) if brief_file is not None else inherited
        except (OSError, ValueError) as exc:
            raise StudioError("INVALID_EDIT_BRIEF", "Cannot read the prepared brief.") from exc
        validate_edit_brief(root, state, brief)
        if any(brief[key] != fields[key] for key in ("outfit_id", "target", "color")):
            raise StudioError("INVALID_EDIT_BRIEF", "The brief must match this outfit option, garment, and color.")
        fields["edit_brief"] = brief
    return save_candidate(root, state, image, fields, report, prompt)


def save_candidate(root: Path, state: dict, image: Path, fields: dict, report: dict,
                   prompt: str | None) -> dict:
    slot = asset_slot(fields)
    previous = [a for a in state["assets"] if asset_slot(a) == slot]
    version = max((a["version"] for a in previous), default=0) + 1
    while (root / "candidates" / f"{slot}_v{version:03d}.png").exists() or (root / "candidates" / f"{slot}_v{version:03d}.prompt.txt").exists():
        version += 1
    asset_id = f"{slot}_v{version:03d}"
    relative = f"candidates/{asset_id}.png"
    copy_exclusive(image, contained(root, relative))
    asset = {
        **fields, "id": asset_id, "version": version, "path": relative,
        "parent_asset_id": max(previous, key=lambda item: item["version"])["id"] if previous else None,
        "origin": "source_reuse" if report["image"]["sha256"] == state["source_sha256"] else "generated",
        "sha256": report["image"]["sha256"],
        "technical_status": "passed" if report["passed"] else "failed",
        "art_review_status": "unreviewed", "validation": report,
        "model": "unknown", "created_at": timestamp(),
    }
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
    if status == "accepted":
        require_fidelity(asset)
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
    require_fidelity(asset)
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
                 mouth_state: str | None = None, outfit_id: str | None = None,
                 detail_box: list[int] | None = None) -> dict:
    state = read_state(root)
    labels = labels or {}
    if outfit_id is not None:
        require_module(state, "outfits")
        if not valid_outfit_id(outfit_id):
            raise StudioError("INVALID_OUTFIT_ID", "Use a lowercase filename key.")
    if expression is not None or mouth_state is not None:
        require_module(state, "expressions")
    if expression is not None and expression not in EXPRESSIONS:
        raise StudioError("INVALID_EXPRESSION", "Unknown standard expression.")
    if mouth_state is not None and mouth_state not in MOUTH_STATES:
        raise StudioError("INVALID_MOUTH_STATE", "Use default, closed, or open.")
    assets = [get_asset(state, item) for item in ids] if ids is not None else state["assets"]
    assets = [a for a in assets if (expression is None or a["expression"] == expression)
              and (mouth_state is None or a.get("mouth_state", "default") == mouth_state)]
    if outfit_id is not None:
        assets = [a for a in assets if a["outfit_id"] == outfit_id]
    if not assets and (ids is not None or expression is not None or mouth_state is not None or outfit_id is not None):
        raise StudioError("NO_MATCHING_ASSETS", "No candidates match the preview selection.")
    if background not in ("checker", "light", "dark"):
        raise StudioError("INVALID_BACKGROUND_MODE", "Unknown preview background.")
    if face_box:
        left, top, right, bottom = face_box
        if not (0 <= left < right <= state["canvas"]["width"] and 0 <= top < bottom <= state["canvas"]["height"]):
            raise StudioError("INVALID_FACE_BOX", "Face box must be inside the source canvas.")
    if detail_box:
        left, top, right, bottom = detail_box
        if not (0 <= left < right <= state["canvas"]["width"] and 0 <= top < bottom <= state["canvas"]["height"]):
            raise StudioError("INVALID_DETAIL_BOX", "Detail box must be inside the source canvas.")
    entries = [{"id": "SOURCE", "path": state["source"], "art_review_status": "reference"}] + assets
    card_width, picture_height, label_height = 360, 420, 100
    face_height = 250 if face_box else 0
    detail_height = 250 if detail_box else 0
    card_height = picture_height + label_height + face_height + detail_height
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
        elif "outfit_id" in entry:
            title = f'{labels.get(entry["outfit_id"], entry["outfit_id"])} v{entry["version"]:03d}'
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
        if entry["id"] != "SOURCE" and ("edit_brief" in entry or "fidelity_review" in entry):
            status = fidelity_status(entry)
            draw.text((x + 10, y + picture_height + 78), labels.get(f"fidelity_{status}", f"fidelity: {status}"),
                      fill="#267048" if status == "passed" else "#b45309", font=font(14))
        for box_coords, offset in ((face_box, 0), (detail_box, face_height)):
            if not box_coords:
                continue
            sx, sy = rgba.width / state["canvas"]["width"], rgba.height / state["canvas"]["height"]
            box = [round(box_coords[0] * sx), round(box_coords[1] * sy), round(box_coords[2] * sx), round(box_coords[3] * sy)]
            face = rgba.crop(tuple(box))
            scale = min((card_width - 20) / face.width, 230 / face.height)
            face = face.resize((max(1, round(face.width * scale)), max(1, round(face.height * scale))), Image.Resampling.LANCZOS)
            panel = backdrop((card_width, 250), background)
            panel.alpha_composite(face, ((card_width - face.width) // 2, (250 - face.height) // 2))
            sheet.paste(panel.convert("RGB"), (x, y + picture_height + label_height + offset))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        sheet.save(stream, format="PNG")
    return {"preview": str(output.resolve()), "size": list(sheet.size), "face_box": face_box,
            "detail_box": detail_box,
            "asset_ids": [a["id"] for a in assets],
            "note": "Preview is scaled for inspection; this does not correct candidate alignment or dimensions."}


def export_pack(root: Path, output: Path | None = None, ids: list[str] | None = None,
                preview: Path | None = None) -> dict:
    state = read_state(root)
    is_outfit = state.get("module", "expressions") == "outfits"
    chosen = ids if ids is not None else list(state["selected"].values())
    if not chosen:
        raise StudioError("NO_SELECTED_ASSETS", "Accept and select at least one candidate before export.")
    seen, payloads, sprites = set(), {}, []
    has_mouth_states = any(get_asset(state, item).get("mouth_state", "default") != "default" for item in chosen)
    for asset_id in chosen:
        asset = get_asset(state, asset_id)
        slot = asset_slot(asset)
        if slot in seen:
            code = "DUPLICATE_OUTFIT" if is_outfit else ("DUPLICATE_EXPRESSION" if asset.get("mouth_state", "default") == "default" else "DUPLICATE_STATE")
            raise StudioError(code, "Choose exactly one version per resource.")
        if asset["art_review_status"] != "accepted":
            raise StudioError("ART_REVIEW_REQUIRED", f"User has not accepted {asset_id}.")
        report = check_asset(root, state, asset)
        if not report["passed"]:
            raise StudioError("TECHNICAL_CHECK_FAILED", f'{asset_id}: {", ".join(report["errors"])}')
        require_fidelity(asset)
        data = contained(root, asset["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != asset["sha256"]:
            raise StudioError("ASSET_CHANGED", f"File changed during export: {asset_id}")
        archive_path = f'sprites/{state["character_key"]}/' + (f'outfits/{slot}.png' if is_outfit else f'{slot}.png')
        payloads[archive_path] = data
        sprites.append({"path": archive_path, "asset_id": asset_id,
                        "source_version": asset["version"], "sha256": asset["sha256"],
                        "technical_status": "passed", "art_review_status": "accepted"})
        if is_outfit:
            sprites[-1].update({key: asset[key] for key in ("outfit_id", "edit_type", "target", "color")})
            if "edit_brief" in asset:
                sprites[-1]["edit_scope"] = {key: asset["edit_brief"][key] for key in ("boundary", "protected_regions", "target_box")}
            if "fidelity_review" in asset:
                sprites[-1]["fidelity_review"] = asset["fidelity_review"]
        else:
            sprites[-1]["expression"] = asset["expression"]
        if has_mouth_states:
            sprites[-1]["mouth_state"] = asset.get("mouth_state", "default")
        seen.add(slot)
    manifest = {"schema_version": "1.2" if is_outfit else ("1.1" if has_mouth_states else "1.0"), "character_key": state["character_key"],
                "asset_kind": "full_character_outfit" if is_outfit else "full_character_expression", "background_mode": state["background_mode"],
                "canvas": state["canvas"], "sprites": sprites}
    payloads["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if preview:
        if image_info(preview)["format"] != "PNG":
            raise StudioError("INVALID_PREVIEW", "Preview must be a PNG.")
        payloads["preview/contact-sheet.png"] = preview.read_bytes()
    if output is None:
        version = 1
        suffix = "outfits" if is_outfit else "expressions"
        output = root / "exports" / f'{state["character_key"]}-{suffix}-v{version:03d}.zip'
        while output.exists():
            version += 1
            output = output.with_name(f'{state["character_key"]}-{suffix}-v{version:03d}.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in payloads.items():
                archive.writestr(name, data)
    return {"export": str(output.resolve()), "asset_ids": chosen, "manifest": manifest}


def parser(module: str = "expressions") -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    if module == "expressions":
        commands.add_parser("presets", help="List supported expression IDs and starting directions; no project required.")
    if module == "outfits":
        prepare = commands.add_parser("prepare", help="Save edit boundaries and a source-only detail reference; does not generate art.")
        prepare.add_argument("--project", required=True, type=Path)
        prepare.add_argument("--outfit", required=True, dest="outfit_id")
        prepare.add_argument("--target", required=True)
        prepare.add_argument("--color", required=True)
        prepare.add_argument("--boundary", required=True)
        prepare.add_argument("--protect", required=True, action="append", dest="protected_regions")
        prepare.add_argument("--target-box", required=True, nargs=4, type=int)
        fidelity = commands.add_parser("fidelity", help="Record manual target/protection observations separately from user acceptance.")
        fidelity.add_argument("--project", required=True, type=Path)
        fidelity.add_argument("--asset", required=True)
        fidelity.add_argument("--target-check", required=True, choices=FIDELITY_CHECKS)
        fidelity.add_argument("--protection-check", required=True, choices=FIDELITY_CHECKS)
        fidelity.add_argument("--note", required=True)
        fidelity.add_argument("--basis", choices=("assistant", "user"), default="assistant")
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
            if module == "outfits":
                command.add_argument("--outfit", required=True, dest="outfit_id")
                command.add_argument("--target", required=True, help="One garment to recolor, in the user's language.")
                command.add_argument("--color", required=True, help="Requested color, in the user's language.")
                command.add_argument("--brief-file", type=Path, help="Prepared edit brief to snapshot with this candidate.")
            else:
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
                if module == "outfits":
                    command.add_argument("--outfit", dest="outfit_id", help="Compare versions of one recolor option.")
                    command.add_argument("--detail-box", type=int, nargs=4, help="Source coordinates of the garment inspection region.")
                else:
                    command.add_argument("--expression", choices=EXPRESSIONS, help="Show only this expression, retaining all versions and mouth states.")
                    command.add_argument("--mouth-state", choices=MOUTH_STATES, help="Show only this mouth state.")
                command.add_argument("--face-box", type=int, nargs=4)
                command.add_argument("--background", choices=("checker", "light", "dark"), default="checker")
                command.add_argument("--labels-file", type=Path, help="UTF-8 JSON label overrides in the user's language.")
            else:
                command.add_argument("--preview", type=Path)
    return result


def main(module: str = "expressions") -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser(module).parse_args()
    try:
        if args.command in ("add", "status", "review", "select", "preview", "export", "prepare", "fidelity"):
            require_module(read_state(args.project), module)
        if args.command == "presets":
            result = {"presets": [{"id": key, **preset} for key, preset in EXPRESSION_PRESETS.items()],
                      "mouth_states": [{"id": key, **preset} for key, preset in MOUTH_PRESETS.items()]}
        elif args.command == "inspect":
            result = image_info(args.image)
        elif args.command == "validate":
            source = image_info(args.source)
            result = validate_image(args.image, source, args.background)
        elif args.command == "init":
            result = init_project(args.project, args.source, args.character, args.background, module)
        elif args.command == "prepare":
            result = prepare_outfit(args.project, args.outfit_id, args.target, args.color, args.boundary, args.protected_regions, args.target_box)
        elif args.command == "fidelity":
            result = record_fidelity(args.project, args.asset, args.target_check, args.protection_check, args.note, args.basis)
        elif args.command == "add":
            if module == "outfits":
                result = add_outfit(args.project, args.image, args.outfit_id, args.target, args.color, args.prompt_file, args.brief_file)
            else:
                result = add_asset(args.project, args.image, args.expression, args.prompt_file, args.mouth_state)
        elif args.command == "status":
            state = read_state(args.project)
            result = {"canvas": state["canvas"], "background_mode": state["background_mode"],
                      "selected": state["selected"], "assets": [
                          {**asset, "current_validation": check_asset(args.project, state, asset),
                           **({"fidelity_status": fidelity_status(asset)} if module == "outfits" else {})} for asset in state["assets"]]}
        elif args.command == "review":
            result = review_asset(args.project, args.asset, args.status, args.note)
        elif args.command == "select":
            result = select_asset(args.project, args.asset)
        elif args.command == "preview":
            result = make_preview(args.project, args.output, args.ids, args.face_box, args.background,
                                  load_preview_labels(args.labels_file), getattr(args, "expression", None),
                                  getattr(args, "mouth_state", None), getattr(args, "outfit_id", None), getattr(args, "detail_box", None))
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
