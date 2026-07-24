"""
Network toggle helpers (public ↔ testnet).

Mirrors webApp/static/webApp/js/sm_network.js for server-side / unit tests.
Keep semantics in sync when changing either file.
"""
from __future__ import annotations

from typing import TypedDict

PUBLIC = "public"
TESTNET = "testnet"


class NetworkState(TypedDict):
    network_toggle: bool
    network_selected: str
    label: str


def normalize_network(value: str | None) -> str:
    v = (value or "").strip().lower()
    if v in (TESTNET, "test", "test-net"):
        return TESTNET
    return PUBLIC


def is_public_network(value: str | None) -> bool:
    return normalize_network(value) == PUBLIC


def network_from_toggle(is_public: bool) -> str:
    return PUBLIC if is_public else TESTNET


def toggle_from_network(network: str | None) -> bool:
    return is_public_network(network)


def display_label(network: str | None) -> str:
    return normalize_network(network).upper()


def next_state(current_network: str | None) -> NetworkState:
    """Flip PUBLIC ↔ TESTNET."""
    currently_public = is_public_network(current_network)
    network_toggle = not currently_public
    network_selected = network_from_toggle(network_toggle)
    return {
        "network_toggle": network_toggle,
        "network_selected": network_selected,
        "label": display_label(network_selected),
    }
