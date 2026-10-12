# CharaKit

**A Codex plugin for editing visual novel character illustrations.** Create expression variants, change clothing, edit accessories or props, and adjust static dialogue poses through a workflow that keeps the source, candidates, review findings, and your chosen version together.

**English** | [简体中文](README.zh-CN.md) · Development version **0.1.30**

Attach an illustration, describe the change, review the results, and choose what to keep. CharaKit uses the image editing tool available in Codex; its local Python helper manages files, comparisons, review records, and exports.

## Features

| Module | Supported edits | Skill |
| --- | --- | --- |
| Expressions | Twelve expression presets and static mouth-open / mouth-closed variants | `$charakit-expressions` |
| Outfits | Garment recoloring, single-garment replacement, full-outfit replacement, and accessory / prop editing | `$charakit-outfits` |
| Poses | Natural standing, one hand on hip, raised-hand greeting, and palm-up explanation | `$charakit-poses` |

Outfits has four edit types:

| Type | Purpose | Example |
| --- | --- | --- |
| `recolor` | Change a garment's color while retaining its design | Make the skirt white |
| `replace` | Replace one garment | Replace a long coat with a short jacket |
| `outfit_replace` | Replace an explicitly defined clothing ensemble | Change into a Japanese school uniform, including socks and shoes |
| `prop_edit` | Add, remove, or replace a scoped accessory or prop | Add glasses or remove a weapon |

All three modules support scoped reference images, bounded redraws, human feedback, and revisions of a chosen candidate. Each uses an independent project; you can manually use an exported PNG as another module's source. Poses supports four static dialogue actions; complex poses and object manipulation remain [planned](plugins/charakit/ROADMAP.md). Real pose generation quality still needs validation.

## Install

Requirements: a Codex host with plugin support and an available image editing tool, plus **Python 3.11+** and **Pillow** for the local helper.

Clone the repository and run:

```shell
git clone https://github.com/SorryM4ker446/CharaKit.git
cd CharaKit
python -m pip install -r plugins/charakit/requirements.txt
codex plugin marketplace add .
codex plugin add charakit@charakit
```

If you already have a local checkout, start from that directory and skip the clone. Make sure Codex uses the Python environment where Pillow is installed, then open a new chat to load the Skills.

You can also register the Git marketplace directly:

```shell
codex plugin marketplace add SorryM4ker446/CharaKit --ref main
codex plugin add charakit@charakit
```

For this route, install the helper dependency from the installed plugin's `requirements.txt`. Keep the complete plugin directory together. The selector `charakit@charakit` means plugin `charakit` from marketplace `charakit`; see the [official plugin packaging guide](https://developers.openai.com/plugins/build/plugins) for marketplace setup.

## Use

Attach the source illustration in a Codex chat, then invoke a Skill with the change you want. You do not need to run the helper commands yourself.

### Expressions

```text
Use $charakit-expressions to create happy and worried versions of this character,
each with mouth closed and naturally open for speaking.
Preserve the character's facial design, hair, clothing, pose, and original style.
```

The twelve presets are neutral, happy, sad, angry, surprised, eyes closed, shy, confused, wry smile, worried, confident, and crying. Mouth states are separate static images; an omitted state is unspecified rather than automatically closed.

### Clothing

```text
Use $charakit-outfits to change this character into a Japanese school uniform:
a navy blazer, white shirt, red bow, pleated skirt, white ankle socks,
and brown loafers. Keep the face, expression, hair, pose, and background.
```

Name every garment you want changed in a full outfit, including shoes and socks. Unlisted clothing and separate equipment remain protected. For a smaller edit, ask for only a recolor or replacement of the named garment.

### Accessories and props

```text
Use $charakit-outfits to add thin-frame glasses.
Keep the expression, facial features, hair, clothing, and pose.
```

To remove or replace an object, name it explicitly. A clothing request alone does not authorize changes to separate accessories or weapons.

### Poses

```text
Use $charakit-poses to raise this character's own right hand near shoulder height,
palm outward, for a greeting. Preserve the left arm, current expression,
mouth state, clothing design, character identity, and original style.
```

Left and right refer to the character's anatomical side. Poses permits necessary limb, joint, fold and overlap changes while preserving protected designs. Pose references guide only the action and structure.

You may attach additional reference images to any module. Describe what each should guide—for example, only the jacket cut, glasses design or palm orientation. References guide those attributes while the source illustration governs the protected character details.

Responses and preview labels follow your language. Outputs default to `art-output/<character-key>/` in your workspace.

## Review and delivery

1. **Define the edit.** Codex inspects the source and records the requested change, allowed boundaries, protected details, and reference roles.
2. **Generate and inspect.** Each requested result has up to three image-tool attempts by default, including the first. Failed checks trigger a targeted redraw within that budget; a full pass stops generation early. Explicit smaller limits are honored.
3. **Review the candidates.** After a full pass or budget exhaustion, the local HTML page shows every readable candidate in that batch alongside the source. Full images remain visible, optional face / target details expand for closer inspection, and the large viewer supports synchronized source comparison. Recommendations remain separate from your choice.
4. **Choose or revise.** Reply in chat with “Use A”, “Revise B: …”, or “Reject all”. You can also copy feedback from the page. A correction edits your chosen version in a new bounded batch, retains successful changes and rechecks still-protected regions against the original. Revision previews compare before/after by default, with task-based detail views and an optional original-source baseline. Failed candidates remain available for comments and revisions.
5. **Receive the result.** Actual human feedback precedes the final review report. Only accepted candidates that pass every delivery check become final full PNGs, with a comparison preview, report, and ZIP when requested. Recorded face / target regions also appear as separate inspection images in the final report.

Internal review uses five dimensions: requested result, character identity, non-target preservation, structure / interfaces, and visual finish. Passage requires **at least 80/100**, **every dimension at least 4/5**, and all applicable domain, fidelity, and file checks. A high total or user preference cannot override a blocking check. If the attempt budget runs out, Codex explains the remaining issues before human review.

Scores are Codex's evidence-based visual judgments; the helper validates records and files rather than independently scoring images. Reports created before human feedback are internal drafts. Details and failed candidates are inspection evidence, not final artwork.

## Documentation

| Topic | Guide |
| --- | --- |
| Expression presets and intensity | [Expression guidelines](plugins/charakit/skills/charakit-expressions/references/expression-guidelines.md) |
| Static dialogue mouth states | [Mouth states](plugins/charakit/skills/charakit-expressions/references/mouth-states.md) |
| Clothing edits | [Recoloring](plugins/charakit/skills/charakit-outfits/references/recolor-guide.md) · [Single replacement](plugins/charakit/skills/charakit-outfits/references/replacement-guide.md) · [Full outfits](plugins/charakit/skills/charakit-outfits/references/full-outfit-guide.md) |
| Accessories and props | [Prop edits](plugins/charakit/skills/charakit-outfits/references/prop-edit-guide.md) |
| Static dialogue poses | [Pose actions, boundaries and checks](plugins/charakit/skills/charakit-poses/references/pose-guide.md) |
| Reference images and protected scope | [Scoped references](plugins/charakit/references/edit-references.md) · [Editing boundaries](plugins/charakit/references/edit-boundaries.md) |
| Review, redraws, and user revisions | [Candidate review](plugins/charakit/references/candidate-review.md) · [Quality policy](plugins/charakit/references/quality-review.md) |
| Reports and exports | [Delivery reports](plugins/charakit/references/delivery-report.md) |
| Helper entrypoints and packaged usage | [Plugin guide](plugins/charakit/README.md) |

Release history is available in [GitHub Releases](https://github.com/SorryM4ker446/CharaKit/releases). Compatibility and legacy workflow details live in the linked guides.

## Development

The repository keeps plugin code under `plugins/charakit/`, synthetic workflow tests under `tests/`, and the ZIP builder under `tools/`. The marketplace entry is `.agents/plugins/marketplace.json`.

Run from the repository root:

```shell
python -m pip install -r plugins/charakit/requirements.txt
python -m unittest discover -s tests -v
python tools/build_plugin.py --output dist/charakit.zip
```

CI checks Linux and Windows. The builder refuses to overwrite an existing ZIP and packages only the plugin files. User artwork, prompts, feedback, and local experiment records stay in ignored output directories.

## Limitations

- Image generation depends on the host's editing tool. CharaKit does not bundle an image model, external image API, or MCP service.
- Edits can drift in identity, pose, framing, or unrelated details. Review helps detect these defects but does not guarantee pixel preservation or fewer revisions.
- Final PNGs must match the source canvas and pass applicable transparency and integrity checks. Canvas mismatch can remain visible in review, but blocks formal acceptance and export; the helper does not resize or repair candidates.
- Outputs are complete static illustrations. Animation, lip synchronization, automatic cross-module generation, larger viewpoint changes, sitting, leaning and object interaction poses are outside the implemented feature set.
