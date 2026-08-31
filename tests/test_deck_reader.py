import pytest

from mtg_proxy.deck import parse_deck
from mtg_proxy.deck.reader import DeckParseError


def test_parse_simple_name():
    reqs, errors = parse_deck("Sol Ring\n")
    assert errors == []
    assert len(reqs) == 1
    assert reqs[0].name == "Sol Ring"
    assert reqs[0].quantity == 1
    assert reqs[0].language is None


def test_parse_quantity():
    reqs, errors = parse_deck("Lightning Bolt x4\n")
    assert errors == []
    assert reqs[0].name == "Lightning Bolt"
    assert reqs[0].quantity == 4


def test_parse_language():
    reqs, errors = parse_deck("Lightning Bolt | pt\n", default_language="en")
    assert errors == []
    assert reqs[0].language == "pt"


def test_parse_quantity_and_language():
    reqs, errors = parse_deck("Lightning Bolt x2 | pt\n")
    assert errors == []
    assert reqs[0].quantity == 2
    assert reqs[0].language == "pt"


def test_parse_set_only():
    reqs, errors = parse_deck("Lightning Bolt | set=FDN\n", default_language="pt")
    assert errors == []
    assert reqs[0].set_code == "FDN"
    assert reqs[0].language == "pt"


def test_parse_full():
    reqs, errors = parse_deck("Lightning Bolt x2 | pt | set=FDN\n")
    assert errors == []
    req = reqs[0]
    assert req.quantity == 2
    assert req.language == "pt"
    assert req.set_code == "FDN"


def test_parse_collector_number():
    reqs, errors = parse_deck("Lightning Bolt | cn=192\n")
    assert errors == []
    assert reqs[0].collector_number == "192"


def test_ignores_blank_and_comments():
    text = "# Ramp\nSol Ring\n\n# Removal\nPath to Exile\n"
    reqs, errors = parse_deck(text)
    assert errors == []
    names = [r.name for r in reqs]
    assert names == ["Sol Ring", "Path to Exile"]


def test_default_language_applied():
    reqs, errors = parse_deck("Sol Ring\n", default_language="pt")
    assert errors == []
    assert reqs[0].language == "pt"


def test_invalid_quantity_reports_error():
    reqs, errors = parse_deck("Weird Card x0\n")
    assert reqs == []
    assert len(errors) == 1
    assert "quantidade inválida" in errors[0]


def test_unknown_option_reports_error():
    reqs, errors = parse_deck("Foo | foo=bar\n")
    assert reqs == []
    assert any("opção desconhecida" in e for e in errors)


def test_empty_name_reports_error():
    reqs, errors = parse_deck("| pt\n")
    assert reqs == []
    assert any("nome da carta vazio" in e for e in errors)


def test_language_uppercase_normalized():
    reqs, errors = parse_deck("Bolt | PT\n")
    assert errors == []
    assert reqs[0].language == "pt"


def test_parse_leading_quantity():
    reqs, errors = parse_deck("6 Island\n")
    assert errors == []
    assert reqs[0].name == "Island"
    assert reqs[0].quantity == 6


def test_parse_trailing_2x():
    reqs, errors = parse_deck("Counterspell 2x\n")
    assert errors == []
    assert reqs[0].name == "Counterspell"
    assert reqs[0].quantity == 2


def test_parse_leading_quantity_with_x():
    reqs, errors = parse_deck("35x Mountain\n")
    assert errors == []
    assert reqs[0].name == "Mountain"
    assert reqs[0].quantity == 35


def test_parse_leading_quantity_with_x_and_space():
    reqs, errors = parse_deck("35X Mountain\n")
    assert errors == []
    assert reqs[0].name == "Mountain"
    assert reqs[0].quantity == 35


def test_ignores_section_headers():
    text = (
        "COMMANDER\n"
        "1 Niv-Mizzet, Parun\n"
        "LANDS (36)\n"
        "1 Command Tower\n"
        "6 Island\n"
    )
    reqs, errors = parse_deck(text)
    assert errors == []
    names = [r.name for r in reqs]
    assert "COMMANDER" not in names
    assert "LANDS (36)" not in names
    assert names == ["Niv-Mizzet, Parun", "Command Tower", "Island"]
    assert sum(r.quantity for r in reqs) == 8


def test_parse_double_faced_card():
    reqs, errors = parse_deck("1 Riverglide Pathway // Lavaglide Pathway\n")
    assert errors == []
    assert reqs[0].name == "Riverglide Pathway // Lavaglide Pathway"
    assert reqs[0].quantity == 1


def test_parse_commander_export_full():
    text = """COMMANDER
1 Niv-Mizzet, Parun

LANDS (36)
1 Command Tower
1 Steam Vents
6 Island
7 Mountain

RAMP (6)
1 Sol Ring
1 Arcane Signet

INTERACTION (2)
1 Counterspell
2 Lightning Bolt
"""
    reqs, errors = parse_deck(text)
    assert errors == []
    # Soma das quantidades efetivamente listadas (os números nos cabeçalhos
    # são apenas ilustrativos e ignorados): 1 + (1+1+6+7) + (1+1) + (1+2) = 21
    assert sum(r.quantity for r in reqs) == 21
    by_name = {r.name: r.quantity for r in reqs}
    assert by_name["Niv-Mizzet, Parun"] == 1
    assert by_name["Island"] == 6
    assert by_name["Mountain"] == 7
    assert by_name["Counterspell"] == 1
    assert by_name["Lightning Bolt"] == 2

