from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.transaction_actions_v4 import ContractActionV4


def test_v4_actions_compile_to_strict_browsergym_code() -> None:
    assert ContractActionV4("click", "B12").browsergym_code() == "click('B12')"
    assert ContractActionV4(
        "fill", "field9", 'Montr"eal', True
    ).browsergym_code() == 'fill(\'field9\', \'Montr"eal\', True)'
    assert ContractActionV4(
        "select_option", "countries", ("Megan", "Karleen")
    ).browsergym_code() == "select_option('countries', ['Megan', 'Karleen'])"
    assert ContractActionV4(
        "select_option", "countries", ()
    ).browsergym_code() == "select_option('countries', [])"
    assert ContractActionV4(
        "move_to_neutral_region"
    ).browsergym_code(viewport_width=800, viewport_height=600) == (
        "mouse_move(795, 595)"
    )


@pytest.mark.parametrize(
    "factory, message",
    (
        (lambda: ContractActionV4("click", "bad-bid"), "unsafe BrowserGym bid"),
        (lambda: ContractActionV4("fill", "B1"), "fill requires"),
        (
            lambda: ContractActionV4("select_option", "B1", ["x"]),
            "requires a tuple",
        ),
        (
            lambda: ContractActionV4("select_option", "B1", ("x", "x")),
            "must be unique",
        ),
        (
            lambda: ContractActionV4("press", "B1", "Escape\nclick"),
            "unsafe key combination",
        ),
    ),
)
def test_v4_actions_reject_unsafe_or_ambiguous_arguments(factory, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()
