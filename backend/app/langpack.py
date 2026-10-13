"""Modules whose texts depend on the language are loaded twice.

The original is Russian; the twin ``app.<name>__en`` is the same file loaded under another
name: the module learns its language from its name (``i18n.twin_lang``). The module is taken in the
language of the campaign the request belongs to (outside a campaign, the instance language) at call
time: ``langpack.prompting().default_kit()``, not ``from .prompting import ...``.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from types import ModuleType

from .i18n import LANGS, content_lang

TWINS = ("app.prompting", "app.schema_defs", "app.names")


def _twin(name: str, lang: str) -> ModuleType:
    alias = f"{name}__{lang}"
    if alias in sys.modules:
        return sys.modules[alias]
    spec = importlib.util.find_spec(name)
    twin = importlib.util.spec_from_file_location(
        alias, spec.origin, submodule_search_locations=spec.submodule_search_locations,
    )
    mod = importlib.util.module_from_spec(twin)
    sys.modules[alias] = mod
    twin.loader.exec_module(mod)
    return mod


_MODS: dict[str, dict[str, ModuleType]] = {
    name: {lang: importlib.import_module(name) if lang == "ru" else _twin(name, lang)
           for lang in LANGS}
    for name in TWINS
}


def _pick(name: str, lang: str | None) -> ModuleType:
    return _MODS[name][lang if lang in LANGS else content_lang()]


def prompting(lang: str | None = None) -> ModuleType:
    return _pick("app.prompting", lang)


def schema(lang: str | None = None) -> ModuleType:
    return _pick("app.schema_defs", lang)


def names(lang: str | None = None) -> ModuleType:
    return _pick("app.names", lang)
