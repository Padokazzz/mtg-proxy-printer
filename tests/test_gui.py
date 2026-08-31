import threading

import pytest

from mtg_proxy.cli import configure_mode, run_generate
from mtg_proxy.config import load_config


def test_configure_mode_front_disables_duplex():
    cfg = load_config()
    out = configure_mode(cfg, "front")
    assert out.duplex.enabled is False
    assert out.output.generate_back_pdf is False
    assert out.output.generate_front_pdf is True
    assert out.output.generate_combined_pdf is False


def test_configure_mode_duplex_enables_back():
    cfg = load_config()
    out = configure_mode(cfg, "duplex")
    assert out.duplex.enabled is True
    assert out.output.generate_front_pdf is False
    assert out.output.generate_back_pdf is False
    assert out.output.generate_combined_pdf is True


def test_configure_mode_does_not_mutate_original():
    cfg = load_config()
    original = cfg.duplex.enabled
    configure_mode(cfg, "front")
    assert cfg.duplex.enabled is original


def test_run_generate_respects_cancel(tmp_path):
    cfg = load_config()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        run_generate("1 Sol Ring", cfg, tmp_path, cancel=cancel)
