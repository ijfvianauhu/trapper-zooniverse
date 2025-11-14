import gettext

# Configuración por defecto
_current_language = 'es'
_translations = {}

def setup_i18n(language='es', locale_dir='locales'):
    global _current_language, _translations
    _current_language = language
    try:
        _translations[language] = gettext.translation(
            'messages',
            localedir=locale_dir,
            languages=[language]
        )
    except FileNotFoundError as e:
        # Fallback a traducciones nulas
        _translations[language] = gettext.NullTranslations()


def get_translator():
    return _translations.get(_current_language, gettext.NullTranslations())


def _(text):
    return get_translator().gettext(text)


def get_language():
    return _current_language
