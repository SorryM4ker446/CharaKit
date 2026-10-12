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


CONTINUITY_CHECK = {'id': 'revision_continuity', 'dimension': 'protection',
                    'component': 'Successful authorized edits', 'property': 'Revision continuity',
                    'expected': 'Retain established authorized results outside the current correction; do not restore superseded source details.',
                    'view': 'full_image'}
SOURCE_RECHECK = {'id': 'source_protection_recheck', 'dimension': 'protection',
                 'component': 'Original protected remainder', 'property': 'Secondary source preservation review',
                 'expected': 'Compare still-protected regions with the immutable source; exclude all authorized edits and necessary interfaces. Record visible drift without reverting successful authorized changes.',
                 'view': 'protected_details'}


def revision_checks(language):
    check, source = copy.deepcopy(CONTINUITY_CHECK), copy.deepcopy(SOURCE_RECHECK)
    if language.lower().startswith('zh'):
        check.update(component='已完成的授权修改', property='修订成果保留',
                     expected='保留当前修订范围之外已完成的成果，不恢复原图中已被替换的特征。')
        source.update(component='最初原图中的受保护区域', property='原图保护区域二次复查',
                      expected='与最初原图复查仍受保护的区域，排除全部已授权修改及必要交界；记录可见偏移，不恢复已完成的服装、道具、表情或姿势修改。')
    return [check, source]


def revision_policy(state, asset):
    return state.get('human_revisions', {}).get(asset.get('human_revision'), {}).get('policy')


def planned_references(c, root, state, asset, parent=None, policy=None):
    return c.reference_call('bindings', root, state, asset, parent, bool(policy))


def validate_policy(c, state, revision):
    policy = revision.get('policy')
    if policy is None:
        return
    require(c, isinstance(policy, dict) and set(policy) == {'version', 'baseline_asset', 'restore_checks', 'inspection_regions'}
            and policy['version'] == '1.0' and policy['baseline_asset'] == revision['parent_asset'],
            'Invalid revision baseline policy.')
    checks = {x['id']: x for x in revision['contract']}
    require(c, isinstance(policy['restore_checks'], list)
            and all(isinstance(x, str) and x in checks and checks[x]['dimension'] in ('identity', 'protection')
                    and x not in ('revision_continuity', 'source_protection_recheck') for x in policy['restore_checks'])
            and len(set(policy['restore_checks'])) == len(policy['restore_checks']),
            'Source restoration must name explicit identity/protection checks.')
    continuity = checks.get('revision_continuity', {})
    require(c, continuity.get('dimension') == 'protection' and continuity.get('view') == 'full_image',
            'New revisions must inspect preservation of successful edits.')
    source_check = checks.get('source_protection_recheck', {})
    require(c, source_check.get('dimension') == 'protection' and source_check.get('view') == 'protected_details',
            'New revisions must recheck still-protected regions against the original source.')
    validate_regions(c, policy['inspection_regions'], state['canvas'])


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
    if "pose_id" in asset:
        require(c, any(check["dimension"] == "target" and check["component"] == asset["target"] for check in contract),
                "Pose contracts must include a target check for the actual action, anatomical side and hand orientation.")
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
        require(c, key in by_id and pool.get("version") in ("1.0", "1.1", "1.2") and pool.get("slot") == c.asset_slot(by_id[key])
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
            prior = [by_id[a['asset_id']] for a in attempts[:n-1] if a['status'] == 'imported']
            restart = source_restart_evidence(c, pool, prior) if n > 1 else None
            expected_strategy = (("user_revision" if pool.get("human_revision") else "source_sample") if n == 1 else
                                 ("source_restart" if restart else "review_redraw") if pool['version'] in ('1.1', '1.2') else
                                 ("user_revision" if pool.get("human_revision") else "source_sample" if n == 2 else "repair_best"))
            require(c, attempt["number"] == n and attempt["status"] in ("reserved", "imported", "failed")
                    and attempt["strategy"] == expected_strategy, "Invalid attempt order.")
            require(c, attempt.get('restart_evidence') == restart, 'Source restarts require unchanged recorded stall evidence.')
            if restart:
                require(c, attempt.get('references') == [
                    {'path': state['source'], 'sha256': state['source_sha256'], 'role': 'immutable_source'}
                ] + by_id[key].get('edit_references', []), 'Source restarts exclude the failed candidate from image inputs.')
            if attempt["status"] == "imported":
                aid = attempt["asset_id"]
                require(c, aid in by_id and aid not in seen and by_id[aid].get("candidate_pool") == key
                        and c.asset_slot(by_id[aid]) == pool["slot"] and "refinement_case" not in by_id[aid], "Invalid pool member.")
                seen.add(aid)
            if by_id[key].get("edit_references") or "pose_id" in by_id[key]:
                require(c, pool["version"] in ("1.1", "1.2"), "Scoped references require the review/redraw workflow.")
                expected = copy.deepcopy(by_id[key]["generation_inputs"]["references"])
                if n > 1:
                    parent = by_id.get(attempt.get("parent"))
                    require(c, parent is not None, "A reference-aware redraw needs its recorded parent.")
                    expected = [{"path": state["source"], "sha256": state["source_sha256"], "role": "immutable_source"}]
                    if not restart:
                        expected.append({"path": parent["path"], "sha256": parent["sha256"], "role": "edit_target"})
                    if revision_policy(state, by_id[key]):
                        expected.reverse()
                    expected += copy.deepcopy(by_id[key].get("edit_references", []))
                require(c, attempt.get("references") == expected, "Attempt references must preserve paths, roles, hashes and editable scopes.")
                if attempt["status"] == "imported":
                    member = by_id[attempt["asset_id"]]
                    require(c, member.get("edit_references") == by_id[key].get("edit_references")
                            and member.get("generation_inputs", {}).get("references") == expected
                            and member["generation_inputs"]["strategy"] == attempt["strategy"], "Imported references differ from their reserved attempt.")
            if pool['version'] in ('1.1', '1.2') and n > 1:
                parent = by_id.get(attempt.get('parent'))
                require(c, parent is not None and parent['id'] in {a.get('asset_id') for a in attempts[:n-1] if a['status']=='imported'}
                        and parent.get('quality_review') is not None
                        and attempt.get('review_sha256') == c.review_fingerprint(parent['quality_review'])
                        and attempt.get('blocking_findings') == redraw_findings(parent)
                        and bool(attempt.get('blocking_findings')),
                        "Redraws must retain the assessed parent's failure evidence.")
                paths = ([state['source']] if restart else
                         [parent['path'], state['source']] if revision_policy(state, by_id[key]) else [state['source'], parent['path']])
                require(c, [r['path'] for r in attempt.get('references', [])] == paths + [r['path'] for r in by_id[key].get('edit_references', [])],
                        "Redraws retain their recorded editing baseline and source context.")
                if revision_policy(state, by_id[key]):
                    require(c, attempt.get('revision_policy') == revision_policy(state, by_id[key]), 'Redraws retain the revision policy.')
                if attempt['status'] == 'imported':
                    require(c, by_id[attempt['asset_id']]['parent_asset_id'] == parent['id'], "Invalid redraw lineage.")
                    if pool['version'] == '1.2':
                        inputs = by_id[attempt['asset_id']].get('generation_inputs', {})
                        require(c, all(inputs.get(k) == attempt.get(k) for k in
                                       ('strategy', 'parent', 'references', 'restart_evidence', 'blocking_findings', 'review_sha256')),
                                'Imported redraw provenance differs from the reserved attempt.')
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
        validate_policy(c, state, revision)
        if parent.get("edit_references"):
            expected = [{"path": state["source"], "sha256": state["source_sha256"], "role": "immutable_source"},
                        {"path": parent["path"], "sha256": parent["sha256"], "role": "edit_target"}]
            if revision.get('policy'):
                expected.reverse()
            expected += copy.deepcopy(parent["edit_references"])
            require(c, revision.get("pool_version") == "1.1" and revision.get("references") == expected,
                    "Human revision inputs retain source, chosen parent and every scoped reference.")
        elif revision.get('policy'):
            expected = [{'path': parent['path'], 'sha256': parent['sha256'], 'role': 'edit_target'},
                        {'path': state['source'], 'sha256': state['source_sha256'], 'role': 'immutable_source'}]
            require(c, revision.get('references') == expected, 'Revision references must match the chosen baseline.')
        if revision["status"] == "imported":
            aid = revision.get("asset_id")
            require(c, aid in by_id and by_id[aid].get("human_revision") == key
                    and by_id[aid].get("parent_asset_id") == parent["id"]
                    and c.asset_slot(by_id[aid]) == c.asset_slot(parent)
                    and aid in pools and pools[aid].get("human_revision") == key
                    and pools[aid]["budget"] == revision.get("budget", 1) and pools[aid]["contract"] == revision["contract"],
                    "Invalid imported human revision.")
            require(c, all(by_id[aid].get(field) == parent.get(field) for field in
                          ("expression", "mouth_state", "pose_id", "pose", "side", "anchors", "outfit_id", "edit_type", "target", "color", "replacement", "outfit_components", "prop_action", "edit_brief", "edit_references")),
                    "Human revisions retain their chosen parent's edit definition and brief.")
            if revision.get('policy'):
                require(c, by_id[aid].get('generation_inputs', {}).get('revision_policy') == revision['policy'],
                        'Imported revision must retain its baseline policy.')
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
            "edit": {k: copy.deepcopy(parent[k]) for k in ("expression", "mouth_state", "pose_id", "pose", "side", "anchors", "outfit_id", "edit_type", "target", "color", "replacement", "outfit_components", "prop_action", "edit_brief", "edit_references") if k in parent},
            "references": copy.deepcopy(revision["references"]),
            "reference_paths": [str(c.contained(root, item["path"])) for item in revision["references"]],
            **({'revision_policy': copy.deepcopy(revision['policy']),
                'edit_target': str(c.contained(root, parent['path'])),
                'source_context': str(c.contained(root, state['source'])),
                'instructions': 'Edit the chosen candidate as the primary baseline. Preserve successful edits outside the correction. Recheck still-protected regions against the source and correct documented unauthorized drift or explicitly named restoration checks. Never restore superseded clothing, objects, expression states or poses.'} if revision.get('policy') else {}),
            "asset_id": revision.get("asset_id"), "failure": revision.get("failure"),
            "next_action": {"reserved": "generate_revision", "imported": "review", "failed": "stopped", "cancelled": "stopped"}[revision["status"]]}


def revision_prepare(c, root, key, contract, budget=None, restore_checks=None, inspection=None):
    root = root.resolve()
    state = c.read_state(root)
    existing = state.get("human_revisions", {}).get(key)
    contract = copy.deepcopy(contract)
    validate_contract(c, contract)
    if not existing or existing.get('policy'):
        if not {'revision_continuity', 'source_protection_recheck'} <= {x['id'] for x in contract}:
            language = 'en'
            packet = state.get('review_packets', {}).get(key)
            if packet and packet.get('items'):
                packet_valid(c, root, state, packet)
                folder = c.contained(root, next(iter(packet['items'].values()))['copy']).parent
                language = json.loads((folder/'packet.json').read_text(encoding='utf-8')).get('language', 'en')
            for check in revision_checks(language):
                if not any(x['id'] == check['id'] for x in contract):
                    contract.append(check)
    if existing:
        require(c, existing["contract"] == contract and (budget is None or budget == existing.get("budget", 1)), "Cannot rewrite or reset an existing human revision.")
        if existing["status"] == "reserved":
            revision_origin(c, root, state, key)
        if existing.get('policy'):
            require(c, (restore_checks is None or restore_checks == existing['policy']['restore_checks'])
                    and (inspection is None or inspection == existing['policy']['inspection_regions']),
                    'Cannot reset the recorded restoration scope or inspection plan.')
        else:
            require(c, restore_checks is None and inspection is None, 'Legacy pending revisions retain their original policy.')
        return revision_plan(c, root, state, key)
    parent, feedback = revision_origin(c, root, state, key)
    budget = 3 if budget is None else budget
    require(c, type(budget) is int and 1 <= budget <= 3, "Use one to three total attempts.")
    validate_revision_contract(c, state, parent, contract)
    require(c, not any(r["status"] == "reserved" and c.asset_slot(c.get_asset(state, r["parent_asset"])) == c.asset_slot(parent)
                      for r in state.get("human_revisions", {}).values()), "Another human revision is pending.", "HUMAN_REVISION_NOT_READY")
    policy = {'version': '1.0', 'baseline_asset': parent['id'], 'restore_checks': restore_checks if restore_checks is not None else [],
              'inspection_regions': inspection if inspection is not None else []}
    validate_policy(c, state, {'policy': policy, 'parent_asset': parent['id'], 'contract': contract})
    references = planned_references(c, root, state, parent, parent, policy)
    state.setdefault("human_revisions", {})[key] = {
        "packet": key, "parent_asset": parent["id"], "parent_sha256": parent["sha256"],
        "source_sha256": state["source_sha256"], "parent_quality_sha256": c.review_fingerprint(parent["quality_review"]),
        "note": feedback["note"], "contract": copy.deepcopy(contract), "references": references,
        "status": "reserved", "budget": budget, "pool_version": "1.1", 'policy': policy, "created_at": c.timestamp()}
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
    fields = {k: copy.deepcopy(parent[k]) for k in ("expression", "mouth_state", "pose_id", "pose", "side", "anchors", "outfit_id", "edit_type", "target", "color", "replacement", "outfit_components", "prop_action", "edit_brief", "edit_references") if k in parent}
    fields.update(human_revision=key, quality_required=c.QUALITY_VERSION,
                  generation_inputs={"strategy": "user_revision", "references": copy.deepcopy(revision["references"]), "packet": key})
    if revision.get('policy'):
        fields['generation_inputs']['revision_policy'] = copy.deepcopy(revision['policy'])
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
    if asset.get("edit_references") or "pose_id" in asset:
        initial["references"] = copy.deepcopy(asset["generation_inputs"]["references"])
    state.setdefault("candidate_pools", {})[aid] = {
        "version": "1.2", "slot": c.asset_slot(asset), "budget": budget, "contract": copy.deepcopy(contract),
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


TARGET_DOMAIN_CHECKS = {
    'expression': ('emotion',), 'mouth_state': ('emotion', 'mouth_state'),
    'garment_recolor': ('target_color',), 'garment_replace': ('target_garment',),
    'outfit_replace': ('outfit_design', 'component_completion', 'ensemble_coherence'),
    'prop_edit': ('target_object',), 'pose_edit': ('target_pose',),
}
PROTECTED_DOMAIN_CHECKS = {
    'face_design': 'identity', 'face_expression': 'identity',
    'nonface_protection': 'protection', 'non_target_protection': 'protection',
    'garment_invariants': 'protection', 'framing_anchors': 'protection',
}


def source_restart_evidence(c, pool, assets):
    """Route from saved observations, not a new visual or similarity judgment."""
    if pool['version'] != '1.2' or pool.get('human_revision') or len(assets) < 2:
        return None
    previous, current = assets[-2:]
    reviews = [a.get('quality_review', {}) for a in (previous, current)]
    for asset, review in zip((previous, current), reviews):
        domain = review.get('domain_review', {})
        target_checks = TARGET_DOMAIN_CHECKS.get(domain.get('kind'))
        if (not target_checks or not all(review.get('inspection', {}).values())
                or review.get('dimensions', {}).get('target', {}).get('score', 0) < 4
                or not all(x['status'] == 'passed' for x in review.get('criteria', []) if x['dimension'] == 'target')
                or any(domain.get('checks', {}).get(k, {}).get('status') != 'passed' for k in target_checks)
                or any(x['status'] != 'passed' for x in domain.get('component_checks', {}).values())
                or asset.get('fidelity_review', {}).get('target_check', 'passed') != 'passed'):
            return None
    before, after = reviews
    earlier = {x['id']: x for x in before['criteria']}
    checks = []
    for item in after['criteria']:
        old = earlier.get(item['id'], {})
        if (item['dimension'] in ('identity', 'protection') and item['status'] == old.get('status') == 'failed'
                and item['score'] <= old['score']):
            checks.append(dict(kind='criterion', id=item['id'], dimension=item['dimension'],
                               previous_score=old['score'], current_score=item['score']))
    for key, dimension in PROTECTED_DOMAIN_CHECKS.items():
        if (before['domain_review']['checks'].get(key, {}).get('status') == 'failed'
                and after['domain_review']['checks'].get(key, {}).get('status') == 'failed'
                and after['dimensions'][dimension]['score'] <= before['dimensions'][dimension]['score']):
            checks.append(dict(kind='domain', id=key, dimension=dimension,
                               previous_score=before['dimensions'][dimension]['score'], current_score=after['dimensions'][dimension]['score']))
    if (all(a.get('fidelity_review', {}).get('protection_check') == 'failed' for a in (previous, current))
            and after['dimensions']['protection']['score'] <= before['dimensions']['protection']['score']):
        checks.append(dict(kind='fidelity', id='protection_check', dimension='protection',
                           previous_score=before['dimensions']['protection']['score'], current_score=after['dimensions']['protection']['score']))
    if not checks:
        return None
    return dict(asset_ids=[a['id'] for a in (previous, current)],
                review_sha256=[c.review_fingerprint(r) for r in reviews],
                fidelity_sha256=[c.review_fingerprint(a.get('fidelity_review', {})) for a in (previous, current)], checks=checks)


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
    elif pool["version"] in ("1.1", "1.2"):
        action = "redraw"
    elif len(pool["attempts"]) == 1:
        action = "sample"
    elif ranking and ranking["repairable"] and ranking["preferred"]:
        action = "repair"
    else:
        action = "exhausted"
    restart = source_restart_evidence(c, pool, assets) if action == 'redraw' else None
    return {"case_id": key, "action": action, "used": len(pool["attempts"]), "budget": pool["budget"],
            "best_asset": best["id"] if best else None, "passed_assets": [a["id"] for a in passed],
            "preferred_asset": ranking["preferred"] if ranking else (best["id"] if best else None),
            "attempts": pool["attempts"], "contract": pool["contract"],
            "repair_parent": (ranking["preferred"] if ranking and ranking["preferred"] else assets[-1]["id"]) if action in ("repair", "redraw") else None,
            "blocking_findings": {a["id"]: redraw_findings(a) for a in assets if not eligible(c, root, state, a)},
            "next_strategy": ('source_restart' if restart else 'review_redraw') if action == 'redraw' else None,
            "restart_evidence": restart,
            "note": "User feedback is required before acceptance/export. Failed candidates remain inspection evidence."}


def pool_reserve(c, root, key):
    plan = pool_status(c, root, key)
    require(c, plan["action"] in ("sample", "repair", "redraw"), "No additional generation is currently permitted.", "POOL_NOT_READY")
    state = c.read_state(root)
    pool = state["candidate_pools"][key]
    refs = [state["source"]]
    restart = plan['next_strategy'] == 'source_restart'
    if plan["repair_parent"] and not restart:
        refs.append(c.get_asset(state, plan["repair_parent"])["path"])
    attempt = {"number": len(pool["attempts"]) + 1, "status": "reserved", "token": secrets.token_hex(12),
               "strategy": plan['next_strategy'] or {"sample": "source_sample", "repair": "repair_best"}[plan["action"]],
               "parent": plan["repair_parent"], "references": [{"path": p, "sha256": c.digest(c.contained(root, p))} for p in refs]}
    original = c.get_asset(state, key)
    policy = revision_policy(state, original)
    if original.get("edit_references") or "pose_id" in original or restart:
        parent = c.get_asset(state, plan["repair_parent"]) if plan["repair_parent"] else None
        attempt["references"] = planned_references(c, root, state, original, None if restart else parent, policy)
        refs = [r["path"] for r in attempt["references"]]
    elif policy:
        attempt['references'] = planned_references(c, root, state, original, c.get_asset(state, plan['repair_parent']), policy)
        refs = [r['path'] for r in attempt['references']]
    if policy:
        attempt['revision_policy'] = copy.deepcopy(policy)
    if restart:
        attempt['restart_evidence'] = copy.deepcopy(plan['restart_evidence'])
    if plan["repair_parent"]:
        attempt["repair_plan"] = (pool["comparisons"][-1]["repair_plan"] if plan["action"] == "repair" else
                                  "Correct the attached failed checks; retain the fixed contract and successful edits. The immutable source controls identity, protected attributes and framing; do not copy failed properties from the candidate.")
        if policy:
            attempt['repair_plan'] = 'Correct the recorded failures on the named edit target. Retain successful changes relative to the user-chosen baseline. Use source context to repair documented drift in still-protected regions or explicitly named restoration checks; never reintroduce superseded source features.'
        if restart:
            attempt['repair_plan'] = 'Reapply the fixed requested edit to the immutable source using the contract, brief and all scoped references. Preserve the successful target through its recorded action/design requirements. The failed parent is review evidence only and is not an image input; do not attach it or reproduce its identity/protection drift.'
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
    fields = {k: copy.deepcopy(original[k]) for k in ("expression", "mouth_state", "pose_id", "pose", "side", "anchors", "outfit_id", "target", "color", "replacement", "edit_type", "outfit_components", "prop_action", "edit_brief", "edit_references") if k in original}
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


def user_review_candidates(c, root, state, requested, selection_note):
    """Select the whole batch by default; record every explicit or file-based omission."""
    require(c, selection_note is None or c.valid_edit_text(selection_note, 1000), "Record the user's actual request for a restricted view.")
    keys = {a.get("candidate_pool") for a in requested}
    require(c, len(keys) == 1, "A user review must cover one batch, not different revision requests.")
    key = next(iter(keys))
    pool = state.get("candidate_pools", {}).get(key)
    members = pool_assets(c, state, pool) if pool else requested
    visible, omissions = [], []
    requested_ids = {a["id"] for a in requested}
    for asset in members:
        report = c.delivery_validation(c.check_asset(root, state, asset))
        if not report["passed"]:
            # Reference changes affect the entire edit contract and cannot be omitted.
            require(c, set(report["errors"]) <= {"FILE_NOT_FOUND", "INVALID_IMAGE", "IMAGE_TOO_LARGE", "ASSET_CHANGED", "OUTPUT_NOT_PNG", "EMPTY_IMAGE"},
                    "Resolve changed reference inputs or other edit constraints before human review.")
            omissions.append({"asset_id": asset["id"], "reason": "unavailable_file", "errors": report["errors"]})
        elif selection_note and asset["id"] not in requested_ids:
            omissions.append({"asset_id": asset["id"], "reason": "user_requested_subset", "note": selection_note})
        else:
            visible.append(asset)
    require(c, bool(visible), "No unchanged, readable candidates can be shown.")
    require(c, all("quality_review" in a and c.quality_status(root, state, a) != "stale" for a in visible),
            "Complete internal assessment before human review.")
    if pool and pool.get("version") in ("1.1", "1.2"):
        action = pool_status(c, root, key)["action"]
        finished = action in ("human_review", "exhausted", "export", "stopped")
        if action == "blocked" and any(x["reason"] == "unavailable_file" for x in omissions):
            # Permit inspection of the remaining intact images only after the batch ended.
            finished = (pool["attempts"][-1]["status"] != "reserved"
                        and all("quality_review" in a and c.fidelity_status(a) != "pending" for a in members)
                        and (len(pool["attempts"]) >= pool["budget"] or any(eligible(c, root, state, a) for a in visible)))
        require(c, finished, "Finish internal review and redraw within the fixed budget before human review.", "INTERNAL_REVIEW_INCOMPLETE")
    return visible, members, pool, omissions


def user_review_summary(c, root, state, assets, members, pool, items, omissions):
    aliases = {v["asset_id"]: label for label, v in items.items()}
    ranking = next((x for x in reversed((pool or {}).get("comparisons", []))
                    if x["asset_ids"] == [a["id"] for a in members]), None)
    preferred = ranking.get("preferred") if ranking else None
    recommendation = None
    if preferred in aliases:
        recommendation = {"candidate": aliases[preferred], "basis": "recorded_comparison", "evidence": ranking["evidence"]}
    elif not ranking:
        passed = next((a for a in assets if eligible(c, root, state, a)), None)
        if passed:
            recommendation = {"candidate": aliases[passed["id"]], "basis": "internal_pass", "evidence": ""}
    return {"generated": len(members), "displayed": len(assets),
            "omissions": [{k: v for k, v in x.items() if k != "asset_id"} for x in omissions],
            "failed_calls": [{"number": x["number"], "failure": x["failure"]} for x in (pool or {}).get("attempts", []) if x["status"] == "failed"],
            "recommendation": recommendation,
            "candidates": {aliases[a["id"]]: {"status": "passed" if c.quality_status(root, state, a) == "passed" and c.fidelity_status(a) not in ("pending", "failed", "uncertain") else "failed",
                                              "findings": redraw_findings(a)} for a in assets}}


def validate_regions(c, regions, canvas):
    require(c, isinstance(regions, list) and len(regions) <= 4,
            'Use at most four focused inspection regions, or an empty list for full images only.', 'INVALID_REVIEW_BOX')
    ids = set()
    for region in regions:
        require(c, isinstance(region, dict) and set(region) == {'id', 'box', 'label', 'reason'}
                and c.valid_outfit_id(region.get('id')) and region['id'] not in ('full', 'source', 'parent')
                and region['id'] not in ids and c.valid_source_box(region.get('box'), canvas)
                and c.valid_edit_text(region.get('label'), 100) and c.valid_edit_text(region.get('reason'), 1000),
                'Each inspection region needs a unique ID, source-coordinate box, localized label and task/risk reason.', 'INVALID_REVIEW_BOX')
        ids.add(region['id'])


def inspection_regions(c, state, assets, face_box, detail_box, requested=None):
    """Inspection boxes locate source pixels; they never align or modify artwork."""
    regions = []
    if requested is not None:
        require(c, face_box is None and detail_box is None, 'Use an inspection plan or individual boxes, not both.', 'INVALID_REVIEW_BOX')
        validate_regions(c, requested, state['canvas'])
        return copy.deepcopy(requested)
    if detail_box is None and state.get('module') != 'poses':
        boxes = [a.get('edit_brief', {}).get('target_box') for a in assets]
        if boxes and boxes[0] and all(box == boxes[0] for box in boxes):
            detail_box = boxes[0]
    for name, box in (('face', face_box), ('target', detail_box)):
        if box is not None:
            require(c, c.valid_source_box(box, state['canvas']),
                    'Inspection boxes must be integer coordinates inside the source canvas.', 'INVALID_REVIEW_BOX')
            regions.append({'id': name, 'box': list(box)})
    return regions


def inspection_images(c, folder, canvas, regions, labels, revision):
    from PIL import Image
    entries = [('source', 'source.png')] + ([('parent', 'parent.png')] if revision else [])
    entries += [(label, label+'.png') for label in labels]
    files, sizes = [], {}
    for name, filename in entries:
        with Image.open(folder / filename) as image:
            sizes[name] = list(image.size)
            for region in regions:
                box = region['box']
                # Same source coordinates for every version; no independent face centering.
                coords = [round(v * image.size[i % 2] / canvas['width' if i % 2 == 0 else 'height']) for i, v in enumerate(box)]
                coords[0] = min(image.width-1, coords[0]); coords[1] = min(image.height-1, coords[1])
                coords[2] = min(image.width, max(coords[0]+1, coords[2]))
                coords[3] = min(image.height, max(coords[1]+1, coords[3]))
                dest = folder / (region['id']+'-'+name+'.png')
                image.convert('RGBA').crop(tuple(coords)).save(dest)
                files.append(dest)
    return {'canvas': {key: canvas[key] for key in ('width', 'height')}, 'regions': regions, 'sizes': sizes}, files


def detail_view_paths(folder, inspection):
    return {r['id']: {name: str((folder/(r['id']+'-'+name+'.png')).resolve())
                     for name in inspection['sizes']} for r in inspection['regions']}


def review_sheet(c, root, ids, purpose="user", language="zh-CN", translations=None, selection_note=None, face_box=None, detail_box=None, inspection=None):
    root = root.resolve()
    try:
        ui = preview_text(language, translations)
    except ValueError as exc:
        raise c.StudioError('INVALID_REVIEW_LANGUAGE', str(exc)) from exc
    state = c.read_state(root)
    require(c, 1 <= len(ids) <= 3 and len(set(ids)) == len(ids), "Review one to three distinct candidates from one request.")
    assets = [c.get_asset(state, i) for i in ids]
    require(c, len({c.asset_slot(a) for a in assets}) == 1, "Compare the same request only.")
    members, pool, omissions = assets, None, []
    if purpose == "user":
        assets, members, pool, omissions = user_review_candidates(c, root, state, assets, selection_note)
    else:
        require(c, selection_note is None, "Assistant inspection packets cannot restrict human presentation.")
    reference_metadata = assets[0].get("edit_references", [])
    require(c, all(a.get("edit_references", []) == reference_metadata for a in assets), "Compare candidates with the same scoped references.")
    require(c, all(c.delivery_validation(c.check_asset(root, state, a))["passed"] for a in assets), "Review requires readable, unchanged images.")
    origin = None
    if assets[0].get("human_revision") and len({a.get("human_revision") for a in assets}) == 1:
        origin = state["human_revisions"][assets[0]["human_revision"]]
        parent = c.get_asset(state, origin["parent_asset"])
        parent_path = c.contained(root, parent["path"])
        require(c, parent_path.is_file() and c.digest(parent_path) == origin["parent_sha256"], "Revision parent changed or is missing.", "STALE_REVIEW_PACKET")
        previous = state['review_packets'][origin['packet']].get('inspection', {}).get('regions', [])
        if origin.get('policy'):
            if inspection is None and face_box is None and detail_box is None:
                inspection = origin['policy']['inspection_regions']
        elif inspection is None:
            if face_box is None:
                face_box = next((r['box'] for r in previous if r['id']=='face'), None)
            if detail_box is None:
                detail_box = next((r['box'] for r in previous if r['id']=='target'), None)
    regions = inspection_regions(c, state, assets, face_box, detail_box, inspection)
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
    summary = user_review_summary(c, root, state, assets, members, pool, items, omissions) if purpose == "user" else None
    if summary is not None:
        packet["presentation"] = {"summary": summary, "omissions": omissions, "pool": assets[0].get("candidate_pool")}
    inspection, detail_files = inspection_images(c, folder, state['canvas'], regions, list(items), revision)
    inspection['comparison_base'] = 'parent' if revision else 'source'
    page = render_sheet(key, list(items), request, contract, purpose, language, ui, revision, edit_references, summary, inspection)
    (folder / "index.html").write_text(page, encoding="utf-8")
    # Assistant packets stay blind; user packets expose checks/recommendation separately.
    public = {"packet": key, "purpose": purpose, "request": request, "contract": contract, "language": language, "ui_labels": ui,
              "source": "source.png", "candidates": {label: f"{label}.png" for label in items}}
    if revision:
        public["revision"] = revision
    if edit_references:
        public["edit_references"] = edit_references
    if summary is not None:
        public["review_summary"] = summary
    public['inspection'] = inspection
    packet['inspection'] = copy.deepcopy(inspection)
    (folder / "packet.json").write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    packet["artifacts"] = [{"path": p.relative_to(root).as_posix(), "sha256": c.digest(p)} for p in (folder / "source.png", folder / "index.html", folder / "packet.json")]
    if revision:
        packet["artifacts"].append({"path": packet["revision_parent"]["copy"], "sha256": origin["parent_sha256"]})
    packet["artifacts"] += [{"path": (folder / ref["path"]).relative_to(root).as_posix(), "sha256": ref["sha256"]} for ref in edit_references]
    packet['artifacts'] += [{'path': p.relative_to(root).as_posix(), 'sha256': c.digest(p)} for p in detail_files]
    c.write_state(root, state)
    return {"packet": key, "page": str((folder / "index.html").resolve()), "public_packet": str((folder / "packet.json").resolve()),
            'inspection': inspection, 'detail_views': detail_view_paths(folder, inspection),
            **({"review_summary": summary} if summary is not None else {}),
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

SUMMARY_LABELS = {
    '推荐与内部检查': 'Recommendation and internal checks',
    '推荐版本': 'Recommended candidate',
    '尚未记录推荐': 'No recommendation recorded',
    '通过全部内部检查': 'Passed all internal checks',
    '内部检查未通过': 'Internal checks failed',
    '已生成候选': 'Generated candidates',
    '已展示候选': 'Displayed candidates',
    '未展示原因': 'Reasons for omitted candidates',
    '根据用户要求仅展示指定版本': 'Only the versions explicitly requested by the user are shown',
    '文件损坏、缺失或变更': 'Image file is invalid, missing or changed',
    '生成调用失败，未产生候选图': 'Image call failed; no candidate was produced',
    'A／B／C 是匿名编号，不代表生成顺序。': 'A/B/C are anonymous labels, not generation order.',
    '你可以评价或要求修订任何展示的候选，包括内部未通过的版本。推荐不代替你的决定；最终交付仍需通过全部门槛。': 'You can evaluate or request changes to any displayed candidate, including failed versions. A recommendation does not replace your decision; delivery still requires every gate to pass.',
}
PREVIEW_EN.update(SUMMARY_LABELS)

INTERACTION_LABELS = {
    '局部对照': 'Detail comparisons', '整脸': 'Whole face', '目标部位': 'Target region',
    '全图': 'Full canvas', '查看范围': 'Inspection area', '与原图同步对照': 'Compare with source',
    '局部使用相同原图坐标；尺寸不同时仅按比例映射，不校正位置或修复画布。': 'Details use the same source coordinates. Different sizes are mapped proportionally; position and canvas differences are not corrected.',
    '采用此版本': 'Use this version', '修改此版本': 'Revise this version',
    '补充评价（可选）': 'Additional ratings (optional)', '复制评审意见': 'Copy review feedback',
    '反馈已复制；粘贴到聊天后才会处理。': 'Feedback copied. Paste it into the chat to have it processed.',
    '无法自动复制，请复制下面的反馈文字。': 'Copy is unavailable. Copy the feedback text below.',
    '待交回的评审意见': 'Review feedback to return',
    '切换图片保留比例和位置；拖动查看细节，方向键切换，Esc 关闭。': 'Switching images retains scale and position. Drag to inspect, use arrow keys to switch, and Esc to close.',
    '原图尺寸': 'Source dimensions', '候选尺寸': 'Candidate dimensions',
}
PREVIEW_EN.update(INTERACTION_LABELS)

BASELINE_LABELS = {'对照基准': 'Comparison baseline', '与修订前同步对照': 'Compare with before revision'}
PREVIEW_EN.update(BASELINE_LABELS)

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
__REVIEW_CONTEXT__
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


LEGACY_REVIEW_SHEET_TEMPLATE = REVIEW_SHEET_TEMPLATE
REVIEW_SHEET_TEMPLATE = r"""<!doctype html>
<html lang="__LANGUAGE__">
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__UI_0__</title><link rel="icon" href="data:,">
<style>
*{box-sizing:border-box}body{font:16px system-ui;max-width:1400px;margin:28px auto;padding:0 20px;background:#f5f4f0;color:#20232a}h1{font-size:28px}h2{font-size:22px}p{line-height:1.55}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}figure{margin:0;min-width:0;background:white;padding:12px;border-radius:12px}figcaption{font-weight:600;margin-bottom:8px}
.image-button{display:block;border:0;margin:0;padding:0;width:100%;background:transparent;cursor:zoom-in}.image-button img{display:block;width:100%;height:360px;object-fit:contain;background:#ddd}.detail-grid .image-button img{height:240px}
button,select,textarea,input{font:inherit}button,select{padding:9px;margin:6px 6px 6px 0}button{cursor:pointer}button:disabled{cursor:default;opacity:.55}.candidate-actions{display:flex;flex-wrap:wrap;margin-top:8px}.candidate-actions button{font-size:14px;flex:1;margin:4px 4px 0 0}
textarea{display:block;width:100%;max-width:100%;min-height:88px;padding:10px;margin:8px 0}section{background:white;padding:20px;margin-top:18px;border-radius:12px}details summary{cursor:pointer}details[open]>summary{margin-bottom:12px}.hint{font-size:14px;color:#535761}
button:focus-visible,select:focus-visible,textarea:focus-visible,input:focus-visible,summary:focus-visible,.viewport:focus-visible{outline:3px solid #3657ae;outline-offset:3px}
dialog{width:min(1400px,96vw);height:94dvh;max-width:none;max-height:94dvh;padding:16px;border:0;border-radius:12px;background:#f5f4f0;color:#20232a}dialog::backdrop{background:#0009}dialog[open]{display:flex;flex-direction:column;gap:8px}body.viewer-open{overflow:hidden}
.viewer-header{display:flex;align-items:center;justify-content:space-between;gap:12px}.viewer-header h2{font-size:20px;margin:0}.viewer-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.viewer-toolbar button,.viewer-header button,.viewer-toolbar select{margin:0}.viewer-toolbar input[type=range]{width:120px;max-width:25vw}.viewer-toolbar output{min-width:50px}
.viewer-panels{display:flex;gap:12px;flex:1;min-height:0;min-width:0}.viewer-pane{display:flex;flex-direction:column;flex:1;min-height:0;min-width:0;gap:6px}.viewer-pane[hidden]{display:none}.pane-label{font-size:14px;margin:0;line-height:1.4}
.viewport{flex:1;min-height:0;min-width:0;overflow:auto;background:#ddd;border-radius:8px;touch-action:pan-x pan-y;cursor:grab}.viewport.dragging{cursor:grabbing;user-select:none}.image-frame{display:flex;align-items:center;justify-content:center}.image-frame img{display:block;flex:none;max-width:none;pointer-events:none;user-select:none}
body.dark .image-button img,body.dark .viewport{background:#25272c}#copy-output[hidden]{display:none}
@media(max-width:600px){body{padding:0 12px;margin:20px auto}.grid{grid-template-columns:1fr}.image-button img{height:360px}dialog{width:100vw;height:100dvh;max-height:100dvh;border-radius:0;padding:12px}.viewer-toolbar{gap:6px}.viewer-toolbar button,.viewer-toolbar select{padding:7px}.viewer-toolbar input[type=range]{width:90px}.viewer-panels.comparing{flex-direction:column}.hint{font-size:12px}.candidate-actions button{font-size:15px}}
</style>
<h1>__UI_1__</h1><p>__REQUEST__</p><p class="hint">__UI_2__</p>
<button id="background" type="button" aria-pressed="false">__UI_3__</button><button id="open-viewer" type="button">__UI_4__</button>
<div class="grid">__CARDS__</div>
__DETAIL_CARDS__
__REVIEW_CONTEXT__
<section id="human-review"><details><summary>__UI_5__</summary><ul>__CHECKS__</ul></details>
<h2>__UI_6__</h2><p>__UI_7__</p>
<label>__UI_8__ <select id="decision"><option value="">__UI_9__</option><option value="accept">__UI_10__</option><option value="revise">__UI_11__</option><option value="reject">__UI_12__</option></select></label>
<label>__UI_13__ <select id="candidate"><option value="">__UI_9__</option>__OPTIONS__</select></label>
<textarea id="note" aria-label="__UI_14__" placeholder="__UI_15__"></textarea>
<details><summary>__EXTRA_RATINGS__</summary>
<label>__UI_16__ <select id="fit"><option value="unspecified">__UI_19__</option><option>__UI_20__</option><option>__UI_21__</option></select></label>
<label>__UI_17__ <select id="preservation"><option value="unspecified">__UI_19__</option><option>__UI_20__</option><option>__UI_21__</option></select></label>
<label>__UI_18__ <select id="usability"><option value="unspecified">__UI_19__</option><option>__UI_22__</option><option>__UI_23__</option></select></label>
</details>
<button id="copy-feedback" type="button">__COPY_FEEDBACK__</button><button id="download" type="button">__UI_24__</button><p id="message" role="status"></p>
<textarea id="copy-output" readonly hidden aria-label="__COPY_OUTPUT__"></textarea><p class="hint">__UI_25__</p></section>
<dialog id="viewer" aria-labelledby="viewer-title">
<div class="viewer-header"><h2 id="viewer-title">__UI_26__</h2><button id="close-viewer" type="button" aria-label="__UI_27__">__UI_28__</button></div>
<div class="viewer-toolbar">
<button id="previous" type="button" aria-label="__UI_29__">←</button><label>__UI_31__ <select id="viewer-candidate"></select></label><button id="next" type="button" aria-label="__UI_30__">→</button>
<label id="inspection-area-label">__INSPECTION_AREA__ <select id="inspection-area"></select></label><label id="comparison-base-label">__BASELINE_LABEL__ <select id="comparison-base"></select></label><label><input id="compare-source" type="checkbox"> <span id="compare-label">__COMPARE_SOURCE__</span></label>
<button id="zoom-out" type="button" aria-label="__UI_32__">−</button><input id="zoom" type="range" min="100" max="500" step="25" value="100" aria-label="__UI_33__"><output id="zoom-label" for="zoom">100%</output><button id="zoom-in" type="button" aria-label="__UI_34__">＋</button>
<button id="fit-window" type="button">__UI_35__</button><button id="viewer-background" type="button" aria-pressed="false">__UI_3__</button>
</div><p class="hint">__VIEWER_HINT__</p>
<div id="viewer-panels" class="viewer-panels">
<div id="source-pane" class="viewer-pane" hidden><p id="source-label" class="pane-label">__SOURCE_LABEL__</p><div id="source-viewport" class="viewport" tabindex="0" aria-label="__SOURCE_VIEWPORT__"><div id="source-frame" class="image-frame"><img id="source-image" alt="__SOURCE_LABEL__" draggable="false"></div></div></div>
<div class="viewer-pane"><p id="candidate-label" class="pane-label"></p><div id="viewport" class="viewport" tabindex="0" aria-label="__UI_37__"><div id="image-frame" class="image-frame"><img id="viewer-image" alt="" draggable="false"></div></div></div>
</div><p id="viewer-status" role="status" class="hint"></p>
<div class="candidate-actions"><button id="viewer-accept" type="button">__ACCEPT_VERSION__</button><button id="viewer-revise" type="button">__REVISE_VERSION__</button></div>
</dialog>
<script>
'use strict';
const packet=__PACKET__,items=__VIEWER_ITEMS__,ui=__UI_STRINGS__,regions=__INSPECTION_REGIONS__,defaultBaseline=__COMPARISON_BASE__;
const byId=id=>document.getElementById(id),viewer=byId('viewer'),choice=byId('viewer-candidate'),area=byId('inspection-area'),compare=byId('compare-source'),baseline=byId('comparison-base');
const panes=[{viewport:byId('viewport'),frame:byId('image-frame'),picture:byId('viewer-image')},{viewport:byId('source-viewport'),frame:byId('source-frame'),picture:byId('source-image')}];
let current=0,zoom=1,position={x:.5,y:.5},drag=null,loadSerial=0;
items.forEach((item,index)=>{const option=document.createElement('option');option.value=index;option.textContent=item.label;choice.append(option);});
items.filter(item=>item.key==='source'||item.key==='parent').forEach(item=>{const option=document.createElement('option');option.value=item.key;option.textContent=item.label;baseline.append(option);});
baseline.value=defaultBaseline;byId('comparison-base-label').hidden=baseline.options.length<2;compare.checked=defaultBaseline==='parent';
[{id:'full',label:ui['全图']},...regions].forEach(region=>{const option=document.createElement('option');option.value=region.id;option.textContent=region.label;area.append(option);});
byId('inspection-area-label').hidden=area.options.length<2;
function remember(pane=panes[0]){const width=pane.frame.clientWidth||1,height=pane.frame.clientHeight||1;return {x:(pane.viewport.scrollLeft+pane.viewport.clientWidth/2)/width,y:(pane.viewport.scrollTop+pane.viewport.clientHeight/2)/height};}
function scrollToPosition(pane){pane.viewport.scrollLeft=position.x*pane.frame.clientWidth-pane.viewport.clientWidth/2;pane.viewport.scrollTop=position.y*pane.frame.clientHeight-pane.viewport.clientHeight/2;pane.expected={left:pane.viewport.scrollLeft,top:pane.viewport.scrollTop};}
function layout(){if(!viewer.open)return;for(const pane of panes){if(!pane.viewport.clientWidth||!pane.picture.naturalWidth||!pane.picture.complete)continue;const fit=Math.min(pane.viewport.clientWidth/pane.picture.naturalWidth,pane.viewport.clientHeight/pane.picture.naturalHeight);const width=pane.picture.naturalWidth*fit*zoom,height=pane.picture.naturalHeight*fit*zoom;pane.picture.style.width=width+'px';pane.picture.style.height=height+'px';pane.frame.style.width=Math.max(pane.viewport.clientWidth,width)+'px';pane.frame.style.height=Math.max(pane.viewport.clientHeight,height)+'px';scrollToPosition(pane);}byId('zoom').value=Math.round(zoom*100);byId('zoom-label').value=Math.round(zoom*100)+'%';}
function imagePath(item){return (item.views||{})[area.value]||item.src;}
function show(index,keepPosition=true){if(keepPosition&&panes[0].picture.complete&&panes[0].picture.naturalWidth)position=remember();current=(index+items.length)%items.length;choice.value=current;const item=items[current],serial=++loadSerial;
for(const option of area.options)option.disabled=option.value!=='full'&&!(item.views||{})[option.value];if(area.selectedOptions[0].disabled)area.value='full';
const base=items.find(entry=>entry.key===baseline.value)||items[0];compare.disabled=!item.key||item.key===base.key;byId('source-pane').hidden=!compare.checked||compare.disabled;byId('viewer-panels').classList.toggle('comparing',!byId('source-pane').hidden);
byId('compare-label').textContent=base.key==='parent'?(ui['与修订前同步对照']||base.label):ui['与原图同步对照'];
byId('viewer-title').textContent=ui['大图预览']+' · '+item.label;byId('viewer-status').textContent=ui['加载中…'];
byId('candidate-label').textContent=item.label+(item.size?' · '+item.size.join(' × '):'');byId('source-label').textContent=base.label+(base.size?' · '+base.size.join(' × '):'');
for(const [i,pane] of panes.entries()){const entry=i===0?item:base;pane.picture.alt=entry.label;pane.picture.onload=()=>{if(serial!==loadSerial)return;layout();byId('viewer-status').textContent=item.label+' · '+area.selectedOptions[0].textContent+(area.value!=='full'?' · '+ui['局部使用相同原图坐标；尺寸不同时仅按比例映射，不校正位置或修复画布。']:'');};pane.picture.onerror=()=>{if(serial===loadSerial)byId('viewer-status').textContent=ui['图片加载失败，请关闭后重试。'];};pane.picture.src=imagePath(entry);}
byId('viewer-accept').disabled=byId('viewer-revise').disabled=!item.candidate;}
function openViewer(index,scope='full'){position={x:.5,y:.5};zoom=1;area.value=scope;viewer.showModal();document.body.classList.add('viewer-open');show(index,false);}
function setZoom(value){position=remember();zoom=Math.min(5,Math.max(1,value));layout();}
function toggleBackground(){const dark=document.body.classList.toggle('dark');for(const id of ['background','viewer-background'])byId(id).setAttribute('aria-pressed',String(dark));}
byId('background').onclick=byId('viewer-background').onclick=toggleBackground;byId('open-viewer').onclick=()=>openViewer(0);
document.querySelectorAll('[data-viewer-index]').forEach(button=>button.onclick=()=>openViewer(Number(button.dataset.viewerIndex),button.dataset.view||'full'));
byId('close-viewer').onclick=()=>viewer.close();viewer.addEventListener('close',()=>{document.body.classList.remove('viewer-open');drag=null;for(const pane of panes)pane.viewport.classList.remove('dragging');});
viewer.addEventListener('click',event=>{if(event.target!==viewer)return;const rect=viewer.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)viewer.close();});
byId('previous').onclick=()=>show(current-1);byId('next').onclick=()=>show(current+1);choice.onchange=()=>show(Number(choice.value));
area.onchange=()=>{position={x:.5,y:.5};zoom=1;show(current,false);};compare.onchange=()=>show(current);baseline.onchange=()=>show(current);
byId('zoom-in').onclick=()=>setZoom(zoom+.25);byId('zoom-out').onclick=()=>setZoom(zoom-.25);byId('zoom').oninput=event=>setZoom(Number(event.target.value)/100);
byId('fit-window').onclick=()=>{zoom=1;position={x:.5,y:.5};layout();};
viewer.addEventListener('keydown',event=>{if(event.target.matches('input,select,textarea'))return;if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();show(current+(event.key==='ArrowLeft'?-1:1));}});
for(const pane of panes){pane.viewport.addEventListener('scroll',()=>{if(!viewer.open)return;const actual={left:pane.viewport.scrollLeft,top:pane.viewport.scrollTop};if(pane.expected&&Math.abs(actual.left-pane.expected.left)<.5&&Math.abs(actual.top-pane.expected.top)<.5)return;position=remember(pane);pane.expected=actual;for(const other of panes)if(other!==pane)scrollToPosition(other);});
pane.viewport.addEventListener('pointerdown',event=>{if(event.pointerType!=='mouse'||event.button!==0)return;event.preventDefault();pane.viewport.focus();drag={pane,id:event.pointerId,x:event.clientX,y:event.clientY,left:pane.viewport.scrollLeft,top:pane.viewport.scrollTop};pane.viewport.setPointerCapture(event.pointerId);pane.viewport.classList.add('dragging');});
pane.viewport.addEventListener('pointermove',event=>{if(!drag||drag.pane!==pane||drag.id!==event.pointerId)return;pane.viewport.scrollLeft=drag.left+drag.x-event.clientX;pane.viewport.scrollTop=drag.top+drag.y-event.clientY;});
for(const name of ['pointerup','pointercancel','lostpointercapture'])pane.viewport.addEventListener(name,()=>{drag=null;pane.viewport.classList.remove('dragging');});}
new ResizeObserver(()=>layout()).observe(byId('viewer-panels'));
function chooseCandidate(label,decision){if(!Array.from(byId('candidate').options).some(option=>option.value===label))return;byId('candidate').value=label;byId('decision').value=decision;byId('copy-output').hidden=true;byId('message').textContent='';if(viewer.open)viewer.close();byId(decision==='revise'?'note':'decision').focus();}
document.querySelectorAll('[data-review-candidate]').forEach(button=>button.onclick=()=>chooseCandidate(button.dataset.reviewCandidate,button.dataset.decision));
byId('viewer-accept').onclick=()=>chooseCandidate(items[current].label,'accept');byId('viewer-revise').onclick=()=>chooseCandidate(items[current].label,'revise');
function feedback(){const value=id=>byId(id).value;const decision=value('decision'),candidate=value('candidate'),note=value('note').trim();if(!decision||(decision!=='reject'&&!candidate)||(decision==='revise'&&!note)){byId('message').textContent=ui['请选择决定和候选；需要修改时请说明问题。'];return null;}return {packet,basis:'user',decision,candidate:decision==='reject'?null:candidate,note,facets:{fit:value('fit'),preservation:value('preservation'),usability:value('usability')}};}
byId('copy-feedback').onclick=async()=>{const data=feedback();if(!data)return;const text=JSON.stringify(data,null,2);try{await navigator.clipboard.writeText(text);byId('copy-output').hidden=true;byId('message').textContent=ui['反馈已复制；粘贴到聊天后才会处理。'];}catch{const output=byId('copy-output');output.hidden=false;output.value=text;output.focus();output.select();byId('message').textContent=ui['无法自动复制，请复制下面的反馈文字。'];}};
byId('download').onclick=()=>{const data=feedback();if(!data)return;const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='charakit-feedback-'+packet+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);byId('message').textContent=ui['反馈已下载。将文件交给 Codex 后才会处理，不会在此页面自动打包。'];};
</script></html>
"""


def preview_text(language="zh-CN", translations=None, allow_legacy=False):
    import re
    if not isinstance(language, str) or not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*', language):
        raise ValueError('Use a language tag such as zh-CN, en or ja.')
    if translations is not None:
        keys = set(PREVIEW_EN)
        reference_keys = {'参考图', '仅参考指定修改内容'}
        revision_keys = {'修订前', '本次修改'}
        accepted = [keys]
        if allow_legacy:
            for feature_keys in (revision_keys, reference_keys, set(SUMMARY_LABELS), set(INTERACTION_LABELS), set(BASELINE_LABELS)):
                accepted += [option - feature_keys for option in list(accepted)]
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


def render_review_summary(summary, ui):
    def escaped(value):
        return html.escape(str(value))
    lines = ['<section id="review-context"><p>'+escaped(ui['A／B／C 是匿名编号，不代表生成顺序。'])+'</p>',
             '<p>'+escaped(ui['已生成候选'])+': '+str(summary['generated'])+' · '+escaped(ui['已展示候选'])+': '+str(summary['displayed'])+'</p>',
             '<p>'+escaped(ui['你可以评价或要求修订任何展示的候选，包括内部未通过的版本。推荐不代替你的决定；最终交付仍需通过全部门槛。'])+'</p>',
             '<details><summary>'+escaped(ui['推荐与内部检查'])+'</summary>']
    recommended = summary.get('recommendation')
    if recommended:
        evidence = recommended['evidence'] if recommended['basis']=='recorded_comparison' else ui['通过全部内部检查']
        lines.append('<p>'+escaped(ui['推荐版本'])+': '+escaped(recommended['candidate'])+' · '+escaped(evidence)+'</p>')
    else:
        lines.append('<p>'+escaped(ui['尚未记录推荐'])+'</p>')
    for label, result in summary['candidates'].items():
        lines.append('<p>'+escaped(label)+' · '+escaped(ui['通过全部内部检查'] if result['status']=='passed' else ui['内部检查未通过'])+'</p><ul>')
        for finding in result['findings']:
            lines.append('<li>'+escaped(finding.get('observed',finding.get('evidence',finding['id'])))+'</li>')
        lines.append('</ul>')
    lines.append('</details>')
    if summary['omissions']:
        lines.append('<p>'+escaped(ui['未展示原因'])+'</p><ul>')
        for omission in summary['omissions']:
            reason = ui['文件损坏、缺失或变更'] if omission['reason']=='unavailable_file' else ui['根据用户要求仅展示指定版本']+' · '+omission['note']
            lines.append('<li>'+escaped(reason)+'</li>')
        lines.append('</ul>')
    for call in summary['failed_calls']:
        lines.append('<p>'+escaped(ui['生成调用失败，未产生候选图'])+' · '+escaped(call['failure'])+'</p>')
    lines.append('</section>')
    return ''.join(lines)


def render_sheet(key, labels, request, contract, purpose, language="zh-CN", translations=None, revision=None, edit_references=None, review_summary=None, inspection=None):
    ui = preview_text(language, translations, allow_legacy=True)
    if revision and not {'修订前', '本次修改'} <= set(ui):
        raise ValueError('Supply revision comparison labels for this page.')
    if edit_references and not {'参考图', '仅参考指定修改内容'} <= set(ui):
        raise ValueError('Supply scoped reference labels for this page.')
    if review_summary is not None and not set(SUMMARY_LABELS) <= set(ui):
        raise ValueError('Supply human review summary labels for this page.')
    modern = set(INTERACTION_LABELS) <= set(ui)
    inspection = inspection or {'regions': [], 'sizes': {}}
    regions = inspection['regions'] if modern else []
    region_label = lambda region: region.get('label') or ui['整脸' if region['id']=='face' else '目标部位']
    items = [{"label": ui['原图'], "src": "source.png", 'key': 'source'}]
    if revision:
        items.append({"label": ui['修订前'], "src": revision['source'], 'key': 'parent'})
        request = f"{request} · {ui['本次修改']}: {revision['note']}"
    items += [{"label": label, "src": f"{label}.png", 'key': label, 'candidate': True} for label in labels]
    items += [{"label": ui['参考图']+' · '+ref['id'], "src": ref['path']} for ref in (edit_references or [])]
    for item in items:
        if item.get('key') in inspection['sizes']:
            item['size'] = inspection['sizes'][item['key']]
            item['views'] = {region['id']: region['id']+'-'+item['key']+'.png' for region in regions}
    def card(index, item, region=None):
        label = html.escape(item['label'])
        view = region['id'] if region else 'full'
        src = html.escape(item['views'][view] if region else item['src'], quote=True)
        actions = ''
        if modern and purpose == 'user' and item.get('candidate'):
            actions = '<div class="candidate-actions">'+''.join(
                f'<button type="button" data-review-candidate="{label}" data-decision="{decision}">{html.escape(ui[text])}</button>'
                for decision, text in (('accept', '采用此版本'), ('revise', '修改此版本')))+'</div>'
        return f'<figure><figcaption>{label}</figcaption><button class="image-button" type="button" data-viewer-index="{index}" data-view="{view}" aria-label="{html.escape(ui["放大查看"])} {label}"><img src="{src}" alt="{label}"></button>{actions}</figure>'
    cards = ''.join(card(index, item) for index, item in enumerate(items))
    detail_cards = ''
    if regions:
        detail_cards = '<section><details id="detail-comparisons"><summary>'+html.escape(ui['局部对照'])+'</summary><p class="hint">'+html.escape(ui['局部使用相同原图坐标；尺寸不同时仅按比例映射，不校正位置或修复画布。'])+'</p>'
        for region in regions:
            detail_cards += '<h3>'+html.escape(region_label(region))+'</h3><div class="grid detail-grid">'+''.join(card(index, item, region) for index, item in enumerate(items) if region['id'] in item.get('views', {}))+'</div>'
        detail_cards += '</details></section>'
    values = {
        '__REQUEST__': html.escape(str(request)), '__CARDS__': cards,
        '__CHECKS__': ''.join(f'<li>{html.escape(x["component"])} · {html.escape(x["property"])}：{html.escape(x["expected"])}</li>' for x in contract),
        '__OPTIONS__': ''.join(f'<option value="{label}">{label}</option>' for label in labels),
        '__PACKET__': script_json(key), '__VIEWER_ITEMS__': script_json(items),
        '__LANGUAGE__': html.escape(language), '__UI_STRINGS__': script_json(ui),
        '__REVIEW_CONTEXT__': render_review_summary(review_summary, ui) if review_summary is not None else '',
    }
    if modern:
        values.update({
            '__DETAIL_CARDS__': detail_cards,
            '__INSPECTION_REGIONS__': script_json([{'id': r['id'], 'label': region_label(r)} for r in regions]),
            '__COMPARISON_BASE__': script_json(inspection.get('comparison_base', 'parent' if revision else 'source')),
            '__BASELINE_LABEL__': html.escape(ui.get('对照基准', ui['查看'])),
            **{token: html.escape(ui[text]) for token, text in {
                '__EXTRA_RATINGS__': '补充评价（可选）', '__COPY_FEEDBACK__': '复制评审意见', '__COPY_OUTPUT__': '待交回的评审意见',
                '__INSPECTION_AREA__': '查看范围', '__COMPARE_SOURCE__': '与原图同步对照', '__SOURCE_LABEL__': '原图', '__SOURCE_VIEWPORT__': '原图',
                '__ACCEPT_VERSION__': '采用此版本', '__REVISE_VERSION__': '修改此版本',
                '__VIEWER_HINT__': '切换图片保留比例和位置；拖动查看细节，方向键切换，Esc 关闭。'}.items()},
        })
    if edit_references:
        values['__CHECKS__'] += ''.join('<li>'+html.escape(ui['仅参考指定修改内容']+' · '+ref['id']+' · '+', '.join(ref['scope'])+'：'+ref['notes'])+'</li>' for ref in edit_references)
    values.update({f'__UI_{index}__': html.escape(ui[label]) for index, label in enumerate(PREVIEW_EN) if label in ui})
    # Substitute once: user prose that resembles a token remains literal text.
    import re
    return re.sub('|'.join(map(re.escape, values)), lambda match: values[match.group()], REVIEW_SHEET_TEMPLATE if modern else LEGACY_REVIEW_SHEET_TEMPLATE)


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
        stream.write(render_sheet(key, list(packet['items']), public['request'], public['contract'], 'user', language, page_ui, public.get('revision'), public.get('edit_references'), public.get('review_summary'), public.get('inspection')))
    packet.setdefault('artifacts', []).append({'path': page.relative_to(root).as_posix(), 'sha256': c.digest(page)})
    packet['latest_page'] = page.relative_to(root).as_posix()
    c.write_state(root, state)
    return {'packet': key, 'page': str(page.resolve()), 'public_packet': str(public_path.resolve()),
            **({'inspection': public['inspection'], 'detail_views': detail_view_paths(folder, public['inspection'])} if public.get('inspection') else {}),
            **({'review_summary': public['review_summary']} if public.get('review_summary') is not None else {}),
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
    if chosen:
        chosen_asset = c.get_asset(state, chosen["asset_id"])
        slot = c.asset_slot(chosen_asset)
        selected = next((a for a in state["assets"] if a["id"] == state["selected"].get(slot)), None)
        if selected and selected.get("candidate_pool") == chosen_asset.get("candidate_pool"):
            del state["selected"][slot]
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
        require(c, asset.get("edit_type") not in ("outfit_replace", "prop_edit", "pose_edit") and "edit_references" not in asset,
                "Full outfits, prop edits and pose edits require a candidate pool and actual user acceptance.", "HUMAN_REVIEW_REQUIRED")
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
            p.add_argument("--selection-note", help="Only for the user's explicit request to show a subset; otherwise show the entire batch.")
            p.add_argument('--face-box', type=int, nargs=4, help='Whole-face inspection in source-canvas coordinates.')
            p.add_argument('--detail-box', type=int, nargs=4, help='Target inspection in source coordinates; defaults to the prepared target box.')
            p.add_argument('--inspection-file', type=Path, help='Task-based localized inspection regions; [] keeps only the full image.')
        if name == "refresh-review-sheet":
            p.add_argument("--packet", required=True)
        if name == "revision-prepare":
            p.add_argument("--packet", required=True)
            p.add_argument("--contract-file", type=Path, required=True)
            p.add_argument("--budget", type=int, choices=(1, 2, 3), default=None)
            p.add_argument('--restore-check', action='append', help='Explicit identity/protection check to restore from the source.')
            p.add_argument('--inspection-file', type=Path, help='Focused regions for this correction; do not inherit every previous region.')
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
        return review_sheet(c, root, args.asset, args.purpose, args.language, read(args.ui_file) if args.ui_file else None, args.selection_note, args.face_box, args.detail_box, read(args.inspection_file) if args.inspection_file else None)
    if args.command == "refresh-review-sheet":
        return refresh_review_sheet(c, root, args.packet)
    if args.command == "revision-prepare":
        return revision_prepare(c, root, args.packet, read(args.contract_file), args.budget, args.restore_check, read(args.inspection_file) if args.inspection_file else None)
    if args.command == "revision-import":
        return revision_import(c, root, args.revision, args.image, args.prompt_file, args.reference)
    if args.command == "revision-fail":
        return revision_import(c, root, args.revision, None, None, None, args.note)
    return human_feedback(c, root, read(args.feedback_file))
