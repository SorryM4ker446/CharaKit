"""Task presentation settings and immutable, reviewed display translations.

Language identification and translation belong to the invoking assistant. These
helpers validate its structured decisions; they never translate or regrade art.
"""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
from string import Formatter
import tempfile


class PresentationError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise PresentationError('INVALID_LANGUAGE_FILE', f'Cannot read presentation JSON: {path}') from exc


def fields(text):
    try:
        return Counter((name, spec, conversion) for _, name, spec, conversion in Formatter().parse(text) if name is not None)
    except ValueError as exc:
        raise PresentationError('INVALID_LOCALE_FILE', 'Invalid format placeholders.') from exc


def template(locale, language):
    language = locale.normalize_language(language)
    baseline = locale.CATALOGS['en']
    return {'schema_version': '1.0', 'catalog_sha256': fingerprint(baseline), 'language': language,
            'direction': direction(language), 'reviewed': False,
            'catalogs': {section: {key: '' for key in values} for section, values in baseline.items()},
            'source_catalogs': copy.deepcopy(baseline)}


def direction(language):
    return 'rtl' if language.split('-')[0] in ('ar', 'fa', 'he', 'ur', 'ps', 'dv', 'yi') else 'ltr'


def validate_pack(locale, data, language):
    baseline = locale.CATALOGS['en']
    if (not isinstance(data, dict) or data.get('schema_version') != '1.0'
            or locale.normalize_language(data.get('language')) != language
            or data.get('catalog_sha256') != fingerprint(baseline)
            or data.get('reviewed') is not True or data.get('direction') not in ('ltr', 'rtl')):
        raise PresentationError('INVALID_LOCALE_FILE', 'Use a reviewed, current language template for this language.')
    catalogs = data.get('catalogs')
    if not isinstance(catalogs, dict) or set(catalogs) != set(baseline):
        raise PresentationError('INVALID_LOCALE_FILE', 'All presentation sections are required.')
    for section, original in baseline.items():
        translated = catalogs[section]
        if not isinstance(translated, dict) or set(translated) != set(original):
            raise PresentationError('INVALID_LOCALE_FILE', f'Incomplete section: {section}')
        for key, source in original.items():
            value = translated[key]
            if not isinstance(value, str) or not value.strip() or len(value) > 8000 or fields(value) != fields(source):
                raise PresentationError('INVALID_LOCALE_FILE', f'Invalid translation or placeholders: {section}.{key}')
    return copy.deepcopy(data)


def validate_translations(locale, data, language):
    if (not isinstance(data, dict) or data.get('schema_version') != '1.0'
            or locale.normalize_language(data.get('language')) != language or not isinstance(data.get('entries'), list)):
        raise PresentationError('INVALID_DISPLAY_TRANSLATIONS', 'Use a display translation file for the selected language.')
    entries = {}
    for entry in data['entries']:
        if not isinstance(entry, dict):
            raise PresentationError('INVALID_DISPLAY_TRANSLATIONS', 'Translation entries must be objects.')
        source, translated = entry.get('source'), entry.get('translation')
        if (not isinstance(source, str) or not source.strip() or not isinstance(translated, str) or not translated.strip()
                or len(source) > 20000 or len(translated) > 20000 or entry.get('source_sha256') != text_hash(source)
                or entry.get('reviewed') is not True or not isinstance(entry.get('source_language'), str)):
            raise PresentationError('INVALID_DISPLAY_TRANSLATIONS', 'Each reviewed translation must bind its exact original text.')
        locale.validate_language(entry['source_language'])
        # Scores, dimensions and other numeric observations must survive translation.
        numbers = lambda value: Counter(re.findall(r'[+-]?\d+(?:\.\d+)?', value))
        if numbers(source) != numbers(translated):
            raise PresentationError('TRANSLATION_FACTS_CHANGED', 'Translation changed numeric observations.')
        key = entry['source_sha256']
        if key in entries:
            raise PresentationError('INVALID_DISPLAY_TRANSLATIONS', 'Duplicate source translation.')
        entries[key] = copy.deepcopy(entry)
    return entries


# Only natural-language presentation fields; filenames, hashes, enums, IDs,
# references and scores are deliberately outside this allowlist.
TEXT_FIELDS = {'request', 'evidence', 'observed', 'note', 'notes', 'expected', 'component', 'property',
               'target', 'replacement', 'color', 'boundary', 'label', 'reason', 'failure',
               'left_arm', 'right_arm', 'contacts', 'occlusion', 'repair_plan'}
TEXT_LISTS = {'critical_defects', 'uncertainties', 'protected_regions', 'anchors'}
REASON_CODES = {'unavailable_file', 'user_requested_subset'}


def human_strings(value, field=None):
    if isinstance(value, dict):
        for key, item in value.items():
            # Source garment descriptions are prose, whereas other source fields are paths.
            if key == 'outfit_components' and isinstance(item, list):
                for component in item:
                    if isinstance(component, dict) and isinstance(component.get('source'), str):
                        yield component['source']
            yield from human_strings(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from human_strings(item, field)
    elif (isinstance(value, str) and value.strip() and field in TEXT_FIELDS | TEXT_LISTS
          and not (field == 'reason' and value in REASON_CODES)):
        yield value


class Presentation:
    def __init__(self, locale, language, pack=None, entries=None, strict=False, font_file=None, source='default'):
        self.locale = locale
        self.language = language
        self.pack = pack
        self.entries = entries or {}
        self.strict = strict
        self.font_file = font_file
        self.source = source
        self.preference_language = None
        self.direction = pack['direction'] if pack else direction(language)
        self.used = {}

    def texts(self, section):
        return dict((self.pack['catalogs'] if self.pack else self.locale.CATALOGS[self.language])[section])

    def display(self, source, required=True):
        if not isinstance(source, str) or not source.strip() or source == '—':
            return source
        entry = self.entries.get(text_hash(source))
        if entry:
            self.used[entry['source_sha256']] = entry
            return entry['translation']
        if any(source in values.values() for values in self.texts_catalog().values()):
            return source
        if self.strict and required:
            raise PresentationError('MISSING_DISPLAY_TRANSLATION', 'Prepare a reviewed display translation for: ' + source[:120])
        return source

    def display_tree(self, value, field=None, skip_labels=False):
        if isinstance(value, dict):
            # This finding is synthesized by the helper from a recorded boolean,
            # rather than authored assessment prose or translation evidence.
            incomplete = (str(value.get('id', '')).startswith('inspection:')
                          and value.get('observed') == 'Required inspection is incomplete.')
            result = {key: self.display_tree(item, key, skip_labels) for key, item in value.items()
                      if not (incomplete and key == 'observed')}
            if incomplete:
                t = self.texts('report')
                result['observed'] = t['inspection'] + ' · ' + t['unchecked']
            if field == 'outfit_components' and isinstance(value.get('source'), str):
                result['source'] = self.display(value['source'])
            return result
        if isinstance(value, list):
            return [self.display_tree(item, field, skip_labels) for item in value]
        if isinstance(value, str) and field in ('fit', 'preservation', 'usability') and value != 'unspecified':
            for key in ('满意', '不满意', '可使用', '需要调整'):
                if any(value == catalog['html'][key] for catalog in self.locale.CATALOGS.values()):
                    return self.texts('html')[key]
            return self.display(value)
        if isinstance(value, str) and field == 'reason' and value in REASON_CODES:
            return value
        if isinstance(value, str) and field in TEXT_FIELDS | TEXT_LISTS and not (field == 'label' and skip_labels):
            return self.display(value)
        return copy.deepcopy(value)

    def snapshot(self):
        body = {'language': self.language, 'direction': self.direction, 'pack': self.pack,
                'translations': list(self.entries.values()), 'strict': self.strict,
                'font_file': self.font_file, 'source': self.source, 'preference_language': self.preference_language,
                'font_sha256': hashlib.sha256(Path(self.font_file).read_bytes()).hexdigest() if self.font_file else None}
        return {**body, 'sha256': fingerprint(body)}

    def provenance(self):
        return {'language': self.language, 'direction': self.direction, 'source': self.source,
                'catalog_sha256': fingerprint(self.texts_catalog()), 'translations': list(self.used.values())}

    def texts_catalog(self):
        return self.pack['catalogs'] if self.pack else self.locale.CATALOGS[self.language]


def from_snapshot(locale, data):
    if not isinstance(data, dict) or data.get('sha256') != fingerprint({k: v for k, v in data.items() if k != 'sha256'}):
        raise PresentationError('STALE_PRESENTATION', 'Presentation snapshot changed.')
    language = locale.normalize_language(data['language'])
    pack = validate_pack(locale, data['pack'], language) if data.get('pack') else None
    if pack is None and language not in locale.CATALOGS:
        raise PresentationError('MISSING_LOCALE_FILE', 'This language requires a complete language pack.')
    entries = validate_translations(locale, {'schema_version': '1.0', 'language': language, 'entries': data.get('translations', [])}, language)
    font_file = data.get('font_file')
    if font_file and (not Path(font_file).is_file() or data.get('font_sha256') != hashlib.sha256(Path(font_file).read_bytes()).hexdigest()):
        raise PresentationError('STALE_PRESENTATION_FONT', 'The saved presentation font changed or is missing.')
    result = Presentation(locale, language, pack, entries, data.get('strict', False), font_file, data.get('source', 'snapshot'))
    result.preference_language = data.get('preference_language')
    return result


def resolve(locale, roots=None, language=None, locale_file=None, translations_file=None, font_file=None):
    explicit = language is not None or locale_file is not None
    settings = []
    for root in roots or []:
        path = Path(root) / 'presentation.json'
        if path.exists():
            settings.append(from_snapshot(locale, read_json(path)))
    if language is None:
        if len({item.language for item in settings}) > 1:
            raise PresentationError('AMBIGUOUS_TASK_LANGUAGE', 'Projects have different task languages; choose --language.')
        language = settings[0].language if settings else locale.DEFAULT_LANGUAGE
    language = locale.normalize_language(language)
    matching = [item for item in settings if item.language == language]
    pack = validate_pack(locale, read_json(locale_file), language) if locale_file else next((p.pack for p in matching if p.pack), None)
    if pack is None and language not in locale.CATALOGS:
        raise PresentationError('MISSING_LOCALE_FILE', 'Prepare a complete language pack with language-template.')
    if len({fingerprint(item.pack) for item in matching}) > 1 and locale_file is None:
        raise PresentationError('AMBIGUOUS_TASK_LANGUAGE', 'Projects have different language packs; choose --locale-file.')
    entries = {}
    for item in settings:
        if item.language != language:
            for key, entry in item.entries.items():
                if locale.normalize_language(entry['source_language']) == language:
                    entries[key] = {**entry, 'translation': entry['source']}
    for item in matching:
        for key, entry in item.entries.items():
            if key in entries and entries[key] != entry:
                raise PresentationError('AMBIGUOUS_TRANSLATION', 'Projects disagree on a display translation.')
            entries[key] = entry
    if translations_file:
        entries.update(validate_translations(locale, read_json(translations_file), language))
    selected_font = str(Path(font_file).resolve()) if font_file else next((p.font_file for p in matching if p.font_file), None)
    if selected_font and not Path(selected_font).is_file():
        raise PresentationError('INVALID_PRESENTATION_FONT', 'Configured preview font is missing.')
    result = Presentation(locale, language, pack, entries, bool(pack or translations_file or any(p.strict for p in settings)), selected_font,
                          'override' if explicit else 'task' if matching else 'default')
    result.preference_language = next((p.preference_language for p in settings if p.preference_language), None)
    return result


def configure(locale, root, language, locale_file=None, translations_file=None, font_file=None, basis='user_request', request=None, clear_preference=False):
    if basis not in ('explicit', 'user_request', 'task_context'):
        raise PresentationError('INVALID_LANGUAGE_DECISION', 'Record explicit preference, user request or task context.')
    current_path = Path(root) / 'presentation.json'
    previous = read_json(current_path) if current_path.exists() else None
    preference = previous.get('preference_language') if previous and not clear_preference else None
    if basis != 'explicit' and preference:
        if locale.normalize_language(language) != preference:
            language, locale_file, translations_file = preference, None, None
        basis = 'explicit'
    elif basis == 'task_context' and previous:
        if locale.normalize_language(language) != previous['language']:
            language, locale_file, translations_file = previous['language'], None, None
    context = resolve(locale, [root], language, locale_file, translations_file, font_file)
    context.strict = True
    context.source = basis
    context.preference_language = context.language if basis == 'explicit' else preference
    body = context.snapshot()
    body.update(request_sha256=text_hash(request) if request else None, previous_sha256=previous.get('sha256') if previous else None)
    body['sha256'] = fingerprint({k: v for k, v in body.items() if k != 'sha256'})
    folder = Path(root) / 'presentation-history'
    folder.mkdir(exist_ok=True)
    history = folder / (body['sha256'] + '.json')
    if not history.exists():
        history.write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # No run.json migration or score/provenance mutation.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root, prefix='.presentation-', suffix='.json', delete=False) as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2)
        temporary = Path(stream.name)
    temporary.replace(current_path)
    return {'language': context.language, 'direction': context.direction, 'settings': str(current_path.resolve()), 'sha256': body['sha256']}


def content_plan(locale, roots, language=None):
    # A plan can be produced before an unknown-language pack exists.
    saved = [read_json(Path(root) / 'presentation.json') for root in roots if (Path(root) / 'presentation.json').exists()]
    language = locale.normalize_language(language or (saved[0]['language'] if saved else locale.DEFAULT_LANGUAGE))
    sources = set()
    for root in roots:
        sources.update(human_strings(read_json(Path(root) / 'run.json')))
    existing = {}
    for data in saved:
        if data['language'] == language:
            existing.update({item['source_sha256']: item for item in data.get('translations', [])})
    return {'schema_version': '1.0', 'language': language, 'entries': [existing.get(text_hash(text),
            {'source': text, 'source_sha256': text_hash(text), 'source_language': 'und', 'translation': '', 'reviewed': False})
            for text in sorted(sources)]}


def register_content(locale, root, value):
    """Register prose the assistant has authored in the current task language.

    The assistant must verify the actual language; this is provenance, not a
    statistical language detector and never rewrites a review record.
    """
    if not (Path(root) / 'presentation.json').exists():
        raise PresentationError('MISSING_TASK_LANGUAGE', 'Persist the task language before registering authored content.')
    context = resolve(locale, [root])
    for source in human_strings(value):
        key = text_hash(source)
        existing = context.entries.get(key)
        if existing and existing['translation'] != source:
            raise PresentationError('CONTENT_LANGUAGE_CONFLICT', 'This original already has a translated display value.')
        context.entries[key] = {'source': source, 'source_sha256': key, 'source_language': context.language,
                                'translation': source, 'reviewed': True}
    body = context.snapshot()
    previous = read_json(Path(root) / 'presentation.json') if (Path(root) / 'presentation.json').exists() else None
    body['previous_sha256'] = previous['sha256'] if previous else None
    body['sha256'] = fingerprint({k: v for k, v in body.items() if k != 'sha256'})
    history = Path(root) / 'presentation-history'
    history.mkdir(exist_ok=True)
    target = history / (body['sha256'] + '.json')
    if not target.exists():
        target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding='utf-8')
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root, prefix='.presentation-', suffix='.json', delete=False) as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2)
        temporary = Path(stream.name)
    temporary.replace(Path(root) / 'presentation.json')
    return {'language': context.language, 'registered': len(context.entries), 'sha256': body['sha256']}
