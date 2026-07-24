"""
Regression: System Dashboard UI conforms to heartbeat panel language.

Guards against:
- Metric sections using fixed square cards without dash-panel wrappers
- Losing shared shell / network mixin on dashboard
"""
from pathlib import Path
import re

from django.test import Client, SimpleTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = PROJECT_ROOT / "webApp/templates/webApp/dashboard.html"
CSS = PROJECT_ROOT / "webApp/static/webApp/css/frontend.css"


class DashboardTemplateConformityTests(SimpleTestCase):
    def setUp(self):
        self.html = DASHBOARD.read_text()
        self.css = CSS.read_text()

    def test_heartbeat_and_metrics_share_dash_panel(self):
        self.assertIn('class="dash-panel heartbeat-panel"', self.html)
        # Metric sections wrap grids
        self.assertGreaterEqual(self.html.count('class="dash-panel"'), 2)
        self.assertIn('class="dashboard-grid"', self.html)
        # Panel count should cover each dashboard-grid
        panels = self.html.count("dash-panel")
        grids = self.html.count("dashboard-grid")
        self.assertGreaterEqual(panels, grids)

    def test_stat_cards_not_forced_square_in_css(self):
        """Compact heartbeat-like cards: no fixed 180px square metric tiles."""
        # Primary .stat-card rule must not force square layout
        m = re.search(
            r"\.stat-card\s*\{([^}]+)\}",
            self.css,
        )
        self.assertIsNotNone(m, "missing .stat-card rule")
        body = m.group(1)
        self.assertNotIn("width: 180px", body)
        self.assertNotIn("height: 180px", body)
        self.assertIn("min-width: 160px", body)
        # Shared panel language
        self.assertIn(".dash-panel", self.css)
        self.assertIn(".heartbeat-panel", self.css)

    def test_page_title_and_section_titles(self):
        self.assertIn("dash-page-title", self.html)
        self.assertIn("Dependency Heartbeat", self.html)
        self.assertIn("API Health Monitoring", self.html)
        self.assertIn("sm_network_mixin", self.html)
        self.assertIn("sm_network.js", self.html)

    def test_div_tags_balanced(self):
        plain = re.sub(r"\{%.*?%\}", "", self.html, flags=re.S)
        plain = re.sub(r"\{\{.*?\}\}", "", plain, flags=re.S)
        opens = len(re.findall(r"<div\b", plain))
        closes = plain.count("</div>")
        self.assertEqual(opens, closes, f"div mismatch open={opens} close={closes}")


class DashboardHttpShellTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_dashboard_200_shell_markers(self):
        resp = self.client.get("/dashboard/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("Dependency Heartbeat", html)
        self.assertIn("dash-panel", html)
        self.assertIn("stat-card", html)
        self.assertIn("sm_network.js", html)
        self.assertIn('id="app"', html)
