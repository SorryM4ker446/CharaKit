# Scoped edit references

This shared contract applies to every implemented editing mode and every future module. References are optional; modules remain independent and never invoke one another automatically. The helper records inputs and enforces workflow gates; visual interpretation and image edits belong to the host image tool.

## Define the reference's purpose

Inspect the immutable source and each proposed reference. Record only the cues the user wants transferred. The source controls identity, original rendering style and all unrequested properties. A reference person's face, hair, pose, framing or background must not replace protected source content. Resolve material ambiguity before generation; explicit user requirements take precedence over reference cues.

Scopes for current modules:

| Mode | Allowed scope IDs | Intended cues |
| --- | --- | --- |
| Expressions, default mouth | `expression` | Requested emotion and facial movement; preserve face design |
| Expressions, explicit mouth state | `expression`, `mouth` | Authorized expression/mouth movement only; a mouth-only request protects established emotion |
| Outfits recolor, replace, prop_edit | `target` | Only the named garment color/design or object; removal references describe the intended clean result |
| Outfits outfit_replace | Exact editable inventory component IDs | The relevant design, material, color and construction for each listed component |
| Poses | `pose` | Requested static action and structural relationships only; preserve source identity, expression, designs and style |

Scopes describe the maximum possible use, not permission to change everything they name. Stay inside the user's actual request. Future modules must define their editable attributes and reference scopes before release. Poses explicitly permits the requested movement while protecting identity; Outfits does not authorize pose edits. See the [pose guide](../skills/charakit-poses/references/pose-guide.md).

## Snapshot and use actual inputs

Create a UTF-8 input JSON in the user's output directory, with one to three distinct, focused PNG/JPEG/WebP images. Paths relative to this JSON are supported. Each entry needs a stable ID, editable scope and a concrete note in the user's language:

```json
[{"id":"design_ref","path":"reference.png","scope":["target"],"notes":"Use only the requested garment design and color; preserve the source character."}]
```

Run the active module's helper:

```text
python <skill>/scripts/studio.py reference-prepare --project <project> --references-file <input.json>
```

The helper preserves original image bytes inside the project, records hashes/roles/scopes/notes and returns `reference_file`, `references` and absolute `reference_paths`. Preparation does not change project metadata, consume a generation attempt or alter old history. A source-detail crop is inspection evidence, not a mask or a substitute for complete reference images.

For Outfits, pass `--reference-file <returned manifest>` to `prepare` alongside the ordinary mode-specific parameters, then use its returned `generation_references`/`reference_paths`. For Expressions, pass the returned manifest to `add --reference-file`. In both modules, generation uses **immutable source followed by every prepared edit reference**. Record each actual submitted input with repeated `add --reference <path>` in that exact order, along with the actual saved prompt. The helper rejects omitted, reordered or additional claimed inputs. Do not claim reference use based on prompt text alone; records must describe the actual host call.

If the host cannot accept all required inputs, explain the limitation and resolve scope with the user before generating; never silently truncate references. Do not add MCP, masks, regional editing or local artwork reconstruction as a fallback.

## Review, redraw and human revision

Define the normal five-dimension contract plus a **target criterion whose `component` equals each reference ID**, describing its permitted cues and appropriate inspection view. Also retain all required component, domain and protection checks. Start the candidate pool before scoring. Anonymous assistant/user review packets include copied reference images and their scopes/notes; references are context, never selectable candidates.

Inspect source, candidate and every applicable reference. Record actual visible adherence and deviation for each reference criterion. Reference adherence belongs to target completion and applicable domain checks; source preservation remains independent. A reference image is not evidence that the generated result passed. Any failed/uncertain required reference criterion, dimension, domain, fidelity or critical-defect check blocks passage, even above 80. Apply the shared [candidate review](candidate-review.md) budget: normally three total attempts including the first; honor a smaller explicit cap, stop as soon as all gates pass, otherwise redraw within the remaining budget and reassess every required check.

Use every `pool-reserve` or `revision-prepare` returned `reference_paths` **without changing order**. New human revisions and their internal redraws use the recorded edit target first, immutable source second, then all scoped references. Initial-request `source_restart` plans use only the source followed by all already-bound scoped references: the failed parent is review evidence, never submitted to the image tool. Other redraws and saved legacy plans retain their recorded strategy. Follow the shared [revision baseline and inspection rules](candidate-review.md#revision-baselines-and-task-based-inspection): preserve successful edits relative to the chosen baseline and separately recheck protected regions against the source. Restore only explicitly named protected properties; do not reintroduce superseded source features. Imports bind actual inputs and parent lineage; new images never inherit scores or acceptance. Tool failures consume their reserved attempt. At exhaustion explain unresolved findings and request actual human feedback; no fourth attempt.

Human corrections preserve the chosen parent, the user's original comment and the same reference records through their new bounded review/redraw batch. A new reference or changed scope/design is a new explicitly requested edit, not a way to reset an old budget or reuse a passed assessment. Unreferenced old projects retain their original strategy and history without automatic migration.

## Integrity and delivery

Saved reference bytes are immutable. Missing/changed snapshots block generation continuation, review reuse, formal acceptance and packaging. Restore the original snapshot to continue; never rewrite hashes or past assessments to bless changed inputs. External source/reference originals may subsequently move because the project uses its own snapshots.

Review pages, notes and reports follow the user's language. Generate the final review report after actual human feedback; pending work produces only an internal draft. Reports record reference scopes and generation lineage, and ZIP manifests include reference metadata and unchanged snapshots separately from final sprites. References do not increase output counts. Human acceptance cannot override failed internal/technical gates. Keep all generated HTML and user artwork outside plugin source files.

Future-module acceptance must cover scope isolation, actual input binding, reference retention in every round, failure-driven redraw, fixed budgets, human revision lineage, localized previews and delivery gates. Synthetic tests verify these mechanics; real art quality and return rates require actual image generation and human evaluation.
