"""
Unit + regression tests for PUBLIC ↔ TESTNET network switch.

Covers:
- Pure Python helpers (mirror of sm_network.js)
- Template markup (real switch button, not bare checkbox)
- Static JS module exports expected API surface
"""
from pathlib import Path

from django.test import SimpleTestCase

from webApp.network_toggle import (
    PUBLIC,
    TESTNET,
    display_label,
    is_public_network,
    network_from_toggle,
    next_state,
    normalize_network,
    toggle_from_network,
)

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent


class NetworkToggleLogicTests(SimpleTestCase):
    def test_normalize_public_aliases(self):
        self.assertEqual(normalize_network("public"), PUBLIC)
        self.assertEqual(normalize_network("PUBLIC"), PUBLIC)
        self.assertEqual(normalize_network(""), PUBLIC)
        self.assertEqual(normalize_network(None), PUBLIC)
        self.assertEqual(normalize_network("mainnet"), PUBLIC)

    def test_normalize_testnet_aliases(self):
        self.assertEqual(normalize_network("testnet"), TESTNET)
        self.assertEqual(normalize_network("TESTNET"), TESTNET)
        self.assertEqual(normalize_network("test"), TESTNET)
        self.assertEqual(normalize_network("test-net"), TESTNET)

    def test_network_from_toggle(self):
        self.assertEqual(network_from_toggle(True), PUBLIC)
        self.assertEqual(network_from_toggle(False), TESTNET)

    def test_toggle_from_network(self):
        self.assertTrue(toggle_from_network("public"))
        self.assertFalse(toggle_from_network("testnet"))
        self.assertTrue(is_public_network("public"))
        self.assertFalse(is_public_network("testnet"))

    def test_display_label_uppercase(self):
        self.assertEqual(display_label("public"), "PUBLIC")
        self.assertEqual(display_label("testnet"), "TESTNET")
        self.assertEqual(display_label("PUBLIC"), "PUBLIC")

    def test_next_state_public_to_testnet(self):
        state = next_state("public")
        self.assertFalse(state["network_toggle"])
        self.assertEqual(state["network_selected"], TESTNET)
        self.assertEqual(state["label"], "TESTNET")

    def test_next_state_testnet_to_public(self):
        state = next_state("testnet")
        self.assertTrue(state["network_toggle"])
        self.assertEqual(state["network_selected"], PUBLIC)
        self.assertEqual(state["label"], "PUBLIC")

    def test_next_state_round_trip(self):
        a = next_state("public")
        b = next_state(a["network_selected"])
        self.assertEqual(b["network_selected"], PUBLIC)
        self.assertTrue(b["network_toggle"])

    def test_next_state_unknown_defaults_as_public(self):
        state = next_state("weird")
        # treated as public → flip to testnet
        self.assertEqual(state["network_selected"], TESTNET)


class NetworkSwitchMarkupRegressionTests(SimpleTestCase):
    """Prevent regression to bare checkbox that looked broken without Bootstrap CSS."""

    def setUp(self):
        self.include = (
            PROJECT_ROOT / "webApp/templates/webApp/search_container_include.html"
        ).read_text()
        self.search_js = (
            PROJECT_ROOT / "webApp/templates/webApp/search.html"
        ).read_text()

    def test_uses_switch_button_not_b_form_checkbox(self):
        self.assertIn('data-testid="network-switch"', self.include)
        self.assertIn("sm-network-switch", self.include)
        self.assertIn('role="switch"', self.include)
        self.assertIn("toggleNetworkSwitch", self.include)
        self.assertIn("PUBLIC", self.include)
        self.assertIn("TESTNET", self.include)
        self.assertNotIn("b-form-checkbox", self.include)

    def test_search_page_defines_toggle_handler(self):
        self.assertIn("toggleNetworkSwitch()", self.search_js)
        self.assertIn("networkLabel()", self.search_js)
        self.assertIn("StellarMapNetwork", self.search_js)

    def test_sm_network_js_exports_api(self):
        js_path = PROJECT_ROOT / "webApp/static/webApp/js/sm_network.js"
        self.assertTrue(js_path.is_file(), "sm_network.js missing")
        js = js_path.read_text()
        for name in (
            "nextState",
            "displayLabel",
            "networkFromToggle",
            "toggleFromNetwork",
            "normalizeNetwork",
            "StellarMapNetwork",
            # Required so pages with search_container_include do not blank on Vue mount
            "sm_network_mixin",
            "networkLabel",
            "toggleNetworkSwitch",
        ):
            self.assertIn(name, js)

    def test_css_defines_switch_states(self):
        css = (PROJECT_ROOT / "webApp/static/webApp/css/frontend.css").read_text()
        self.assertIn(".sm-network-switch", css)
        self.assertIn(".sm-network-switch.is-public", css)
        self.assertIn(".sm-network-switch.is-testnet", css)
        self.assertIn(".sm-network-switch__thumb", css)

    def test_python_and_js_agree_on_toggle_semantics(self):
        """Keep Python helpers and JS string constants aligned."""
        js = (PROJECT_ROOT / "webApp/static/webApp/js/sm_network.js").read_text()
        self.assertIn("var PUBLIC = 'public'", js)
        self.assertIn("var TESTNET = 'testnet'", js)
        # nextState public → testnet is encoded in JS
        self.assertIn("networkFromToggle", js)
        self.assertEqual(next_state("public")["network_selected"], "testnet")
        self.assertEqual(next_state("testnet")["network_selected"], "public")


class NetworkSwitchRenderedHtmlTests(SimpleTestCase):
    """Ensure live template include still has switch after deploy regressions."""

    def test_search_page_loads_sm_network_js_before_vue(self):
        search = (
            PROJECT_ROOT / "webApp/templates/webApp/search.html"
        ).read_text()
        self.assertIn("sm_network.js", search)
        self.assertLess(search.find("sm_network.js"), search.find("vue@2"))

    def test_shell_pages_load_sm_network_js_before_vue(self):
        """Home/dashboard/etc. must define networkLabel via mixin or Vue render blanks #app."""
        pages = (
            "webApp/templates/webApp/index.html",
            "webApp/templates/webApp/dashboard.html",
            "webApp/templates/webApp/bulk_search.html",
            "webApp/templates/webApp/high_value_accounts.html",
            "webApp/templates/webApp/query_builder.html",
        )
        for rel in pages:
            text = (PROJECT_ROOT / rel).read_text()
            self.assertIn("sm_network.js", text, rel)
            self.assertLess(
                text.find("sm_network.js"),
                text.find("vue@2"),
                f"{rel}: sm_network.js must load before Vue",
            )
            self.assertIn(
                "sm_network_mixin",
                text,
                f"{rel}: must use sm_network_mixin so networkLabel exists at render",
            )
