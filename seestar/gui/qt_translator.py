# Qt translation wrapper for ZeAnalyser

from typing import Optional
from zone import translations

class QtTranslator:
    def __init__(self, lang: str = 'fr'):
        self.lang = lang if lang in translations else 'fr'

    def set_language(self, lang: str):
        if lang in translations:
            self.lang = lang

    def tr(self, key: str, **kwargs) -> str:
        """
        Return the translated string for the given key, formatted with kwargs if needed.
        """
        value = translations.get(self.lang, {}).get(key, key)
        if kwargs:
            try:
                return value.format(**kwargs)
            except Exception:
                return value
        return value

qt_translator = QtTranslator()
