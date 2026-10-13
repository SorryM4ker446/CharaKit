# Task language and presentation

Read this reference before preparing language-dependent prompts, reviews or outputs. The executing assistant identifies the user's language and prepares translations. Python validates and stores those structured decisions, then renders deterministically; it does not guess languages or call a translation service.

## Choose and persist the language

Honor an explicit user language preference first. Otherwise identify the language of the current natural-language request. Short continuations, filenames, code, quoted examples and attached documents do not independently change it; use the existing task language for ambiguous continuations. A new clear natural-language request can change the task language when no explicit preference applies. Prefer context over unnecessary clarification.

After project initialization, use `language-status` to inspect existing settings and `language-set` to record the chosen language, its basis and optionally the actual request file. All modules use the same commands. Settings live in `presentation.json` with immutable snapshots in `presentation-history/`; scores, source artwork and `run.json` are not modified. Report, HTML and PNG commands inherit this language without repeated flags. Explicit `--language` affects that output only. For a combined report with differing project languages, choose one explicitly.

```bash
python <skill>/scripts/studio.py language-status --project <project>
python <skill>/scripts/studio.py language-set --project <project> --language ja --basis user_request --request-file <request.txt> --locale-file <ja.json>
```

Use `--basis explicit` for an actual user preference; it takes precedence over later inferred languages. Use `task_context` for an ambiguous continuation. `--clear-preference` applies only when the user withdraws that preference. Identifiers such as `hand_on_hip`, paths, JSON keys, status/error codes and anonymous aliases stay stable.

## Prepare and reuse a complete language pack

Built-in catalogs cover Simplified Chinese and English. Any valid language tag can use the same external pack schema; there is no two-language allowlist. Traditional Chinese tags require their own pack instead of silently using Simplified Chinese. Regional English tags currently resolve to the English catalog.

```bash
python <skill>/scripts/studio.py language-template --language ja --output <new-template.json>
```

The template supplies `source_catalogs` and empty `catalogs` for report headings, HTML controls, PNG statuses, preset names and revision criteria. Translate every value into the task language, retain keys and format placeholders exactly, choose `ltr` or `rtl`, review meanings, and set `reviewed: true`. Do not mark an untranslated template reviewed. The helper requires all sections/keys and checks the current `catalog_sha256`, nonempty values and placeholder multiplicity. Cached packs remain reusable only while that source-catalog hash matches. Keep generated packs in task output or a workspace cache such as `art-output/.locales/`, outside plugin source. No user download/upload or extra approval is needed to prepare these local files.

Supply the completed pack to `language-set --locale-file`; a validated copy is stored in the project. `preview`, `review-sheet` and `report` also accept `--locale-file`, `--translations-file` and `--font-file` for output-specific overrides. Missing or obsolete translations fail instead of silently displaying a different language.

## Author new content in the task language

Write new prompts, edit targets/boundaries, review criteria, observations, reasons, captions, recommendations and explanations directly in the selected language. Preserve actual user comments and names as supplied. Register the newly authored structured content with:

```bash
python <skill>/scripts/studio.py content-register --project <project> --input-file <new-assessment-or-brief.json>
```

Registration is an assistant declaration that these natural-language fields were authored and checked in the task language. It records identity display entries and source language, without changing the input file or review scores. Never register older foreign-language observations as if they were newly written in the task language. Arbitrary user feedback and existing foreign-language material belong in the translation workflow below.

## Translate historical content only for display

```bash
python <skill>/scripts/studio.py content-plan --project <project> --language ja --output <new-translations.json>
```

The plan extracts natural-language fields and preserves any existing reviewed translations. Complete new entries with `source_language`, `translation` and `reviewed: true`; retain each exact `source` and `source_sha256`. An already Japanese entry can have an identical Japanese display value. Review negation, uncertainty, numbers, units and the actual conclusion; a failed or uncertain assessment must remain failed or uncertain. The helper verifies original-text hashes and numeric observations, but semantic accuracy requires the assistant's review.

Import the completed file with `language-set --translations-file`, preserving the current language pack. Configured tasks require display entries for historical prose; newly encountered untranslated observations trigger a fresh plan. This does not authorize new image generations or regrading.

Reports retain original machine records in `report.json`, keep translated copies under `display_content`, and link `translations.json` with exact originals and translation provenance. HTML packets likewise retain original request/criteria and separate display copies, with an original-text link to `packet.json`. Refresh uses the page's saved language/translation snapshot even when the current task later changes language. Translations never become assessment evidence or alter score/gate fingerprints.

## Names, fonts and layout

Partial `--labels-file` overrides retain exact user names for expressions, mouth slots, outfits, poses and source cards. Omitted names use localized presets or translated edit targets. Legacy PNG status overrides remain compatible. HTML's older complete `--ui-file` remains supported, including older custom-language pages; new tasks should use the shared pack so all output types agree.

PNG captions measure and wrap all text, increasing caption height instead of truncating names or statuses. Font selection checks glyph coverage. Supply `--font-file <font.ttf-or-font.ttc>` when installed fonts cannot cover the task's text. The font is bound to saved presentation snapshots. Arabic and other scripts requiring complex shaping need a Pillow build with libraqm; missing glyphs or shaping support produce explicit errors rather than misleading output. HTML receives the correct `lang` and `dir` attributes. No fonts are downloaded or redistributed automatically.

Legacy projects without task settings retain their prior default `zh-CN` and authored prose. New configured tasks use the complete language and content workflow above. The Japanese fixture in repository tests verifies all fixed text, historical/new prose, preserved numbers, HTML refresh, PNG rendering and raw-image preservation.
