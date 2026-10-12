# Presentation language

Reports, HTML review pages and PNG comparison previews use `--language` and the shared fixed-text catalogs in `lib/localization.py`. All three default to `zh-CN`. Pass the user's current or preferred language explicitly to each command in the task; a previous preview or review page does not change another command's default.

Built-in languages are Simplified Chinese (`zh-CN`) and English (`en`). Regional tags such as `zh-Hans`, `zh-TW` and `en-US` select the corresponding built-in catalog; Chinese tags currently all use Simplified Chinese. PNG and report results record the canonical built-in language. HTML preserves the supplied valid language tag, including custom-language pages.

```bash
python <skill>/scripts/studio.py preview --project <project> --output <preview.png> --language en --labels-file <names.json>
python <skill>/scripts/studio.py review-sheet --project <project> --asset <candidate-id> --language en
python <skill>/scripts/studio.py report --project <project> --output <new-report-dir> --language en --labels-file <names.json>
```

`--labels-file` remains a partial, flat UTF-8 JSON name mapping for PNG previews and reports. Keys include `source`, expression IDs, `mouth_open`, `mouth_closed`, complete expression/mouth slots, outfit IDs and pose IDs. Example:

```json
{"source": "Original artwork", "happy": "Gentle smile", "hand_on_hip": "Confident stance"}
```

Omitted names use localized expression/mouth presets or existing edit targets and IDs. PNG titles retain version numbers. Fixed status labels, file-check findings, report headings and HTML controls come from the selected catalog without requiring label overrides. Existing PNG status/error overrides remain supported for compatibility, but normal localization should use `--language`. Report name overrides do not override fixed status text.

HTML additionally retains `--ui-file` for complete custom UI mappings, including languages without built-in catalogs. It is separate from name overrides. Existing pages and their stored UI mappings remain refreshable; a complete new mapping must cover all current controls. Custom HTML UI files do not translate PNGs, reports or recorded review criteria into additional languages.

Saved requests, observations, feedback, custom names and user-supplied titles keep their authored language. IDs, CLI flags, JSON keys and status/error codes in machine records stay stable. No automatic translation or language detection is performed. Preview glyph coverage depends on installed fonts.

Catalog tests require matching Chinese/English sections and keys, nonempty values and matching format placeholders. Fixed PNG statuses and known file-check error codes also have explicit coverage checks.
