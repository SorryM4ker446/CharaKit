"""Budgeted candidate sampling and attributable human review. No image generation."""
import copy
import html
import json
from pathlib import Path
import secrets
import string


def require(c, condition, message, code="INVALID_CANDIDATE_REVIEW"):
    if not condition:
        raise c.StudioError(code, message)


def validate_contract(c, contract):
    require(c, isinstance(contract, list) and 5 <= len(contract) <= 30,
            "Define 5–30 source-grounded checks before generation.")
    ids = set()
    dimensions = set()
    for item in contract:
        require(c, isinstance(item, dict) and all(c.valid_edit_text(item.get(k), 1000)
                for k in ("id", "component", "property", "expected"))
                and item.get("dimension") in c.QUALITY_WEIGHTS_V12
                and item.get("view") in c.QUALITY_INSPECTIONS, "Invalid check definition.")
        require(c, item["id"] not in ids, "Check IDs must be unique.")
        ids.add(item["id"])
        dimensions.add(item["dimension"])
    require(c, dimensions == set(c.QUALITY_WEIGHTS_V12), "Cover all five dimensions with distinct checks.")


def validate_assessment(c, data):
    checks = data.get("criteria")
    validate_contract(c, checks)
    require(c, type(data.get("normal_display_height")) is int and 1 <= data["normal_display_height"] <= 10000
            and c.valid_edit_text(data.get("blind_packet"), 100), "Record inspection height and anonymous packet ID.")
    for item in checks:
        score = item.get("score")
        require(c, type(score) is int and 0 <= score <= 5 and item.get("status") in c.FIDELITY_CHECKS
                and c.valid_edit_text(item.get("observed"), 2000), "Record each actual observation, score and status.")
        require(c, (item["status"] == "passed") == (score >= 4), "Passing checks require 4 or 5; defects/uncertainty cannot receive passing scores.")
        if item["status"] == "uncertain":
            require(c, bool(data["uncertainties"]), "Record unresolved evidence explicitly.")
    for dim in c.QUALITY_WEIGHTS_V12:
        require(c, data["dimensions"][dim]["score"] == min(x["score"] for x in checks if x["dimension"] == dim),
                "Each dimension uses its weakest applicable check; do not average away defects.")


def validate_outfit_contract(c, asset, contract):
    for ref in asset.get("edit_references", []):
        require(c, any(check["dimension"] == "target" and check["component"] == ref["id"] for check in contract),
                "Include a target check for every reference ID, describing its permitted design/expression cues.")
    if asset.get("edit_type") == "prop_edit":
        require(c, any(check["dimension"] == "target" and check["component"] == asset["target"]
                       for check in contract), "Prop contracts must include a target check for the actual object or addition site.")
    if asset.get("edit_type") == "outfit_replace":
        require(c, all(any(check["dimension"] == "target" and check["component"] == item["source"]
                           for check in contract) for item in asset["outfit_components"]),
                "Full outfit contracts must include a target check for each source clothing component.")


def validate_state(c, state):
    pools = state.get("candidate_pools", {})
    require(c, isinstance(pools, dict), "Invalid candidate pools.")
    by_id = {a["id"]: a for a in state["assets"]}
    slots = set()
    for key, pool in pools.items():
        require(c, key in by_id and pool.get("version") in ("1.0", "1.1") and pool.get("slot") == c.asset_slot(by_id[key])
                and (pool.get("stopped") or pool["slot"] not in slots), "Invalid pool identity.")
        if not pool.get("stopped"):
            slots.add(pool["slot"])
        validate_contract(c, pool["contract"])
        validate_outfit_contract(c, by_id[key], pool["contract"])
        attempts = pool["attempts"]
        require(c, type(pool["budget"]) is int and 1 <= pool["budget"] <= 3 and isinstance(attempts, list)
                and 1 <= len(attempts) <= pool["budget"] and attempts[0].get("asset_id") == key, "Invalid fixed budget.")
        seen = set()
        for n, attempt in enumerate(attempts, 1):
            require(c, attempt["number"] == n and attempt["status"] in ("reserved", "imported", "failed")
                    and attempt["strategy"] == (("user_revision" if pool.get("human_revision") else "source_sample") if n == 1 else
                                                ("review_redraw" if pool["version"] == "1.1" else
                                                 ("user_revision" if pool.get("human_revision") else "source_sample" if n == 2 else "repair_best"))), "Invalid attempt order.")
            if attempt["status"] == "imported":
                aid = attempt["asset_id"]
                require(c, aid in by_id and aid not in seen and by_id[aid].get("candidate_pool") == key
                        and c.asset_slot(by_id[aid]) == pool["slot"] and "refinement_case" not in by_id[aid], "Invalid pool member.")
                seen.add(aid)
            if by_id[key].get("edit_references"):
                require(c, pool["version"] == "1.1", "Scoped references require the review/redraw workflow.")
                expected = copy.deepcopy(by_id[key]["generation_inputs"]["references"])
                if n > 1:
                    parent = by_id.get(attempt.get("parent"))
                    require(c, parent is not None, "A reference-aware redraw needs its recorded parent.")
                    expected = [{"path": state["source"], "sha256": state["source_sha256"], "role": "immutable_source"},
                                {"path": parent["path"], "sha256": parent["sha256"], "role": "edit_target"}] + copy.deepcopy(by_id[key]["edit_references"])
                require(c, attempt.get("references") == expected, "Attempt references must preserve paths, roles, hashes and editable scopes.")
                if attempt["status"] == "imported":
                    member = by_id[attempt["asset_id"]]
                    require(c, member.get("edit_references") == by_id[key]["edit_references"]
                            and member.get("generation_inputs", {}).get("references") == expected
                            and member["generation_inputs"]["strategy"] == attempt["strategy"], "Imported references differ from their reserved attempt.")
            if pool['version'] == '1.1' and n > 1:
                parent = by_id.get(attempt.get('parent'))
                require(c, parent is not None and parent['id'] in {a.get('asset_id') for a in attempts[:n-1] if a['status']=='imported'}
                        and parent.get('quality_review') is not None
                        and attempt.get('review_sha256') == c.review_fingerprint(parent['quality_review'])
                        and attempt.get('blocking_findings') == redraw_findings(parent)
                        and bool(attempt.get('blocking_findings')),
                        "Redraws must retain the assessed parent's failure evidence.")
                require(c, [r['path'] for r in attempt.get('references', [])] == [state['source'], parent['path']] + [r['path'] for r in by_id[key].get('edit_references', [])],
                        "Redraws use the immutable source and their recorded parent.")
                if attempt['status'] == 'imported':
                    require(c, by_id[attempt['asset_id']]['parent_asset_id'] == parent['id'], "Invalid redraw lineage.")
        require(c, not any(a["status"] == "reserved" for a in attempts[:-1]), "Only the latest attempt can be pending.")
    for asset in state["assets"]:
        if "candidate_pool" in asset:
            require(c, asset["candidate_pool"] in pools and any(a.get("asset_id") == asset["id"]
                    for a in pools[asset["candidate_pool"]]["attempts"]), "Orphan pool candidate.")
    revisions = state.get("human_revisions", {})
    require(c, isinstance(revisions, dict), "Invalid human revisions.")
    for key, revision in revisions.items():
        packet = state.get("review_packets", {}).get(key, {})
        feedback = packet.get("feedback", {}).get("input", {})
        parent = by_id.get(revision.get("parent_asset"))
        require(c, parent is not None and revision.get("packet") == key and feedback.get("decision") == "revise"
                and feedback.get("basis") == "user" and feedback.get("note") == revision.get("note")
                and packet.get("items", {}).get(feedback.get("candidate"), {}).get("asset_id") == parent["id"]
                and revision.get("source_sha256") == state["source_sha256"]
                and revision.get("parent_sha256") == parent["sha256"]
                and revision.get("status") in ("reserved", "imported", "failed", "cancelled"), "Invalid human revision binding.")
        validate_revision_contract(c, state, parent, revision["contract"])
        if parent.get("edit_references"):
            expected = [{"path": state["source"], "sha256": state["source_sha256"], "role": "immutable_source"},
                        {"path": parent["path"], "sha256": parent["sha256"], "role": "edit_target"}] + copy.deepcopy(parent["edit_references"])
            require(c, revision.get("pool_version") == "1.1" and revision.get("references") == expected,
                    "Human revision inputs retain source, chosen parent and every scoped reference.")
        if revision["status"] == "imported":
            aid = revision.get("asset_id")
            require(c, aid in by_id and by_id[aid].get("human_revision") == key
                    and by_id[aid].get("parent_asset_id") == parent["id"]
                    and c.asset_slot(by_id[aid]) == c.asset_slot(parent)
                    and aid in pools and pools[aid].get("human_revision") == key
                    and pools[aid]["budget"] == revision.get("budget", 1) and pools[aid]["contract"] == revision["contract"],
                    "Invalid imported human revision.")
            require(c, all(by_id[aid].get(field) == parent.get(field) for field in
                          ("expression", "mouth_state", "outfit_id", "edit_type", "target", "color", "replacement", "outfit_components", "prop_action", "edit_brief", "edit_references")),
                    "Human revisions retain their chosen parent's edit definition and brief.")
    for asset in state["assets"]:
        if "human_revision" in asset:
            origin = revisions.get(asset["human_revision"], {}).get("asset_id")
            require(c, origin == asset.get("candidate_pool")
                    and pools.get(origin, {}).get("human_revision") == asset["human_revision"], "Orphan human revision.")
    for key, pool in pools.items():
        if "human_revision" in pool:
            require(c, revisions.get(pool["human_revision"], {}).get("asset_id") == key, "Orphan revision pool.")


def validate_revision_contract(c, state, parent, contract):
    validate_contract(c, contract)
    validate_outfit_contract(c, parent, contract)
    fields = {"id", "component", "property", "expected", "dimension", "view"}
    require(c, all(set(item) == fields for item in contract), "Revision contracts contain definitions only.")
    original = state["candidate_pools"][parent["candidate_pool"]]["contract"]
    current = {item["id"]: item for item in contract}
    for item in original:
        replacement = current.get(item["id"], {})
        fixed = fields - {"expected"} if item["dimension"] == "target" else fields
        require(c, all(replacement.get(k) == item[k] for k in fixed),
                "Keep original protection checks; only target expectations may change. Add focused checks for the actual correction.")


def revision_origin(c, root, state, key):
    packet = state.get("review_packets", {}).get(key)
    feedback = (packet or {}).get("feedback", {}).get("input", {})
    require(c, packet is not None and packet["purpose"] == "user" and feedback.get("decision") == "revise"
            and feedback.get("basis") == "user", "Record actual, specific revision feedback first.", "HUMAN_REVISION_REQUIRED")
    packet_valid(c, root, state, packet)
    parent = c.get_asset(state, packet["items"][feedback["candidate"]]["asset_id"])
    require(c, parent.get("human_feedback", {}).get("packet") == key
            and parent["human_feedback"]["decision"] == "revise", "A newer user decision supersedes this revision.", "HUMAN_REVISION_SUPERSEDED")
    require(c, parent.get("candidate_pool") in state.get("candidate_pools", {})
            and state["candidate_pools"][parent["candidate_pool"]].get("stopped"), "Close the original batch first.")
    require(c, not any(p["slot"] == c.asset_slot(parent) and not p.get("stopped")
                      for p in state.get("candidate_pools", {}).values()), "Another batch for this request is active.", "HUMAN_REVISION_NOT_READY")
    require(c, c.quality_status(root, state, parent) != "stale", "Parent inspection evidence changed.", "STALE_REVIEW_PACKET")
    return parent, feedback


def revision_plan(c, root, state, key):
    revision = state["human_revisions"][key]
    parent = c.get_asset(state, revision["parent_asset"])
    return {"revision": key, "status": revision["status"], "budget": revision.get("budget", 1),
            "parent_asset": parent["id"], "note": revision["note"], "contract": revision["contract"],
            "edit": {k: copy.deepcopy(parent[k]) for k in ("expression", "mouth_state", "outfit_id", "edit_type", "target", "color", "replacement", "outfit_components", "prop_action", "edit_brief", "edit_references") if k in parent},
            "references": copy.deepcopy(revision["references"]),
            "reference_paths": [str(c.contained(root, item["path"])) for item in revision["references"]],
            "asset_id": revision.get("asset_id"), "failure": revision.get("failure"),
            "next_action": {"reserved": "generate_revision", "imported": "review", "failed": "stopped", "cancelled": "stopped"}[revision["status"]]}


def revision_prepare(c, root, key, contract, budget=None):
    root = root.resolve()
    state = c.read_state(root)
    existing = state.get("human_revisions", {}).get(key)
    if existing:
        require(c, existing["contract"] == contract and (budget is None or budget == existing.get("budget", 1)), "Cannot rewrite or reset an existing human revision.")
        if existing["status"] == "reserved":
            revision_origin(c, root, state, key)
        return revision_plan(c, root, state, key)
    parent, feedback = revision_origin(c, root, state, key)
    budget = 3 if budget is None else budget
    require(c, type(budget) is int and 1 <= budget <= 3, "Use one to three total attempts.")
    validate_revision_contract(c, state, parent, contract)
    require(c, not any(r["status"] == "reserved" and c.asset_slot(c.get_asset(state, r["parent_asset"])) == c.asset_slot(parent)
                      for r in state.get("human_revisions", {}).values()), "Another human revision is pending.", "HUMAN_REVISION_NOT_READY")
    references = [{"path": path, "sha256": c.digest(c.contained(root, path)), "role": role}
                  for path, role in ((state["source"], "immutable_source"), (parent["path"], "edit_target"))]
    if parent.get("edit_references"):
        references = c.reference_call("bindings", root, state, parent, parent)
    state.setdefault("human_revisions", {})[key] = {
        "packet": key, "parent_asset": parent["id"], "parent_sha256": parent["sha256"],
        "source_sha256": state["source_sha256"], "parent_quality_sha256": c.review_fingerprint(parent["quality_review"]),
        "note": feedback["note"], "contract": copy.deepcopy(contract), "references": references,
        "status": "reserved", "budget": budget, "pool_version": "1.1", "created_at": c.timestamp()}
    c.write_state(root, state)
    return revision_plan(c, root, state, key)


def revision_import(c, root, key, image, prompt, references, failure=None):
    root = root.resolve()
    state = c.read_state(root)
    revision = state.get("human_revisions", {}).get(key)
    require(c, revision is not None and revision["status"] == "reserved", "This revision is not pending; do not generate again.", "HUMAN_REVISION_NOT_READY")
    parent, _ = revision_origin(c, root, state, key)
    require(c, c.review_fingerprint(parent["quality_review"]) == revision["parent_quality_sha256"]
            and all(c.digest(c.contained(root, r["path"])) == r["sha256"] for r in revision["references"]),
            "Revision references or parent assessment changed.", "STALE_REVIEW_PACKET")
    if failure is not None:
        require(c, c.valid_edit_text(failure, 2000), "Record the failed image-tool call.")
        revision.update(status="failed", failure=failure)
        c.write_state(root, state)
        return revision_plan(c, root, state, key)
    require(c, [p.resolve() for p in references] == [c.contained(root, r["path"]) for r in revision["references"]],
            "Use the returned immutable source, chosen edit target and scoped references in order.", "INVALID_REVISION_REFERENCES")
    actual_prompt = prompt.read_text(encoding="utf-8")
    require(c, bool(actual_prompt.strip()), "Save the actual targeted revision prompt.")
    fields = {k: copy.deepcopy(parent[k]) for k in ("expression", "mouth_state", "outfit_id", "edit_type", "target", "color", "replacement", "outfit_components", "prop_action", "edit_brief", "edit_references") if k in parent}
    fields.update(human_revision=key, quality_required=c.QUALITY_VERSION,
                  generation_inputs={"strategy": "user_revision", "references": copy.deepcopy(revision["references"]), "packet": key})
    return c.save_candidate(root, state, image, fields, c.validate_image(image, state["canvas"], state["background_mode"]), actual_prompt)


def pool_start(c, root, aid, contract, budget=3):
    state = c.read_state(root)
    asset = c.get_asset(state, aid)
    validate_contract(c, contract)
    validate_outfit_contract(c, asset, contract)
    require(c, all(set(x) == {"id", "component", "property", "expected", "dimension", "view"} for x in contract), "Contracts contain definitions only, not retrospective scores.")
    require(c, type(budget) is int and 1 <= budget <= 3, "Use one to three total attempts.")
    existing = state.get("candidate_pools", {}).get(aid)
    if existing:
        require(c, existing["budget"] == budget and existing["contract"] == contract, "Cannot reset budget or rewrite contract.")
        return pool_status(c, root, aid)
    require(c, not any(r["status"] == "reserved" and c.asset_slot(c.get_asset(state, r["parent_asset"])) == c.asset_slot(asset)
                      for r in state.get("human_revisions", {}).values()), "Use the pending human revision, not another pool.", "HUMAN_REVISION_NOT_READY")
    require(c, "refinement_case" not in asset and "quality_review" not in asset
            and asset["art_review_status"] == "unreviewed" and "candidate_pool" not in asset,
            "Start before assessing a fresh candidate; do not migrate old verdicts or reset spent budgets.")
    require(c, not any(p["slot"] == c.asset_slot(asset) and not p.get("stopped") for p in state.get("candidate_pools", {}).values()), "This request already has a pool.")
    asset["candidate_pool"] = aid
    asset["parent_asset_id"] = None
    initial = {"number": 1, "status": "imported", "strategy": "source_sample", "asset_id": aid}
    if asset.get("edit_references"):
        initial["references"] = copy.deepcopy(asset["generation_inputs"]["references"])
    state.setdefault("candidate_pools", {})[aid] = {
        "version": "1.1", "slot": c.asset_slot(asset), "budget": budget, "contract": copy.deepcopy(contract),
        "attempts": [initial],
        "comparisons": [], "created_at": c.timestamp()}
    c.write_state(root, state)
    return pool_status(c, root, aid)


def pool_assets(c, state, pool):
    return [c.get_asset(state, a["asset_id"]) for a in pool["attempts"] if a["status"] == "imported"]


def eligible(c, root, state, asset):
    return (c.quality_status(root, state, asset) == "passed"
            and c.fidelity_status(asset) not in ("pending", "failed", "uncertain")
            and c.delivery_validation(c.check_asset(root, state, asset))["passed"]
            and asset["art_review_status"] != "rejected")


def redraw_findings(asset):
    """Return recorded failures, never inferred visual observations."""
    review = asset.get("quality_review", {})
    findings = [{"id": item["id"], "component": item["component"], "expected": item["expected"],
                 "observed": item["observed"], "status": item["status"]}
                for item in review.get("criteria", []) if item["status"] != "passed"]
    domain = review.get("domain_review", {})
    for key, item in list(domain.get("checks", {}).items()) + list(domain.get("component_checks", {}).items()):
        if item["status"] != "passed":
            findings.append({"id": key, **item})
    for key in ("critical_defects", "uncertainties"):
        for note in review.get(key, []):
            findings.append({"id": key, "observed": note})
    for key, completed in review.get('inspection', {}).items():
        if not completed:
            findings.append({'id': 'inspection:'+key, 'status': 'uncertain', 'observed': 'Required inspection is incomplete.'})
    fidelity = asset.get("fidelity_review", {})
    if any(fidelity.get(k) in ("failed", "uncertain") for k in ("target_check", "protection_check")):
        findings.append({"id": "fidelity", "observed": fidelity["note"]})
    return findings


def pool_status(c, root, key):
    state = c.read_state(root)
    require(c, key in state.get("candidate_pools", {}), "Unknown pool.")
    pool = state["candidate_pools"][key]
    assets = pool_assets(c, state, pool)
    passed = [a for a in assets if eligible(c, root, state, a)]
    stale = any(c.quality_status(root, state, a) == "stale" or not c.delivery_validation(c.check_asset(root, state, a))["passed"] for a in assets)
    pending = any("quality_review" not in a or c.fidelity_status(a) == "pending" for a in assets)
    ranking = next((x for x in reversed(pool["comparisons"]) if x["asset_ids"] == [a["id"] for a in assets]), None)
    best = next((a for a in passed if ranking and a["id"] == ranking["preferred"]), passed[0] if passed else None)
    if stale:
        action = "blocked"
    elif pool.get("stopped"):
        accepted = next((a for a in passed if a["id"] == state["selected"].get(pool["slot"])), None)
        action = "export" if accepted and c.check_asset(root, state, accepted)["passed"] else "stopped"
    elif pool["attempts"][-1]["status"] == "reserved":
        action = "generate_reserved"
    elif pending:
        action = "review"
    elif len(assets) > 1 and not ranking:
        action = "compare"
    elif passed:
        action = "human_review"
    elif len(pool["attempts"]) >= pool["budget"]:
        action = "exhausted"
    elif pool["version"] == "1.1":
        action = "redraw"
    elif len(pool["attempts"]) == 1:
        action = "sample"
    elif ranking and ranking["repairable"] and ranking["preferred"]:
        action = "repair"
    else:
        action = "exhausted"
    return {"case_id": key, "action": action, "used": len(pool["attempts"]), "budget": pool["budget"],
            "best_asset": best["id"] if best else None, "passed_assets": [a["id"] for a in passed],
            "preferred_asset": ranking["preferred"] if ranking else (best["id"] if best else None),
            "attempts": pool["attempts"], "contract": pool["contract"],
            "repair_parent": (ranking["preferred"] if ranking and ranking["preferred"] else assets[-1]["id"]) if action in ("repair", "redraw") else None,
            "blocking_findings": {a["id"]: redraw_findings(a) for a in assets if not eligible(c, root, state, a)},
            "note": "User feedback is required before acceptance/export. Failed candidates remain inspection evidence."}


def pool_reserve(c, root, key):
    plan = pool_status(c, root, key)
    require(c, plan["action"] in ("sample", "repair", "redraw"), "No additional generation is currently permitted.", "POOL_NOT_READY")
    state = c.read_state(root)
    pool = state["candidate_pools"][key]
    refs = [state["source"]]
    if plan["repair_parent"]:
        refs.append(c.get_asset(state, plan["repair_parent"])["path"])
    attempt = {"number": len(pool["attempts"]) + 1, "status": "reserved", "token": secrets.token_hex(12),
               "strategy": {"sample": "source_sample", "repair": "repair_best", "redraw": "review_redraw"}[plan["action"]],
               "parent": plan["repair_parent"], "references": [{"path": p, "sha256": c.digest(c.contained(root, p))} for p in refs]}
    original = c.get_asset(state, key)
    if original.get("edit_references"):
        parent = c.get_asset(state, plan["repair_parent"]) if plan["repair_parent"] else None
        attempt["references"] = c.reference_call("bindings", root, state, original, parent)
        refs = [r["path"] for r in attempt["references"]]
    if plan["repair_parent"]:
        attempt["repair_plan"] = (pool["comparisons"][-1]["repair_plan"] if plan["action"] == "repair" else
                                  "Correct the attached failed checks; retain the fixed contract and successful edits. The immutable source controls identity, pose and framing; do not copy failed properties from the candidate.")
        attempt["blocking_findings"] = plan["blocking_findings"][plan["repair_parent"]]
        attempt["review_sha256"] = c.review_fingerprint(c.get_asset(state, plan["repair_parent"])["quality_review"])
    pool["attempts"].append(attempt)
    c.write_state(root, state)
    return {**attempt, "reference_paths": [str(c.contained(root, p)) for p in refs]}


def pool_import(c, root, key, token, image, prompt, references, failure=None):
    state = c.read_state(root)
    pool = state.get("candidate_pools", {}).get(key)
    require(c, pool is not None, "Unknown pool.")
    attempt = pool["attempts"][-1]
    require(c, attempt["status"] == "reserved" and attempt["token"] == token, "Attempt is not reserved.")
    if failure is not None:
        require(c, c.valid_edit_text(failure, 2000), "Record the tool failure; it consumes the reserved attempt.")
        attempt.update(status="failed", failure=failure)
        c.write_state(root, state)
        return pool_status(c, root, key)
    require(c, pool_status(c, root, key)["action"] == "generate_reserved", "Existing evidence changed after reservation.", "POOL_NOT_READY")
    require(c, [p.resolve() for p in references] == [c.contained(root, r["path"]).resolve() for r in attempt["references"]]
            and all(c.digest(c.contained(root, r["path"])) == r["sha256"] for r in attempt["references"]), "References differ from the reserved plan.")
    if attempt.get("parent"):
        require(c, attempt["review_sha256"] == c.review_fingerprint(c.get_asset(state, attempt["parent"])["quality_review"]), "Parent assessment changed after reservation.", "POOL_NOT_READY")
    actual_prompt = prompt.read_text(encoding="utf-8")
    require(c, bool(actual_prompt.strip()), "Save the actual submitted prompt.")
    original = c.get_asset(state, key)
    fields = {k: copy.deepcopy(original[k]) for k in ("expression", "mouth_state", "outfit_id", "target", "color", "replacement", "edit_type", "outfit_components", "prop_action", "edit_brief", "edit_references") if k in original}
    fields.update(candidate_pool=key, repair_parent=attempt["parent"], generation_inputs=copy.deepcopy(attempt))
    if pool.get("human_revision"):
        fields["human_revision"] = pool["human_revision"]
    result = c.save_candidate(root, state, image, fields, c.validate_image(image, state["canvas"], state["background_mode"]), actual_prompt)
    return result


def packet_valid(c, root, state, packet):
    require(c, packet["source_sha256"] == state["source_sha256"], "Review source changed.")
    for item in packet.get("artifacts", []):
        path = c.contained(root, item["path"])
        require(c, path.is_file() and c.digest(path) == item["sha256"], "Review page or reference changed.", "STALE_REVIEW_PACKET")
    for label, binding in packet["items"].items():
        asset = c.get_asset(state, binding["asset_id"])
        c.reference_call("check_files", root, asset.get("edit_references", []))
        original = c.contained(root, asset["path"])
        snapshot = c.contained(root, binding["copy"])
        require(c, original.is_file() and snapshot.is_file() and c.digest(original) == binding["sha256"] == asset["sha256"]
                and c.digest(snapshot) == binding["sha256"], "Review candidate changed or is missing.", "STALE_REVIEW_PACKET")
        if packet["purpose"] == "user":
            require(c, c.review_fingerprint(asset.get("quality_review", {})) == binding["quality_sha256"], "Assessment changed after user packet creation.", "STALE_REVIEW_PACKET")
    if packet.get("revision_parent"):
        binding = packet["revision_parent"]
        parent = c.get_asset(state, binding["asset_id"])
        original = c.contained(root, parent["path"])
        snapshot = c.contained(root, binding["copy"])
        require(c, original.is_file() and snapshot.is_file() and c.digest(original) == parent["sha256"] == binding["sha256"]
                and c.digest(snapshot) == binding["sha256"], "Revision comparison parent changed or is missing.", "STALE_REVIEW_PACKET")


def check_pool_assessment(c, root, state, asset, assessment):
    require(c, assessment["rubric_version"] == "1.2", "New candidate pools require rubric 1.2.")
    pool = state["candidate_pools"][asset["candidate_pool"]]
    definition = [{k: x[k] for k in ("id", "dimension", "component", "property", "expected", "view")} for x in assessment["criteria"]]
    require(c, definition == pool["contract"], "Assess the original contract without adding or relaxing criteria.")
    packet = state.get("review_packets", {}).get(assessment["blind_packet"])
    require(c, packet is not None and packet["purpose"] == "assistant" and any(b["asset_id"] == asset["id"] for b in packet["items"].values()), "Inspect the anonymous assistant packet first.")
    packet_valid(c, root, state, packet)


def review_sheet(c, root, ids, purpose="user", language="zh-CN", translations=None):
    root = root.resolve()
    try:
        ui = preview_text(language, translations)
    except ValueError as exc:
        raise c.StudioError('INVALID_REVIEW_LANGUAGE', str(exc)) from exc
    state = c.read_state(root)
    require(c, 1 <= len(ids) <= 3 and len(set(ids)) == len(ids), "Review one to three distinct candidates from one request.")
    assets = [c.get_asset(state, i) for i in ids]
    require(c, len({c.asset_slot(a) for a in assets}) == 1, "Compare the same request only.")
    reference_metadata = assets[0].get("edit_references", [])
    require(c, all(a.get("edit_references", []) == reference_metadata for a in assets), "Compare candidates with the same scoped references.")
    require(c, all(c.delivery_validation(c.check_asset(root, state, a))["passed"] for a in assets), "Review requires readable, unchanged images.")
    if purpose == "user":
        require(c, all("quality_review" in a and c.quality_status(root, state, a) != "stale" for a in assets), "Complete internal assessment before human review.")
        for asset in assets:
            pool = state.get("candidate_pools", {}).get(asset.get("candidate_pool"), {})
            if pool.get("version") == "1.1":
                require(c, pool_status(c, root, asset["candidate_pool"])["action"] in ("human_review", "exhausted", "export", "stopped"),
                        "Finish internal review and redraw within the fixed budget before human review.", "INTERNAL_REVIEW_INCOMPLETE")
    origin = None
    if purpose == "user" and assets[0].get("human_revision") and len({a.get("human_revision") for a in assets}) == 1:
        origin = state["human_revisions"][assets[0]["human_revision"]]
        parent = c.get_asset(state, origin["parent_asset"])
        parent_path = c.contained(root, parent["path"])
        require(c, parent_path.is_file() and c.digest(parent_path) == origin["parent_sha256"], "Revision parent changed or is missing.", "STALE_REVIEW_PACKET")
    secrets.SystemRandom().shuffle(assets)
    key = secrets.token_hex(12)
    folder = root / "reviews" / key
    folder.mkdir(parents=True)
    c.copy_exclusive(c.contained(root, state["source"]), folder / "source.png")
    items = {}
    for label, asset in zip(string.ascii_uppercase, assets):
        path = folder / f"{label}.png"
        c.copy_exclusive(c.contained(root, asset["path"]), path)
        items[label] = {"asset_id": asset["id"], "sha256": asset["sha256"], "copy": path.relative_to(root).as_posix(),
                        "quality_sha256": c.review_fingerprint(asset.get("quality_review", {}))}
    packet = {"purpose": purpose, "source_sha256": state["source_sha256"], "items": items, "created_at": c.timestamp()}
    state.setdefault("review_packets", {})[key] = packet
    contract = state.get("candidate_pools", {}).get(assets[0].get("candidate_pool"), {}).get("contract", [])
    request = assets[0].get("quality_review", {}).get("request") or assets[0].get("replacement") or assets[0].get("color") or assets[0].get("expression", "")
    if assets[0].get("edit_type") == "prop_edit" and not assets[0].get("quality_review"):
        action = {"add": "添加", "remove": "移除", "replace": "替换"}[assets[0]["prop_action"]] if language == "zh-CN" else assets[0]["prop_action"].capitalize()
        request = action + " · " + assets[0]["target"] + (" → " + assets[0]["replacement"] if "replacement" in assets[0] else "")
    revision = None
    if origin:
        c.copy_exclusive(parent_path, folder / "parent.png")
        packet["revision_parent"] = {"asset_id": parent["id"], "sha256": parent["sha256"],
                                     "copy": (folder / "parent.png").relative_to(root).as_posix()}
        revision = {"source": "parent.png", "note": origin["note"]}
    edit_references = []
    for index, ref in enumerate(reference_metadata, 1):
        filename = f'reference-{index}' + Path(ref["path"]).suffix
        c.copy_exclusive(c.contained(root, ref["path"]), folder / filename)
        edit_references.append({**ref, "path": filename})
    if edit_references:
        packet["edit_references"] = copy.deepcopy(reference_metadata)
    page = render_sheet(key, list(items), request, contract, purpose, language, ui, revision, edit_references)
    (folder / "index.html").write_text(page, encoding="utf-8")
    # Public packet contains no mapping, version, generation prompt, prior score or status.
    public = {"packet": key, "purpose": purpose, "request": request, "contract": contract, "language": language, "ui_labels": ui,
              "source": "source.png", "candidates": {label: f"{label}.png" for label in items}}
    if revision:
        public["revision"] = revision
    if edit_references:
        public["edit_references"] = edit_references
    (folder / "packet.json").write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    packet["artifacts"] = [{"path": p.relative_to(root).as_posix(), "sha256": c.digest(p)} for p in (folder / "source.png", folder / "index.html", folder / "packet.json")]
    if revision:
        packet["artifacts"].append({"path": packet["revision_parent"]["copy"], "sha256": origin["parent_sha256"]})
    packet["artifacts"] += [{"path": (folder / ref["path"]).relative_to(root).as_posix(), "sha256": ref["sha256"]} for ref in edit_references]
    c.write_state(root, state)
    return {"packet": key, "page": str((folder / "index.html").resolve()), "public_packet": str((folder / "packet.json").resolve()),
            **({"edit_references": [{**r, "path": str((folder / r["path"]).resolve())} for r in edit_references]} if edit_references else {}),
            **({"revision_parent": str((folder / "parent.png").resolve()), "revision_note": origin["note"]} if origin else {}),
            "source": str((folder / "source.png").resolve()), "candidates": {label: str((folder / f"{label}.png").resolve()) for label in items}}


PREVIEW_EN = {'CharaKit 评图': 'CharaKit image review',
 '查看效果，再决定是否交付': 'Review the images before delivery',
 '这里是匿名评图材料，不代表已通过或可打包。请先看整体，再看目标部位、人物和未要求修改的细节。': 'These anonymous candidates are inspection materials. Review the '
                                                   'full image, the requested edit, the character and protected '
                                                   'details before deciding.',
 '切换明暗底色': 'Toggle light/dark background',
 '放大预览': 'Enlarge preview',
 '本次检查要求': 'Review requirements',
 '你的评审': 'Your review',
 '可以直接在聊天中回复“采用 A”“B 需要修改：……”或“都不采用”，也可以下载反馈文件交给 Codex。': 'Reply in chat with “Accept A”, “Revise B: …” or “Reject '
                                                          'all”, or download your feedback for Codex.',
 '决定': 'Decision',
 '请选择': 'Choose…',
 '采用': 'Accept',
 '需要修改': 'Request changes',
 '都不采用': 'Reject all',
 '候选': 'Candidate',
 '评审意见': 'Review comments',
 '哪些地方满意或需要修改？请描述部位和希望保留/改变的效果。': 'What works and what needs changing? Describe the part and what to preserve or '
                                  'change.',
 '需求符合度': 'Request fit',
 '人物与细节保留': 'Character and detail preservation',
 '实际使用意愿': 'Usability',
 '未评价': 'Not rated',
 '满意': 'Satisfied',
 '不满意': 'Unsatisfied',
 '可使用': 'Usable',
 '需要调整': 'Needs changes',
 '下载反馈 JSON': 'Download feedback JSON',
 '将实际反馈交给 Codex 后，才会生成最终评审报告，包含你的意见和处理结果；符合交付条件的作品再进入打包。此页面不会自动提交或打包。': 'After you give Codex your actual feedback, '
                                                                        'the final review report includes your '
                                                                        'comments and the disposition. Only eligible '
                                                                        'accepted images can be packaged. This page '
                                                                        'does not submit or package anything '
                                                                        'automatically.',
 '大图预览': 'Large image preview',
 '关闭大图预览': 'Close large image preview',
 '关闭 ×': 'Close ×',
 '上一张': 'Previous image',
 '下一张': 'Next image',
 '查看': 'View',
 '缩小': 'Zoom out',
 '放大比例': 'Zoom level',
 '放大': 'Zoom in',
 '适应窗口': 'Fit to window',
 '拖动或滚动查看细节；切换图片保留放大比例和查看位置。方向键切换，Esc 关闭。': 'Drag or scroll to inspect details. Switching images retains zoom and '
                                            'position. Arrow keys switch images; Esc closes.',
 '可滚动的大图': 'Scrollable image',
 '原图': 'Source',
 '放大查看': 'Enlarge',
 '加载中…': 'Loading…',
 '图片加载失败，请关闭后重试。': 'Image failed to load. Close and try again.',
 '请选择决定和候选；需要修改时请说明问题。': 'Choose a decision and candidate. Describe the issue when requesting changes.',
 '反馈已下载。将文件交给 Codex 后才会处理，不会在此页面自动打包。': 'Feedback downloaded. Give it to Codex for processing; this page does not '
                                        'package images automatically.'}

# Append labels to preserve the existing template's numbered UI tokens.
PREVIEW_EN.update({'修订前': 'Before revision', '本次修改': 'Requested correction',
                  '参考图': 'Edit reference', '仅参考指定修改内容': 'Use only for the specified edit'})

REVIEW_SHEET_TEMPLATE = r"""<!doctype html>
<html lang="__LANGUAGE__">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__UI_0__</title><link rel="icon" href="data:,">
<style>
*{box-sizing:border-box}body{font:16px system-ui;max-width:1400px;margin:32px auto;padding:0 20px;background:#f5f4f0;color:#20232a}h1{font-size:28px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}figure{margin:0;min-width:0;background:white;padding:12px;border-radius:12px}
.image-button{display:block;border:0;margin:0;padding:0;width:100%;background:transparent;cursor:zoom-in}.image-button img{display:block;width:100%;height:520px;object-fit:contain;background:#ddd}body.dark .image-button img{background:#25272c}
figcaption{font-weight:bold;margin-bottom:8px}button,select,textarea,input{font:inherit}button,select{padding:10px;margin:8px 8px 8px 0}textarea{display:block;width:100%;max-width:100%;min-height:80px;padding:10px;margin:8px 0}button{cursor:pointer}section{background:white;padding:20px;margin-top:20px;border-radius:12px}button:focus-visible,select:focus-visible,textarea:focus-visible,input:focus-visible{outline:3px solid #3657ae;outline-offset:3px}
dialog{width:min(1400px,96vw);height:94dvh;max-width:none;max-height:94dvh;padding:16px;border:0;border-radius:12px;background:#f5f4f0;color:#20232a}dialog::backdrop{background:#0009}dialog[open]{display:flex;flex-direction:column;gap:8px}body.viewer-open{overflow:hidden}
.viewer-header{display:flex;align-items:center;justify-content:space-between;gap:12px}.viewer-header h2{font-size:20px;margin:0}.viewer-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.viewer-toolbar button,.viewer-header button,.viewer-toolbar select{margin:0}.viewer-toolbar input{width:140px;max-width:30vw}.viewer-toolbar output{min-width:56px}.viewer-hint{font-size:14px;margin:0;color:#535761}
.viewport{flex:1;min-height:0;min-width:0;overflow:auto;background:#ddd;border-radius:8px;touch-action:pan-x pan-y;cursor:grab}.viewport.dragging{cursor:grabbing;user-select:none}body.dark .viewport{background:#25272c}.image-frame{display:flex;align-items:center;justify-content:center}.image-frame img{display:block;flex:none;max-width:none;pointer-events:none;user-select:none}
@media(max-width:600px){body{padding:0 12px;margin:20px auto}.grid{grid-template-columns:1fr}.image-button img{height:420px}dialog{width:100vw;height:100dvh;max-height:100dvh;border-radius:0;padding:12px}.viewer-toolbar{gap:6px}.viewer-toolbar button{padding:8px}.viewer-toolbar input{width:110px}.viewer-hint{font-size:12px}}
</style>
<h1>__UI_1__</h1>
<p>__REQUEST__</p>
<p>__UI_2__</p>
<button id="background" type="button" aria-pressed="false">__UI_3__</button><button id="open-viewer" type="button">__UI_4__</button>
<div class="grid">__CARDS__</div>
<section><details><summary>__UI_5__</summary><ul>__CHECKS__</ul></details>
<h2>__UI_6__</h2><p>__UI_7__</p>
<label>__UI_8__ <select id="decision"><option value="">__UI_9__</option><option value="accept">__UI_10__</option><option value="revise">__UI_11__</option><option value="reject">__UI_12__</option></select></label>
<label>__UI_13__ <select id="candidate"><option value="">__UI_9__</option>__OPTIONS__</select></label>
<textarea id="note" aria-label="__UI_14__" placeholder="__UI_15__"></textarea>
<label>__UI_16__ <select id="fit"><option value="unspecified">__UI_19__</option><option>__UI_20__</option><option>__UI_21__</option></select></label>
<label>__UI_17__ <select id="preservation"><option value="unspecified">__UI_19__</option><option>__UI_20__</option><option>__UI_21__</option></select></label>
<label>__UI_18__ <select id="usability"><option value="unspecified">__UI_19__</option><option>__UI_22__</option><option>__UI_23__</option></select></label>
<button id="download" type="button">__UI_24__</button><p id="message" role="status"></p>
<p>__UI_25__</p></section>
<dialog id="viewer" aria-labelledby="viewer-title">
<div class="viewer-header"><h2 id="viewer-title">__UI_26__</h2><button id="close-viewer" type="button" aria-label="__UI_27__">__UI_28__</button></div>
<div class="viewer-toolbar">
<button id="previous" type="button" aria-label="__UI_29__">←</button><label>__UI_31__ <select id="viewer-candidate"></select></label><button id="next" type="button" aria-label="__UI_30__">→</button>
<button id="zoom-out" type="button" aria-label="__UI_32__">−</button><input id="zoom" type="range" min="100" max="500" step="25" value="200" aria-label="__UI_33__"><output id="zoom-label" for="zoom">200%</output><button id="zoom-in" type="button" aria-label="__UI_34__">＋</button>
<button id="fit-window" type="button">__UI_35__</button><button id="viewer-background" type="button" aria-pressed="false">__UI_3__</button>
</div>
<p class="viewer-hint">__UI_36__</p>
<div id="viewport" class="viewport" tabindex="0" aria-label="__UI_37__"><div id="image-frame" class="image-frame"><img id="viewer-image" alt="" draggable="false"></div></div>
<p id="viewer-status" role="status" class="viewer-hint"></p>
</dialog>
<script>
'use strict';
const packet=__PACKET__,items=__VIEWER_ITEMS__,ui=__UI_STRINGS__;
const byId=id=>document.getElementById(id),viewer=byId('viewer'),viewport=byId('viewport'),frame=byId('image-frame'),picture=byId('viewer-image'),choice=byId('viewer-candidate');
let current=0,zoom=2,position={x:.5,y:.5},drag=null,loadSerial=0;
items.forEach((item,index)=>{const option=document.createElement('option');option.value=index;option.textContent=item.label;choice.append(option);});
function remember(){const width=frame.clientWidth||1,height=frame.clientHeight||1;return {x:(viewport.scrollLeft+viewport.clientWidth/2)/width,y:(viewport.scrollTop+viewport.clientHeight/2)/height};}
function layout(center=position){if(!viewer.open||!picture.naturalWidth||!picture.complete)return;const fit=Math.min(viewport.clientWidth/picture.naturalWidth,viewport.clientHeight/picture.naturalHeight);const width=picture.naturalWidth*fit*zoom,height=picture.naturalHeight*fit*zoom;picture.style.width=width+'px';picture.style.height=height+'px';frame.style.width=Math.max(viewport.clientWidth,width)+'px';frame.style.height=Math.max(viewport.clientHeight,height)+'px';viewport.scrollLeft=center.x*frame.clientWidth-viewport.clientWidth/2;viewport.scrollTop=center.y*frame.clientHeight-viewport.clientHeight/2;position=remember();byId('zoom').value=Math.round(zoom*100);byId('zoom-label').value=Math.round(zoom*100)+'%';}
function show(index,keepPosition=true){if(keepPosition&&picture.complete&&picture.naturalWidth)position=remember();current=(index+items.length)%items.length;choice.value=current;const item=items[current],serial=++loadSerial;byId('viewer-title').textContent=ui['大图预览']+' · '+item.label;picture.alt=item.label;byId('viewer-status').textContent=ui['加载中…'];picture.onload=()=>{if(serial!==loadSerial)return;layout();byId('viewer-status').textContent=item.label+' · '+picture.naturalWidth+' × '+picture.naturalHeight;};picture.onerror=()=>{if(serial===loadSerial)byId('viewer-status').textContent=ui['图片加载失败，请关闭后重试。'];};picture.src=item.src;}
function openViewer(index){position={x:.5,y:.5};zoom=2;viewer.showModal();document.body.classList.add('viewer-open');show(index,false);}
function setZoom(value){position=remember();zoom=Math.min(5,Math.max(1,value));layout();}
function toggleBackground(){const dark=document.body.classList.toggle('dark');for(const id of ['background','viewer-background'])byId(id).setAttribute('aria-pressed',String(dark));}
byId('background').onclick=byId('viewer-background').onclick=toggleBackground;
byId('open-viewer').onclick=()=>openViewer(0);
document.querySelectorAll('[data-viewer-index]').forEach(button=>button.onclick=()=>openViewer(Number(button.dataset.viewerIndex)));
byId('close-viewer').onclick=()=>viewer.close();viewer.addEventListener('close',()=>{document.body.classList.remove('viewer-open');drag=null;viewport.classList.remove('dragging');});
viewer.addEventListener('click',event=>{if(event.target!==viewer)return;const rect=viewer.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)viewer.close();});
byId('previous').onclick=()=>show(current-1);byId('next').onclick=()=>show(current+1);choice.onchange=()=>show(Number(choice.value));
byId('zoom-in').onclick=()=>setZoom(zoom+.25);byId('zoom-out').onclick=()=>setZoom(zoom-.25);byId('zoom').oninput=event=>setZoom(Number(event.target.value)/100);
byId('fit-window').onclick=()=>{zoom=1;position={x:.5,y:.5};layout();};
viewer.addEventListener('keydown',event=>{if(event.target.matches('input,select,textarea'))return;if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();show(current+(event.key==='ArrowLeft'?-1:1));}});
viewport.addEventListener('pointerdown',event=>{if(event.pointerType!=='mouse'||event.button!==0)return;event.preventDefault();viewport.focus();drag={id:event.pointerId,x:event.clientX,y:event.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};viewport.setPointerCapture(event.pointerId);viewport.classList.add('dragging');});
viewport.addEventListener('pointermove',event=>{if(!drag||drag.id!==event.pointerId)return;viewport.scrollLeft=drag.left+drag.x-event.clientX;viewport.scrollTop=drag.top+drag.y-event.clientY;position=remember();});
for(const name of ['pointerup','pointercancel','lostpointercapture'])viewport.addEventListener(name,()=>{drag=null;viewport.classList.remove('dragging');});
new ResizeObserver(()=>{if(viewer.open)layout(position);}).observe(viewport);
byId('download').onclick=()=>{const value=id=>byId(id).value;const decision=value('decision'),candidate=value('candidate'),note=value('note').trim();if(!decision||(decision!=='reject'&&!candidate)||(decision==='revise'&&!note)){byId('message').textContent=ui['请选择决定和候选；需要修改时请说明问题。'];return;}const data={packet,basis:'user',decision,candidate:decision==='reject'?null:candidate,note,facets:{fit:value('fit'),preservation:value('preservation'),usability:value('usability')}};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='charakit-feedback-'+packet+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);byId('message').textContent=ui['反馈已下载。将文件交给 Codex 后才会处理，不会在此页面自动打包。'];};
</script>
</html>
"""


def preview_text(language="zh-CN", translations=None, allow_legacy=False):
    import re
    if not isinstance(language, str) or not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*', language):
        raise ValueError('Use a language tag such as zh-CN, en or ja.')
    if translations is not None:
        keys = set(PREVIEW_EN)
        reference_keys = {'参考图', '仅参考指定修改内容'}
        revision_keys = {'修订前', '本次修改'}
        accepted = (keys, keys - revision_keys, keys - reference_keys, keys - reference_keys - revision_keys) if allow_legacy else (keys,)
        if not isinstance(translations, dict) or set(translations) not in accepted or not all(isinstance(v, str) and v.strip() and len(v) <= 2000 for v in translations.values()):
            raise ValueError('Supply a complete text mapping for the preview language.')
        return dict(translations)
    if language.lower().startswith('zh'):
        return {key: key for key in PREVIEW_EN}
    if language.lower().startswith('en'):
        return dict(PREVIEW_EN)
    raise ValueError('Supply translated UI text for this language with --ui-file.')


def script_json(value):
    return json.dumps(value, ensure_ascii=False).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')


def render_sheet(key, labels, request, contract, purpose, language="zh-CN", translations=None, revision=None, edit_references=None):
    ui = preview_text(language, translations, allow_legacy=not edit_references)
    if revision and not {'修订前', '本次修改'} <= set(ui):
        raise ValueError('Supply revision comparison labels for this page.')
    items = [{"label": ui['原图'], "src": "source.png"}]
    if revision:
        items.append({"label": ui['修订前'], "src": revision['source']})
        request = f"{request} · {ui['本次修改']}: {revision['note']}"
    items += [{"label": label, "src": f"{label}.png"} for label in labels]
    items += [{"label": ui['参考图']+' · '+ref['id'], "src": ref['path']} for ref in (edit_references or [])]
    cards = ''.join(f'<figure><figcaption>{html.escape(item["label"])}</figcaption><button class="image-button" type="button" data-viewer-index="{index}" aria-label="{html.escape(ui["放大查看"])} {html.escape(item["label"])}"><img src="{item["src"]}" alt="{html.escape(item["label"])}"></button></figure>' for index, item in enumerate(items))
    values = {
        '__REQUEST__': html.escape(str(request)), '__CARDS__': cards,
        '__CHECKS__': ''.join(f'<li>{html.escape(x["component"])} · {html.escape(x["property"])}：{html.escape(x["expected"])}</li>' for x in contract),
        '__OPTIONS__': ''.join(f'<option value="{label}">{label}</option>' for label in labels),
        '__PACKET__': script_json(key), '__VIEWER_ITEMS__': script_json(items),
        '__LANGUAGE__': html.escape(language), '__UI_STRINGS__': script_json(ui),
    }
    if edit_references:
        values['__CHECKS__'] += ''.join('<li>'+html.escape(ui['仅参考指定修改内容']+' · '+ref['id']+' · '+', '.join(ref['scope'])+'：'+ref['notes'])+'</li>' for ref in edit_references)
    values.update({f'__UI_{index}__': html.escape(ui[label]) for index, label in enumerate(PREVIEW_EN) if label in ui})
    # Substitute once: user prose that resembles a token remains literal text.
    import re
    return re.sub('|'.join(map(re.escape, values)), lambda match: values[match.group()], REVIEW_SHEET_TEMPLATE)


def refresh_review_sheet(c, root, key):
    """Add a fixed page for an unanswered packet without changing its aliases/evidence."""
    # contained() resolves paths, including Windows short directory names.
    root = root.resolve()
    state = c.read_state(root)
    packet = state.get('review_packets', {}).get(key)
    require(c, packet is not None and packet['purpose'] == 'user' and not packet.get('feedback'),
            'Refresh only an unanswered user review page.')
    packet_valid(c, root, state, packet)
    first = next(iter(packet['items'].values()))
    folder = c.contained(root, first['copy']).parent
    public_path = folder / 'packet.json'
    public = json.loads(public_path.read_text(encoding='utf-8'))
    language = public.get('language', 'zh-CN')
    page_ui = public.get('ui_labels')
    if page_ui and language.lower().split('-')[0] in ('zh', 'en'):
        page_ui = {**preview_text(language), **page_ui}
    number = 2
    while (folder / f'index-{number:03d}.html').exists():
        number += 1
    page = folder / f'index-{number:03d}.html'
    with page.open('x', encoding='utf-8') as stream:
        stream.write(render_sheet(key, list(packet['items']), public['request'], public['contract'], 'user', language, page_ui, public.get('revision'), public.get('edit_references')))
    packet.setdefault('artifacts', []).append({'path': page.relative_to(root).as_posix(), 'sha256': c.digest(page)})
    packet['latest_page'] = page.relative_to(root).as_posix()
    c.write_state(root, state)
    return {'packet': key, 'page': str(page.resolve()), 'public_packet': str(public_path.resolve()),
            **({'edit_references': [{**r, 'path': str((folder / r['path']).resolve())} for r in public['edit_references']]} if public.get('edit_references') else {}),
            **({'revision_parent': str((folder / 'parent.png').resolve()), 'revision_note': public['revision']['note']} if public.get('revision') else {}),
            'source': str((folder / 'source.png').resolve()),
            'candidates': {label: str(c.contained(root, item['copy']).resolve()) for label, item in packet['items'].items()}}


def compare(c, root, key, data):
    state = c.read_state(root)
    pool = state["candidate_pools"][key]
    assets = pool_assets(c, state, pool)
    require(c, pool_status(c, root, key)["action"] == "compare", "Comparison is not pending.")
    packet = state.get("review_packets", {}).get(data.get("packet"))
    require(c, packet is not None and packet["purpose"] == "assistant"
            and {x["asset_id"] for x in packet["items"].values()} == {a["id"] for a in assets}, "Use a fresh anonymous comparison of this pool.")
    packet_valid(c, root, state, packet)
    require(c, data.get("basis") == "assistant" and data.get("preferred") in (*packet["items"], None)
            and type(data.get("repairable")) is bool and c.valid_edit_text(data.get("evidence"), 2000), "Record preference/tie, evidence and whether one bounded repair is feasible.")
    preferred = packet["items"][data["preferred"]]["asset_id"] if data["preferred"] else None
    passed = [a["id"] for a in assets if eligible(c, root, state, a)]
    require(c, not passed or preferred in passed, "A failed candidate cannot outrank a passing candidate.")
    if data["repairable"] and pool["version"] == "1.0":
        require(c, preferred is not None and not passed and c.valid_edit_text(data.get("repair_plan"), 2000), "Explain one localized, feasible repair to a named candidate.")
        review = c.get_asset(state, preferred)["quality_review"]
        scores = [v["score"] for v in review["dimensions"].values()]
        require(c, min(scores) >= 3 and review["dimensions"]["target"]["score"] >= 4
                and sum(s < 4 for s in scores) <= 2 and not review["critical_defects"] and not review["uncertainties"],
                "Only an achieved target with at most two modest defects and sufficient evidence is eligible for one repair.")
    record = {**data, "preferred": preferred, "asset_ids": [a["id"] for a in assets], "created_at": c.timestamp()}
    pool["comparisons"].append(record)
    c.write_state(root, state)
    return pool_status(c, root, key)


def human_feedback(c, root, data):
    state = c.read_state(root)
    packet = state.get("review_packets", {}).get(data.get("packet"))
    require(c, packet is not None and packet["purpose"] == "user", "Use an existing user review packet.")
    packet_valid(c, root, state, packet)
    require(c, data.get("basis") == "user" and data.get("decision") in ("accept", "revise", "reject")
            and isinstance(data.get("note"), str) and len(data["note"]) <= 4000, "Record actual user feedback, not an assistant prediction.")
    require(c, data["decision"] == "reject" or data.get("candidate") in packet["items"], "Choose a displayed alias.")
    require(c, data["decision"] != "revise" or bool(data["note"].strip()), "Record the requested change.")
    if packet.get("feedback"):
        require(c, packet["feedback"]["input"] == data, "This packet already has feedback; create a new packet for a changed decision.")
        return packet["feedback"]["result"]
    chosen = packet["items"].get(data.get("candidate")) if data["decision"] != "reject" else None
    target_ids = [chosen["asset_id"]] if chosen else [v["asset_id"] for v in packet["items"].values()]
    for aid in target_ids:
        asset = c.get_asset(state, aid)
        for revision in state.get("human_revisions", {}).values():
            if revision["status"] == "reserved" and revision["parent_asset"] == aid and revision["packet"] != data["packet"]:
                revision.update(status="cancelled", cancelled_by=data["packet"], cancelled_at=c.timestamp())
        record = {"basis": "user", "decision": data["decision"], "note": data["note"], "facets": data.get("facets", {}),
                  "packet": data["packet"], "asset_sha256": asset["sha256"], "source_sha256": state["source_sha256"],
                  "quality_sha256": c.review_fingerprint(asset.get("quality_review", {})), "recorded_at": c.timestamp()}
        asset.setdefault("human_feedback_history", []).append(record)
        asset["human_feedback"] = record
        if data["decision"] != "accept":
            asset["art_review_status"] = "rejected" if data["decision"] == "reject" else "unreviewed"
            if state["selected"].get(c.asset_slot(asset)) == aid:
                del state["selected"][c.asset_slot(asset)]
        if asset.get("candidate_pool"):
            state["candidate_pools"][asset["candidate_pool"]]["stopped"] = True
    # Save positive opinions even when technical/visual gates prevent acceptance.
    result = {"decision": data["decision"], "asset_ids": target_ids, "next_action": "revision_request" if data["decision"] == "revise" else "stopped"}
    if data["decision"] == "revise":
        result["revision"] = {"packet": data["packet"], "parent_asset": chosen["asset_id"],
                              "note": data["note"], "budget": 3, "prepare_command": "revision-prepare"}
    if chosen and data["decision"] == "accept":
        asset = c.get_asset(state, chosen["asset_id"])
        # A new explicit decision may supersede rejection, without rewriting its history.
        asset["art_review_status"] = "unreviewed"
        if eligible(c, root, state, asset) and c.check_asset(root, state, asset)["passed"]:
            asset.update(art_review_status="accepted", review_note=data["note"], reviewed_at=c.timestamp())
            state["selected"][c.asset_slot(asset)] = asset["id"]
            result["next_action"] = "export"
        else:
            result["next_action"] = "blocked"
            result["blockers"] = {"quality": c.quality_status(root, state, asset), "fidelity": c.fidelity_status(asset), "technical": c.check_asset(root, state, asset)["errors"]}
    packet["feedback"] = {"input": copy.deepcopy(data), "result": result}
    c.write_state(root, state)
    return result


def validate_blind_record(c, root, state, asset, review):
    packet = state.get("review_packets", {}).get(review.get("blind_packet"))
    require(c, packet is not None and packet["purpose"] == "assistant"
            and any(v["asset_id"] == asset["id"] for v in packet["items"].values()), "Missing blind inspection evidence.")
    packet_valid(c, root, state, packet)


def require_user_feedback(c, root, state, asset):
    if "candidate_pool" not in asset:
        require(c, asset.get("edit_type") not in ("outfit_replace", "prop_edit") and "edit_references" not in asset,
                "Full outfits and prop edits require a candidate pool and actual user acceptance.", "HUMAN_REVIEW_REQUIRED")
        return
    feedback = asset.get("human_feedback", {})
    require(c, feedback.get("decision") == "accept" and feedback.get("basis") == "user"
            and feedback.get("asset_sha256") == asset["sha256"] and feedback.get("source_sha256") == state["source_sha256"]
            and feedback.get("quality_sha256") == c.review_fingerprint(asset.get("quality_review", {})),
            "Present the review sheet and record the user's actual acceptance before packaging.", "HUMAN_REVIEW_REQUIRED")
    packet = state.get("review_packets", {}).get(feedback.get("packet"))
    require(c, packet is not None and packet.get("feedback", {}).get("input", {}).get("decision") == "accept", "Missing user review packet.")
    packet_valid(c, root, state, packet)


def add_commands(c, commands):
    for name in ("pool-start", "pool-status", "pool-reserve", "pool-import", "pool-fail", "pool-compare", "review-sheet", "refresh-review-sheet", "human-feedback", "revision-prepare", "revision-import", "revision-fail"):
        p = commands.add_parser(name)
        p.add_argument("--project", type=Path, required=True)
        if name == "pool-start":
            p.add_argument("--asset", required=True)
            p.add_argument("--contract-file", type=Path, required=True)
            p.add_argument("--budget", type=int, choices=(1, 2, 3), default=3)
        elif name.startswith("pool-"):
            p.add_argument("--case", dest="case_id", required=True)
        if name in ("pool-import", "pool-fail"):
            p.add_argument("--token", required=True)
        if name == "pool-import":
            p.add_argument("--image", type=Path, required=True)
            p.add_argument("--prompt-file", type=Path, required=True)
            p.add_argument("--reference", type=Path, action="append", required=True)
        if name == "pool-fail":
            p.add_argument("--note", required=True)
        if name in ("pool-compare", "human-feedback"):
            p.add_argument("--feedback-file", type=Path, required=True)
        if name == "review-sheet":
            p.add_argument("--asset", action="append", required=True)
            p.add_argument("--purpose", choices=("assistant", "user"), default="user")
            p.add_argument("--language", default="zh-CN", help="Match the user's language; built-in zh-CN/en, or supply --ui-file for another language.")
            p.add_argument("--ui-file", type=Path, help="Complete UTF-8 mapping of preview UI text to the user's language.")
        if name == "refresh-review-sheet":
            p.add_argument("--packet", required=True)
        if name == "revision-prepare":
            p.add_argument("--packet", required=True)
            p.add_argument("--contract-file", type=Path, required=True)
            p.add_argument("--budget", type=int, choices=(1, 2, 3), default=None)
        if name in ("revision-import", "revision-fail"):
            p.add_argument("--revision", required=True)
        if name == "revision-import":
            p.add_argument("--image", type=Path, required=True)
            p.add_argument("--prompt-file", type=Path, required=True)
            p.add_argument("--reference", type=Path, action="append", required=True)
        if name == "revision-fail":
            p.add_argument("--note", required=True)


def dispatch(c, args):
    def read(path):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise c.StudioError("INVALID_REVIEW_FILE", "Cannot read review JSON.") from exc
    root = args.project.resolve()
    if args.command == "pool-start":
        return pool_start(c, root, args.asset, read(args.contract_file), args.budget)
    if args.command == "pool-status":
        return pool_status(c, root, args.case_id)
    if args.command == "pool-reserve":
        return pool_reserve(c, root, args.case_id)
    if args.command == "pool-import":
        return pool_import(c, root, args.case_id, args.token, args.image, args.prompt_file, args.reference)
    if args.command == "pool-fail":
        return pool_import(c, root, args.case_id, args.token, None, None, None, args.note)
    if args.command == "pool-compare":
        return compare(c, root, args.case_id, read(args.feedback_file))
    if args.command == "review-sheet":
        return review_sheet(c, root, args.asset, args.purpose, args.language, read(args.ui_file) if args.ui_file else None)
    if args.command == "refresh-review-sheet":
        return refresh_review_sheet(c, root, args.packet)
    if args.command == "revision-prepare":
        return revision_prepare(c, root, args.packet, read(args.contract_file), args.budget)
    if args.command == "revision-import":
        return revision_import(c, root, args.revision, args.image, args.prompt_file, args.reference)
    if args.command == "revision-fail":
        return revision_import(c, root, args.revision, None, None, None, args.note)
    return human_feedback(c, root, read(args.feedback_file))
