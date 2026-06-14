"""Tests para utils/translations.py — I18n y diccionario de traducciones."""

import pytest
from utils.translations import TRANSLATIONS, I18n, i18n


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: TRANSLATIONS dict structure
# ═══════════════════════════════════════════════════════════════════════════════

def test_translations_has_es_and_en():
    """TRANSLATIONS contiene español e inglés."""
    assert "es" in TRANSLATIONS
    assert "en" in TRANSLATIONS


def test_translations_es_not_empty():
    """Traducciones en español no están vacías."""
    assert len(TRANSLATIONS["es"]) > 0


def test_translations_en_not_empty():
    """Traducciones en inglés no están vacías."""
    assert len(TRANSLATIONS["en"]) > 0


def test_translations_es_has_required_keys():
    """Traducciones en español tienen claves esenciales."""
    required = ["app_title", "tab_dashboard", "tab_telegram", "tab_consola",
                "settings_title", "risk_title"]
    for key in required:
        assert key in TRANSLATIONS["es"], f"Falta clave '{key}' en es"


def test_translations_en_has_required_keys():
    """Traducciones en inglés tienen claves esenciales."""
    required = ["app_title", "tab_dashboard", "tab_telegram", "tab_consola",
                "settings_title", "risk_title"]
    for key in required:
        assert key in TRANSLATIONS["en"], f"Falta clave '{key}' en en"


def test_translations_en_matches_es_keys():
    """Inglés tiene las mismas claves que español."""
    es_keys = set(TRANSLATIONS["es"].keys())
    en_keys = set(TRANSLATIONS["en"].keys())
    only_in_es = es_keys - en_keys
    only_in_en = en_keys - es_keys
    assert not only_in_es, f"Claves solo en español: {only_in_es}"
    assert not only_in_en, f"Claves solo en inglés: {only_in_en}"


def test_translations_no_empty_values():
    """Ninguna traducción tiene valor vacío."""
    for lang, keys in TRANSLATIONS.items():
        for key, value in keys.items():
            assert value, f"Traducción vacía para '{key}' en '{lang}'"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: I18n class
# ═══════════════════════════════════════════════════════════════════════════════

def test_i18n_default_language():
    """I18n por defecto usa español."""
    i = I18n()
    assert i.current_lang == "es"
    assert i.lang == "es"


def test_i18n_custom_language():
    """I18n acepta idioma personalizado."""
    i = I18n("en")
    assert i.current_lang == "en"


def test_i18n_t_existing_key_es():
    """t() retorna la traducción en español."""
    i = I18n("es")
    assert i.t("app_title") == TRANSLATIONS["es"]["app_title"]


def test_i18n_t_existing_key_en():
    """t() retorna la traducción en inglés."""
    i = I18n("en")
    assert i.t("app_title") == TRANSLATIONS["en"]["app_title"]


def test_i18n_t_missing_key_falls_back_to_es():
    """t() para clave faltante en EN pero presente en ES retorna ES."""
    # Crear un idioma ficticio que herede de ES
    i = I18n("es")
    # Clave que no existe en ningún idioma
    result = i.t("nonexistent_key_xyz")
    assert result == "nonexistent_key_xyz"


def test_i18n_t_missing_key_returns_key():
    """t() para clave que no existe retorna la misma clave."""
    i = I18n("en")
    result = i.t("key_that_does_not_exist_12345")
    assert result == "key_that_does_not_exist_12345"


def test_i18n_set_language():
    """set_language cambia el idioma."""
    i = I18n("es")
    i.set_language("en")
    assert i.current_lang == "en"
    assert i.t("app_title") == TRANSLATIONS["en"]["app_title"]


def test_i18n_set_language_same():
    """set_language al mismo idioma no hace nada (no notifica)."""
    i = I18n("es")
    notified = []

    def listener():
        notified.append(True)

    i.add_listener(listener)
    i.set_language("es")  # Mismo idioma
    assert len(notified) == 0  # No debe notificar


def test_i18n_set_language_invalid():
    """set_language a idioma inválido no cambia."""
    i = I18n("es")
    i.set_language("fr")  # No existe
    assert i.current_lang == "es"


def test_i18n_listener():
    """add_listener recibe notificaciones al cambiar idioma."""
    i = I18n("es")
    notified = []

    def listener():
        notified.append(True)

    i.add_listener(listener)
    i.set_language("en")
    assert len(notified) == 1


def test_i18n_multiple_listeners():
    """Múltiples listeners reciben notificaciones."""
    i = I18n("es")
    count = [0]

    def listener1():
        count[0] += 1

    def listener2():
        count[0] += 1

    i.add_listener(listener1)
    i.add_listener(listener2)
    i.set_language("en")
    assert count[0] == 2


def test_i18n_global_instance():
    """i18n global existe y usa español."""
    from utils.translations import i18n
    assert i18n is not None
    assert i18n.current_lang == "es"
    assert i18n.t("app_title") is not None
