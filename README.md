# CharaKit

**English** | [简体中文](README.zh-CN.md)

**CharaKit** is a modular Codex plugin for visual novel character artwork. **CharaKit Expressions** creates full expression variants; **CharaKit Outfits** recolors a specified existing garment while preserving the character's design.

Each module combines a focused Skill with a shared local Python helper. Codex uses its available OpenAI image editing tool to generate images; the helper preserves versions, checks files, creates full-image and detail comparisons, and exports selected resources.

Development version: **0.1.15**.

Every generation/revision batch ends with [final PNGs, a preview and a saved-review report](plugins/charakit/references/delivery-report.md). The shared `report` command can cover Expressions, mouth states and Outfits together, includes per-round scores and failure findings, and copies only gated final PNGs unchanged. If none pass, it produces only the report. Reporting does not generate, regrade or accept artwork; use helper 0.1.15 or later.

Opt-in [review-driven bounded refinement](plugins/charakit/references/refinement.md) permits three total rounds per expression/mouth-state or garment/color case: the first image plus at most two targeted revisions. Use the previous complete image as the edit target and the immutable original as the design authority. Stop on passage or the limit; deliver only the passed final and retain process images for inspection. Codex still performs host-tool generation and visual review; the helper records budgets and gates. Host-native generation previews may appear automatically.

Fresh assessments use rubric 1.1: at least **80/100**, every dimension at least **4/5**, and unchanged domain, critical-defect, uncertainty, technical and fidelity vetoes. Minor brushwork variation can pass; pixel equality is not required by default. Historical rubric 1.0 reviews retain their 85 threshold and recorded verdicts. Use helper 0.1.14 or later.

New internal reviews require the checklist for the active module/state, not just a global score: expression, explicit mouth state, or garment recolor. Garment checks specialize by the source's actual component and material/interfaces. Any failed/uncertain item vetoes delivery even at 100/100. Use helper 0.1.13 or later; historical reviews remain readable without invented domain findings.

Resolution is temporarily excluded from visual scoring and preview-delivery rejection. Actual canvas mismatch remains recorded and is returned as a delivery warning; other quality/fidelity/technical gates remain. Formal acceptance and ZIP export still require the source canvas. Use helper 0.1.12 or later for this exception.

Quality-first development and delivery follow the shared [internal review policy](plugins/charakit/references/quality-review.md). New candidates need evidence-backed dimension scores, all active domain checks, and applicable technical/fidelity passage. These are assistant visual judgments, not an objective automated similarity model. Internal passage remains separate from user acceptance. Legacy files are preserved; enable quality before new work in old projects.

All available modules use shared [editing boundaries](plugins/charakit/references/edit-boundaries.md): identify the target, allowed property, target invariants, and protected interfaces/remainder. Unrequested components and properties stay protected. Prompts and inspections derive from the request, domain, and actual source; a past test character does not define the template. Outfits provides [garment-specific rules](plugins/charakit/skills/charakit-outfits/references/garment-domains.md); Expressions specializes allowed facial movement and mouth state without authorizing other edits.

Artwork quality takes priority over prompt length. Retain the source's actual appearance, including each eye's original color distribution and design, without assigning guessed colors. Expression prompts include the coordinated movements and visible effects needed to distinguish emotions; generation and inspection check these separately from file validity.

Release notes are published with GitHub Releases.

## Modules

| Module | Skill ID | Status |
| --- | --- | --- |
| CharaKit Expressions | `charakit-expressions` | Available: full expression variants |
| CharaKit Outfits | `charakit-outfits` | Available: one-garment recoloring; full replacement planned |
| CharaKit Poses | `charakit-poses` | Planned: static pose and action edits |

Install the plugin as `charakit`; use `$charakit-expressions` for expressions and static mouth states, or `$charakit-outfits` for garment recoloring. Pose editing remains planned. See the [module definitions](plugins/charakit/modules.json) and [roadmap](plugins/charakit/ROADMAP.md).

## Current expression features

- Support twelve fixed presets: neutral, happy, sad, angry, surprised, eyes closed, shy, confused, wry smile, worried, confident, and crying.
- Preserve the entire face, original art style, character design, pose, and visual harmony.
- Revise a single expression while keeping other candidates and history.
- Keep static mouth-open and mouth-closed versions independently versioned, selected, and exported.
- Compare full illustrations and enlarged face regions on light, dark, or checker backgrounds.
- Check exact canvas dimensions, actual PNG content, transparency, and file fingerprints.
- Export accepted, technically valid PNGs with a manifest and ZIP.

List expression IDs, mouth states, and starting directions with the helper's `presets` command. Generated results still require visual review. See the [expression guide](plugins/charakit/skills/charakit-expressions/references/expression-guidelines.md) for emotion directions and the [mouth-state guide](plugins/charakit/skills/charakit-expressions/references/mouth-states.md) for static dialogue states. Each expression/state pair keeps its own versions and selection. Gaze states remain planned.

Every variant is a complete image. There is no facial-part extraction, face compositing, database, external image API, ComfyUI integration, MCP service, or dedicated application.

## Garment recoloring

```text
Use $charakit-outfits to make only this character's jacket fabric navy blue.
Preserve the trim, buttons, fabric texture, folds, lighting, tie, skirt,
face, expression, mouth state, hair, and pose. Generate two candidates
and compare them, including enlarged face and jacket regions.
```

The current mode changes the color of one existing garment. Full outfit replacement, accessory additions/removals, clothing on/off states, and automated outfit/expression combinations remain planned. Actual recolor quality needs review of generated images; workflow tests do not prove visual preservation.

Use a separate outfit project, for example `art-output/my-character/outfits/`, with its own immutable source. The helper records an outfit option ID, target garment, and requested color. Each target/color option has independent versions and selection. Revisions retain the same target/color definition; changing it requires a new ID.

Outfit projects and manifests use schema 1.2. Existing expression projects remain schema 1.0/1.1 and keep their original helper path, IDs, and export filenames. The complete plugin now includes a shared `lib/studio_core.py`; keep it with both Skills. See the [Outfits Skill](plugins/charakit/skills/charakit-outfits/SKILL.md) for details.

Before generation, `prepare` saves an edit boundary, protected-region descriptions, and a source-only detail reference. The default uses one complete source and a complete domain-specific prompt stating the allowed recolor, invariants, exclusions, preservation, and output. Quality takes priority over prompt length; necessary detail is retained in the submission as well as the inspection brief. The crop is submitted only for an ambiguous target or a requested reference comparison when supported. All final artwork changes remain in the host image tool; the crop is not a mask, pixel lock, or final asset.

Compare the full image, face, garment, and relevant non-target details such as weapons, hair outlines, hands, and neighboring equipment. Additional `preview --detail-box` calls with distinct output paths can enlarge these regions. Non-target repainting remains a known limitation; simplifying the prompt/reference workflow has not been shown to resolve it.

After inspecting the result, `fidelity` records target recoloring and protected-region preservation separately as passed, failed, or uncertain, with the observation source and a factual note. It does not grant user acceptance. Brief-linked candidates require both checks passed as well as technical validity and user acceptance before selection/export. Old records remain unchanged and do not acquire inferred checks; use helper 0.1.7 or later for the new gates, which older helpers do not enforce.

```shell
python plugins/charakit/skills/charakit-outfits/scripts/studio.py init --project art-output/my-character/outfits --source character.png --character my-character
python plugins/charakit/skills/charakit-outfits/scripts/studio.py prepare --project art-output/my-character/outfits --outfit coat_navy --target "jacket fabric" --color "navy blue" --boundary "Main fabric only; exclude lining, trim and buttons" --protect "Entire face, expression, hair and pose" --protect "Other clothing and accessories" --target-box 80 250 280 500
python plugins/charakit/skills/charakit-outfits/scripts/studio.py add --project art-output/my-character/outfits --outfit coat_navy --target "jacket fabric" --color "navy blue" --image generated-coat-navy.png --prompt-file prompt.txt --brief-file art-output/my-character/outfits/briefs/coat_navy_v001.json
python plugins/charakit/skills/charakit-outfits/scripts/studio.py preview --project art-output/my-character/outfits --outfit coat_navy --output art-output/my-character/outfits/preview/coat-navy-v001.png --face-box 100 100 200 200 --detail-box 80 250 280 500
python plugins/charakit/skills/charakit-outfits/scripts/studio.py fidelity --project art-output/my-character/outfits --asset coat_navy_v001 --target-check passed --protection-check uncertain --note "Target color is visible; inspect face and neighboring trim before passing protection"
```

Replace paths and preview coordinates with those of the actual artwork. Review, selection, and export use the same command names as Expressions. Outfit PNGs export to `sprites/<character>/outfits/<outfit-id>.png` and retain the candidate's original bytes. Technical failures remain excluded from formal exports.

The fidelity command above illustrates an uncertain observation, not an automatically passed result. Record only findings visible in the actual comparisons. Revisions inherit an existing edit brief but start without fidelity observations; prepare a new brief if its boundaries need clarification.

## Requirements

- A Codex host with plugin/Skill support and an available image editing tool.
- Python 3.11+ and Pillow for the local helper.

Installing the plugin does not supply a missing image tool or select a model. Use the current host-provided tool; record the model as unknown when the tool does not report one.

## Install

For a local clone, run from the repository root:

```shell
codex plugin marketplace add .
codex plugin add charakit@charakit
```

After publishing to GitHub, users can install from the repository. Replace `YOUR_GITHUB_OWNER/CharaKit` with the actual repository:

```shell
codex plugin marketplace add YOUR_GITHUB_OWNER/CharaKit --ref main
codex plugin add charakit@charakit
```

The marketplace and plugin both use the identifier `charakit`. The install selector `charakit@charakit` means plugin `charakit` from marketplace `charakit`, for both local and Git sources. Refresh or restart Codex and open a new chat after installation.

Install the helper dependency in the desired Python environment:

```shell
python -m pip install -r plugins/charakit/requirements.txt
```

## Use

Attach a source illustration in Codex, then ask:

```text
Use $charakit-expressions to generate happy, sad, angry,
surprised, and eyes-closed versions of this character.
Preserve the entire face, original style, design, and visual harmony.
```

Ask for a specific intensity, revise one version, or select images for export.

For example, request only shy, confused, and crying versions, then revise the crying version to use fewer tears. The other expression versions and selections are retained.

Use the same Skill for static dialogue states:

```text
Use $charakit-expressions to create happy and worried versions,
each with mouth closed and naturally open for speaking.
Generate two candidates per state and compare each pair in preview.
```

Omitting a mouth state keeps it unspecified (`default`); it does not label the image as closed-mouth. Both explicit states can be selected and exported together. These are static images, without lip synchronization or animation frames. Old projects remain readable; the first explicit-state import backs up metadata and upgrades the project to schema 1.1. Use version 0.1.5 or later for upgraded projects.

**The plugin responds in your language.** Progress updates, visible expression names, generation prompts, quality explanations, limitations, and delivery notes follow your current request or explicitly preferred language. CLI arguments, JSON keys, filenames, and status/error codes remain stable English identifiers. Preview labels can be localized through `--labels-file`.

Outputs default to `art-output/<character-key>/`. User artwork and experiment records are ignored by Git and excluded from distribution packages.

## Local helper example

Run from the repository root. Replace image paths and the face coordinates for your artwork:

```shell
python plugins/charakit/skills/charakit-expressions/scripts/studio.py presets
python plugins/charakit/skills/charakit-expressions/scripts/studio.py init --project art-output/my-character --source character.png --character my-character
python plugins/charakit/skills/charakit-expressions/scripts/studio.py add --project art-output/my-character --expression angry --image generated-angry.png --prompt-file prompt.txt
python plugins/charakit/skills/charakit-expressions/scripts/studio.py add --project art-output/my-character --expression happy --mouth-state closed --image happy-closed.png
python plugins/charakit/skills/charakit-expressions/scripts/studio.py add --project art-output/my-character --expression happy --mouth-state open --image happy-open.png
python plugins/charakit/skills/charakit-expressions/scripts/studio.py preview --project art-output/my-character --output art-output/my-character/preview/comparison-v001.png --face-box 100 100 200 200 --background light
python plugins/charakit/skills/charakit-expressions/scripts/studio.py preview --project art-output/my-character --output art-output/my-character/preview/comparison-dark-v001.png --face-box 100 100 200 200 --background dark
python plugins/charakit/skills/charakit-expressions/scripts/studio.py quality --project art-output/my-character --asset angry_v001 --assessment-file assessment.json --comparison art-output/my-character/preview/comparison-v001.png --comparison art-output/my-character/preview/comparison-dark-v001.png
python plugins/charakit/skills/charakit-expressions/scripts/studio.py deliver --project art-output/my-character --asset angry_v001
python plugins/charakit/skills/charakit-expressions/scripts/studio.py review --project art-output/my-character --asset angry_v001 --status accepted --note "User selected this version."
python plugins/charakit/skills/charakit-expressions/scripts/studio.py export --project art-output/my-character
```

A failing `add` returns exit code 2 with a structured report and retains the candidate. Prepare `assessment.json` from actual inspected findings using the [quality rubric](plugins/charakit/references/quality-review.md); it is not a default passing template. A technical pass does not imply art approval. Formal export requires technical validity, applicable quality/fidelity gates and actual user acceptance.

If a user likes an image that fails technical checks, preserve their feedback separately. The helper does not set the `accepted` status until those checks pass.

## Repository layout

```text
README.md                           English overview and instructions
README.zh-CN.md                     Simplified Chinese overview and instructions
.agents/plugins/marketplace.json     Local/Git marketplace entry
.github/workflows/ci.yml             Tests and plugin package verification
plugins/charakit/
  plugin.json                       Plugin manifest
  README.md                         Standalone plugin instructions
  modules.json                      Available and planned module definitions
  ROADMAP.md                        Module scope and development sequence
  requirements.txt                  Helper dependency
  lib/studio_core.py                Shared file workflow for both modules
  skills/charakit-expressions/
    SKILL.md                        Workflow and language behavior
    references/                     Expression and review guidelines
    scripts/studio.py               Local file helper
  skills/charakit-outfits/
    SKILL.md                        Garment recoloring workflow
    references/recolor-guide.md     Editing and review directions
    references/garment-domains.md    Component, material, and interface rules
    scripts/studio.py               Outfit helper entrypoint
  references/edit-boundaries.md     Shared editing scope across modules
  references/quality-review.md      Development baseline and internal delivery rubric
tests/test_studio.py                 Synthetic-fixture workflow tests
tests/test_outfits.py                Recolor and packaging workflow tests
tests/test_outfit_fidelity.py        Source-reference and manual-fidelity workflow tests
tests/test_quality.py                Internal review, delivery and compatibility gates
tools/build_plugin.py               Plugin ZIP builder
```

## Development

```shell
python -m pip install -r plugins/charakit/requirements.txt
python -m unittest discover -s tests -v
python tools/build_plugin.py --output dist/charakit-0.1.15.zip
```

Tests use synthetic images; no third-party character art is required. CI runs on Linux and Windows. The build refuses to overwrite an existing ZIP.

The plugin ZIP contains only the plugin's files. Keep user images, prompts, local feedback, caches, credentials, and personal machine paths out of commits.

## Current limitations

Expression and garment edits may alter unrelated details or produce a different canvas size. Preserving character identity, facial detail, original style, and alignment requires visual review; prompt instructions alone cannot guarantee consistency.

Automatic checks cover file format, canvas dimensions, transparency, and file integrity. They do not assess artistic quality or how expression changes look in a game. Export requires passing technical checks and approval after visual review.

See the [plugin guide](plugins/charakit/README.md) for details.
