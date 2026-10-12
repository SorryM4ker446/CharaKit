# CharaKit

**Edit visual novel character illustrations in Codex.** This plugin provides expression variants, clothing edits, accessory / prop edits and static dialogue poses with versioned candidates, human review, and selected PNG exports.

Development version **0.1.30** · [Repository](https://github.com/SorryM4ker446/CharaKit) · [中文介绍](https://github.com/SorryM4ker446/CharaKit/blob/main/README.zh-CN.md)

Codex generates artwork through its available image editing tool. The bundled Python helper preserves raw files and manages comparisons, review records, revisions, and packaging.

## Skills

| Skill | Supported edits |
| --- | --- |
| `$charakit-expressions` | Twelve expression presets and static mouth-open / mouth-closed variants |
| `$charakit-outfits` | `recolor`, `replace`, `outfit_replace`, and `prop_edit` with `add`, `remove`, or `replace` actions |
| `$charakit-poses` | `natural_standing`, `hand_on_hip`, `wave`, `palm_up`; explicit anatomical sides, static dialogue poses |

The modules use independent projects. Manually use an exported PNG as another module's source. Four static dialogue poses are available; actual pose generation quality needs validation. Complex poses and object interaction remain [planned](ROADMAP.md). See the [Poses Skill](skills/charakit-poses/SKILL.md) and [pose guide](skills/charakit-poses/references/pose-guide.md).

## Setup

You need Codex plugin support, an available image editing tool, and Python **3.11+**. Install the helper dependency from this plugin directory:

```shell
python -m pip install -r requirements.txt
```

Keep the complete plugin directory, including `lib/`, `references/`, and all three Skills. Use the Python environment with Pillow installed. For marketplace installation, follow the [repository instructions](https://github.com/SorryM4ker446/CharaKit#install) or the [official packaging guide](https://developers.openai.com/plugins/build/plugins).

## Quick start

Attach a source illustration in Codex and ask:

```text
Use $charakit-expressions to create happy and worried expressions,
each with mouth closed and naturally open for speaking.
Keep the character's facial design, hair, clothing, pose, and original style.
```

Or edit clothing or an object:

```text
Use $charakit-outfits to replace the jacket with a short navy blazer.
Keep the shirt, skirt, shoes, accessories, face, hair, expression, and pose.
```

```text
Use $charakit-outfits to add thin-frame glasses.
Keep the facial features, expression, hair, clothing, and pose.
```

For a full outfit, name all included garments, socks, and shoes. Unlisted components remain protected. Optional reference images can guide explicitly named attributes in either module; state what each reference is for.

Responses and preview UI follow your current or preferred language. Machine-readable IDs, filenames, and CLI arguments remain stable English identifiers. Artwork belongs in your workspace, normally `art-output/<character-key>/`, outside the installed plugin.

## Review and delivery

- Each requested result gets up to **three attempts**, including the initial image, unless you set a smaller limit. Internal failures trigger redraws within that allowance; full passage stops generation early.
- Internal passage requires **80/100 or higher**, all five dimensions at least **4/5**, and all applicable domain, fidelity, and file checks. Scores are Codex's visual observations, not automated image measurements.
- After passage or exhaustion, the local HTML review page shows every readable candidate in the batch. Full images, optional face / target comparisons, and synchronized source viewing support inspection. Recommendations do not preselect a candidate.
- Reply “Use A”, “Revise B: …”, or “Reject all” in chat, or copy feedback from the page. Corrections edit the chosen version, preserve successful changes and recheck still-protected regions against the original. Revision previews default to before/after comparison with task-based local views and a switchable source baseline. Failed candidates remain open to feedback and revision.
- Actual human feedback is required for the final review report. Only accepted, eligible candidates become final full PNGs, a comparison preview, and a requested ZIP. Final reports also include recorded face / target inspection images separately from the full artwork. Earlier reports are internal drafts.

Positive feedback cannot bypass failed delivery checks. If every attempt fails, the workflow explains the remaining issues and retains the candidates for human review rather than exporting them as finished art.

## Helper entrypoints

Codex uses the helper during the workflow; users can work through chat. To inspect the available commands, run from this plugin directory:

```shell
python skills/charakit-expressions/scripts/studio.py --help
python skills/charakit-outfits/scripts/studio.py --help
python skills/charakit-poses/scripts/studio.py --help
```

Outside this directory, use the entrypoint's absolute installed path. All modules share `lib/studio_core.py`. Commands manage source snapshots, raw candidates, comparisons, assessment records, actual feedback, revisions, and exports. Poses uses its own schema 3.0 and action/side/anchor brief; its pages default to full images without inheriting a source target crop. Work sequentially within one project.

## Guides

| Topic | Documentation |
| --- | --- |
| Expression workflow | [Expressions Skill](skills/charakit-expressions/SKILL.md) · [Presets](skills/charakit-expressions/references/expression-guidelines.md) · [Mouth states](skills/charakit-expressions/references/mouth-states.md) |
| Clothing and object workflow | [Outfits Skill](skills/charakit-outfits/SKILL.md) |
| Clothing modes | [Recoloring](skills/charakit-outfits/references/recolor-guide.md) · [Single replacement](skills/charakit-outfits/references/replacement-guide.md) · [Full outfits](skills/charakit-outfits/references/full-outfit-guide.md) |
| Accessories and props | [Prop edits](skills/charakit-outfits/references/prop-edit-guide.md) |
| Static dialogue poses | [Poses Skill](skills/charakit-poses/SKILL.md) · [Actions and checks](skills/charakit-poses/references/pose-guide.md) |
| Reference roles and protection | [Scoped references](references/edit-references.md) · [Editing boundaries](references/edit-boundaries.md) |
| Candidate review and revisions | [Human review and redraws](references/candidate-review.md) · [Quality policy](references/quality-review.md) |
| Final reports and exports | [Delivery reports](references/delivery-report.md) |

The guides include command details and legacy compatibility rules. See [GitHub Releases](https://github.com/SorryM4ker446/CharaKit/releases) for release history.

## Limits

Inputs are static PNG/JPEG images up to 50 MiB and 40 million pixels. Final assets must be PNGs matching the source canvas and passing applicable transparency and integrity checks. Canvas mismatch may be shown for review, but blocks formal acceptance and export.

The helper preserves generated image bytes; it does not generate, resize, repaint, composite, or change alpha. Image editing can still alter protected details, so visual inspection remains necessary. CharaKit supplies no image model, external image API, MCP service, animation, or lip synchronization.
