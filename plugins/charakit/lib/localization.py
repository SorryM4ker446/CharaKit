"""Fixed presentation text shared by reports, HTML and PNG previews.

Saved requests, evidence, IDs and custom names are never translated here.
"""
import re
import importlib.util
from pathlib import Path
from types import SimpleNamespace

DEFAULT_LANGUAGE = "zh-CN"


def validate_language(language):
    if not isinstance(language, str) or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", language):
        raise PresentationError('INVALID_LANGUAGE_TAG', "Use a language tag such as zh-CN, en or ja.")
    return language


def normalize_language(language=DEFAULT_LANGUAGE):
    tag = validate_language(language)
    parts = tag.split('-')
    base = parts[0].lower()
    if base == "zh" and not any(p.lower() in ('tw', 'hk', 'mo', 'hant') for p in parts[1:]):
        return "zh-CN"
    if base == "en":
        return "en"
    return '-'.join([base] + [p.title() if len(p) == 4 else p.upper() if len(p) == 2 else p.lower() for p in parts[1:]])


def texts(section, language=DEFAULT_LANGUAGE, locale_file=None):
    """Return a copy; fixed keys are strict lookups, never English fallbacks."""
    return resolve(language=language, locale_file=locale_file).texts(section)


_task_spec = importlib.util.spec_from_file_location('charakit_task_localization', Path(__file__).with_name('task_localization.py'))
task = importlib.util.module_from_spec(_task_spec)
_task_spec.loader.exec_module(task)
PresentationError = task.PresentationError


BUILTIN_LOCALE_DIR = Path(__file__).resolve().parent.parent / 'locales'


def load_builtin_catalogs(directory=BUILTIN_LOCALE_DIR):
    """Load packaged defaults using the same pack validation as task languages."""
    try:
        packs = {language: task.read_json(Path(directory) / (language + '.json'))
                 for language in ('zh-CN', 'en')}
        baseline = packs['en']['catalogs']
        if not isinstance(baseline, dict) or set(baseline) != {'report', 'html', 'names', 'png', 'revision'}:
            raise ValueError('The English source catalog must contain every presentation section.')
        proxy = SimpleNamespace(CATALOGS={'en': baseline}, normalize_language=normalize_language,
                                validate_language=validate_language)
        catalogs = {language: task.validate_pack(proxy, pack, language)['catalogs']
                    for language, pack in packs.items()}
        groups = packs['en']['ui_groups']
        if (not isinstance(groups, dict) or set(groups) != {'summary', 'interaction', 'baseline'}
                or any(not isinstance(keys, list) or not keys or any(not isinstance(key, str) for key in keys)
                       or len(keys) != len(set(keys)) or not set(keys) <= set(baseline['html'])
                       for keys in groups.values())):
            raise ValueError('HTML compatibility groups must reference existing catalog keys.')
        return catalogs, groups
    except (ValueError, KeyError, TypeError) as exc:
        raise PresentationError('INVALID_BUILTIN_LOCALE',
                                'Missing or invalid packaged language resources: ' + str(directory)) from exc


CATALOGS, _UI_GROUPS = load_builtin_catalogs()
# Legacy renderer exports retain their names and key ordering; values come from JSON.
SUMMARY_LABELS = {key: CATALOGS['en']['html'][key] for key in _UI_GROUPS['summary']}
INTERACTION_LABELS = {key: CATALOGS['en']['html'][key] for key in _UI_GROUPS['interaction']}
BASELINE_LABELS = {key: CATALOGS['en']['html'][key] for key in _UI_GROUPS['baseline']}


def resolve(roots=None, language=None, locale_file=None, translations_file=None, font_file=None):
    import sys
    return task.resolve(sys.modules.get(__name__) or SimpleNamespace(**globals()), roots, language, locale_file, translations_file, font_file)


def locale_proxy():
    return SimpleNamespace(**globals())
