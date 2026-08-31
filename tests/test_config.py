from mtg_proxy.config import DEFAULT_CONFIG, load_config


def test_load_defaults_without_file():
    config = load_config()
    assert config.cards.default_language == "pt"
    assert config.cards.fallback_language == "en"
    assert config.print.card_width_mm == 63
    assert config.page.orientation == "portrait"
    assert config.duplex.flip == "long_edge"


def test_load_config_merges_user_values(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "cards:\n  default_language: en\n"
        "duplex:\n  flip: short_edge\n",
        encoding="utf-8",
    )
    config = load_config(str(cfg))
    assert config.cards.default_language == "en"
    # Valores não sobrescritos mantêm o padrão.
    assert config.cards.fallback_language == "en"
    assert config.duplex.flip == "short_edge"
    assert config.page.width_mm == 210


def test_missing_config_raises(tmp_path):
    import pytest

    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError):
        load_config(str(missing))


def test_default_config_well_formed():
    assert "scryfall" in DEFAULT_CONFIG
    assert "output" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["print"]["card_width_mm"] == 63
