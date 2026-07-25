"""
Static contract tests for radial tree full-circle layout + mobile controls.
(Does not require pytest or a live database.)
"""
from pathlib import Path

from django.test import SimpleTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RadialLayoutContractTests(SimpleTestCase):
    def setUp(self):
        self.js = (
            PROJECT_ROOT
            / "radialTidyTreeApp/static/radialTidyTreeApp/d3-3.2.2/tidytree.js"
        ).read_text()
        self.css = (
            PROJECT_ROOT
            / "radialTidyTreeApp/static/radialTidyTreeApp/css/visualization_controls.css"
        ).read_text()
        self.include = (
            PROJECT_ROOT
            / "radialTidyTreeApp/templates/radialTidyTreeApp/visualization_toggle_include.html"
        ).read_text()

    def test_full_circle_size_layout(self):
        self.assertIn("2 * Math.PI", self.js)
        self.assertIn(".size([2 * Math.PI", self.js)
        self.assertIn(".separation(", self.js)
        # Adaptive radius from sibling density
        self.assertIn("maxSiblingsAtDepth", self.js)
        self.assertIn("minArcPx", self.js)
        # Must not re-introduce half-circle lineage sector clamp
        self.assertNotIn("maxSectorSize = Math.PI", self.js)
        self.assertNotIn("Fibonacci spiral", self.js)

    def test_angle_normalization_present(self):
        self.assertIn("Normalize angles", self.js)
        self.assertIn("minX", self.js)
        self.assertIn("2 * Math.PI", self.js)

    def test_mobile_controls_collapsible(self):
        self.assertIn("viz-controls-toggle", self.include)
        self.assertIn("is-collapsed", self.css)
        self.assertIn("max-width: 1024px", self.css)
        # Controls must not stay absolute overlay on iPad
        self.assertIn("position: relative !important", self.css)

    def test_filter_debounce_present(self):
        self.assertIn("applyTreeFiltersDebounced", self.include)
