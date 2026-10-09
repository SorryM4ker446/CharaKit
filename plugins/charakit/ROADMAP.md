# CharaKit module roadmap

CharaKit is the project and plugin name; its plugin ID is `charakit`. Modules have their own Skill IDs. The available and reserved module definitions are maintained in [modules.json](modules.json).

| Module | Skill ID | Status | Scope |
| --- | --- | --- | --- |
| CharaKit Expressions | `charakit-expressions` | Available | Complete expression variants, individual revisions, previews, and selected PNG exports |
| CharaKit Outfits | `charakit-outfits` | Planned | Local clothing edits followed by full outfit replacement |
| CharaKit Poses | `charakit-poses` | Planned | Static character pose and action edits |

Only the expression Skill is packaged. Reserved module IDs are planning placeholders, not invocable Skills. No release dates or version targets are assigned to the planned modules.

## Development order

1. Strengthen expression delivery: source-canvas consistency, transparent edges, and switching stability in a game.
2. Validate clothing recoloring and a small, explicitly requested accessory edit while preserving the face, pose, and unrelated details.
3. Validate a complete outfit replacement in the original pose, using a clothing reference or a clear design description.
4. Validate modest static pose changes before larger perspective changes or complex action poses.
5. Organize requested combinations of outfit, pose, and expression, with individual revisions and traceable base artwork.

Each stage needs actual image and game-use validation before it is advertised as available. All deliverables remain complete character PNGs.

## Editing boundaries

- **Expressions:** allow the requested facial expression changes; preserve outfit, pose, facial design, and original style.
- **Outfits:** allow the requested clothing changes; preserve face, expression, hair, body proportions, pose, and original style. Evaluate garment structure, material, folds, and occlusions.
- **Poses:** allow the requested body movement and necessary changes in folds and occlusions; preserve identity, outfit design, prop design, proportions, and original style. Evaluate anatomy, hands, perspective, balance, and prop interaction.

Preserve whole-face detail and overall visual harmony in every mode. Quality rules must follow the selected mode; an intended pose change is not an expression-alignment error.

## References and variant organization

Keep the original artwork as the identity and style reference. Assign clothing and pose references explicit roles. Select a suitable outfit/pose base before generating its expression group; each expression should independently use that same base.

Future records may add `outfit_id`, `pose_id`, and `base_asset_id` alongside expression, version, source references, fingerprints, checks, and user feedback. Select versions per outfit/pose/expression combination. Preserve compatibility or provide an explicit migration for existing expression projects.

A possible future export path is `sprites/<character>/<outfit>/<pose>/<expression>.png`. This is a proposal; the current helper's record schema and export paths stay in use until combination support is implemented.

Generate only requested combinations. Positive art feedback and deterministic technical checks remain distinct; formal export requires both. Pose previews will need candidate-specific face regions and checks suited to the intended movement.

## Architecture

Keep the plugin lightweight: focused Skills, local Python/Pillow helpers, and the host-provided image tool. Shared versioning, file checks, previews, and packaging can support later modules. The plan does not add a database, external image API, ComfyUI workflow, MCP service, model selector, facial-part compositing, or a dedicated application.

Static pose editing does not include animation frames, Live2D parts, or rigging. Image-tool capabilities and art fidelity must be verified in the actual host.
