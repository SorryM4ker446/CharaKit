"""Immutable, scoped reference inputs shared by implemented editing modules."""
import copy
import json
from pathlib import Path
import re


def require(c, condition, message, code="INVALID_EDIT_REFERENCES"):
    if not condition:
        raise c.StudioError(code, message)


def valid(c, records):
    return (isinstance(records, list) and 1 <= len(records) <= 3
            and all(isinstance(r, dict) and set(r) == {"id", "path", "sha256", "role", "scope", "notes"}
                    and c.valid_outfit_id(r["id"]) and isinstance(r["path"], str) and bool(r["path"])
                    and not Path(r["path"]).is_absolute() and ".." not in Path(r["path"]).parts
                    and r["role"] == "edit_reference" and isinstance(r["sha256"], str)
                    and bool(re.fullmatch(r"[0-9a-f]{64}", r["sha256"]))
                    and isinstance(r["scope"], list) and 1 <= len(r["scope"]) <= 12
                    and all(c.valid_outfit_id(s) for s in r["scope"])
                    and len(set(r["scope"])) == len(r["scope"])
                    and c.valid_edit_text(r["notes"], 1000) for r in records)
            and len({r["id"] for r in records}) == len(records)
            and len({r["sha256"] for r in records}) == len(records))


def allowed_scopes(asset):
    if "outfit_id" in asset:
        return {x["id"] for x in asset["outfit_components"]} if asset.get("edit_type") == "outfit_replace" else {"target"}
    return {"expression", "mouth"} if asset.get("mouth_state", "default") != "default" else {"expression"}


def validate(c, records, asset):
    require(c, valid(c, records), "Use prepared, uniquely identified reference images with explicit editable scopes and notes.")
    require(c, all(set(r["scope"]) <= allowed_scopes(asset) for r in records),
            "Reference scopes must name editable components; they cannot authorize protected regions.")


def check_files(c, root, records):
    for ref in records:
        path = c.contained(root, ref["path"])
        require(c, path.is_file() and c.digest(path) == ref["sha256"],
                "A saved edit reference is missing or changed; restore its original bytes.", "EDIT_REFERENCE_CHANGED")


def prepare(c, root, input_file):
    """Snapshot all inputs only after validating the complete list; never edit run.json."""
    state = c.read_state(root)
    try:
        data = json.loads(input_file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise c.StudioError("INVALID_EDIT_REFERENCES", "Cannot read the reference input JSON.") from exc
    require(c, isinstance(data, list) and 1 <= len(data) <= 3, "Supply one to three focused reference images.")
    records, paths = [], []
    for item in data:
        require(c, isinstance(item, dict) and set(item) == {"id", "path", "scope", "notes"}
                and isinstance(item["path"], str) and bool(item["path"]), "Each input needs id, path, scope and notes.")
        path = Path(item["path"])
        path = path if path.is_absolute() else input_file.resolve().parent / path
        info = c.image_info(path)
        require(c, info["format"] in ("PNG", "JPEG", "WEBP") and info["alpha_range"][1] > 0,
                "Reference images must be readable, nonempty PNG, JPEG or WebP images.")
        suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[info["format"]]
        records.append({"id": item["id"], "path": f'references/inputs/{item["id"]}-{info["sha256"]}{suffix}',
                        "sha256": info["sha256"], "role": "edit_reference", "scope": item["scope"], "notes": item["notes"]})
        paths.append(path)
    require(c, valid(c, records), "Invalid or duplicate reference IDs/images/scopes/notes.")
    require(c, all(r["sha256"] != state["source_sha256"] for r in records), "The immutable source is already a separate input.")
    payload = {"version": "1.0", "module": state.get("module", "expressions"),
               "source_sha256": state["source_sha256"], "edit_references": records}
    # Check all existing destinations before copying any new reference.
    for ref in records:
        target = c.contained(root, ref["path"])
        require(c, not target.exists() or (target.is_file() and c.digest(target) == ref["sha256"]),
                "Existing reference snapshot changed.", "EDIT_REFERENCE_CHANGED")
    for ref, path in zip(records, paths):
        target = c.contained(root, ref["path"])
        if not target.exists():
            c.copy_exclusive(path, target)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    key = c.hashlib.sha256(encoded).hexdigest()
    destination = root / "references" / f"set-{key}.json"
    require(c, not destination.exists() or destination.read_bytes() == encoded, "Existing reference manifest changed.", "EDIT_REFERENCE_CHANGED")
    if not destination.exists():
        with destination.open("xb") as stream:
            stream.write(encoded)
    refs = bindings(c, root, state, {"edit_references": records})
    return {"reference_file": str(destination.resolve()), "edit_references": records, "references": refs,
            "reference_paths": [str(c.contained(root, r["path"])) for r in refs],
            "note": "The source controls identity, pose, style and framing; each other image supplies only its recorded editable scope."}


def load(c, root, state, manifest, asset):
    try:
        path = manifest.resolve()
        require(c, path.is_relative_to(root.resolve()), "Use the prepared in-project reference manifest.")
        data = json.loads(path.read_text(encoding="utf-8"))
        require(c, data["version"] == "1.0" and data["module"] == state.get("module", "expressions")
                and data["source_sha256"] == state["source_sha256"], "References belong to another source or module.")
        records = data["edit_references"]
        validate(c, records, asset)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise c.StudioError("INVALID_EDIT_REFERENCES", "Cannot read the matching prepared reference manifest.") from exc
    check_files(c, root, records)
    return copy.deepcopy(records)


def bindings(c, root, state, asset, parent=None, parent_first=False):
    refs = [{"path": state["source"], "sha256": state["source_sha256"], "role": "immutable_source"}]
    if parent is not None:
        refs.append({"path": parent["path"], "sha256": parent["sha256"], "role": "edit_target"})
        if parent_first:
            refs.reverse()
    records = asset.get("edit_references", [])
    check_files(c, root, records)
    return refs + copy.deepcopy(records)


def initial_inputs(c, root, state, fields, submitted):
    expected = bindings(c, root, state, fields)
    require(c, submitted is not None and [p.resolve() for p in submitted] == [c.contained(root, r["path"]) for r in expected],
            "Record the actual inputs: immutable source first, then all prepared edit references in order.", "INVALID_GENERATION_REFERENCES")
    return {"strategy": "source_sample", "references": expected}


def validate_asset(c, root, state, asset):
    if "edit_references" not in asset:
        return
    validate(c, asset["edit_references"], asset)
    inputs = asset.get("generation_inputs", {})
    require(c, inputs.get("strategy") in ("source_sample", "review_redraw", "user_revision"), "Record reference-aware generation provenance.")
    parent = next((a for a in state["assets"] if a["id"] == asset.get("parent_asset_id")), None) if inputs["strategy"] != "source_sample" else None
    require(c, inputs["strategy"] == "source_sample" or parent is not None, "A redraw/revision needs its recorded parent.")
    # Structural verification only; missing/changed files produce a recoverable stale gate.
    expected = [{"path": state["source"], "sha256": state["source_sha256"], "role": "immutable_source"}]
    if parent:
        require(c, parent.get("edit_references") == asset["edit_references"], "Revisions retain reference scope and notes.")
        expected.append({"path": parent["path"], "sha256": parent["sha256"], "role": "edit_target"})
    policy = state.get('human_revisions', {}).get(asset.get('human_revision'), {}).get('policy')
    if parent and policy:
        expected.reverse()
    expected += asset["edit_references"]
    require(c, inputs.get("references") == expected, "Reference paths, order, roles, hashes or scopes differ from the recorded edit.")
