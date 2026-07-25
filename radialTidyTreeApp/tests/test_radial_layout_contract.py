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
        self.assertIn("minChordPx", self.js)
        # Non-overlap post-process
        self.assertIn("resolveRadialNodeOverlaps", self.js)
        # Must not re-introduce half-circle lineage sector clamp
        self.assertNotIn("maxSectorSize = Math.PI", self.js)
        self.assertNotIn("Fibonacci spiral", self.js)

    def test_properties_pane_and_breadcrumbs(self):
        self.assertIn("renderTreePropertiesPane", self.js)
        self.assertIn("renderTreeBreadcrumbs", self.js)
        self.assertIn("sm-tree-props", self.js)
        self.assertIn("sm-tree-breadcrumbs", self.js)
        # Original tooltip field labels
        self.assertIn("Name", self.js)
        self.assertIn("XLM Balance", self.js)
        self.assertIn("sm-tree-props--asset", self.js)
        self.assertIn("selectNode", self.js)
        partial = (
            PROJECT_ROOT
            / "radialTidyTreeApp/templates/radialTidyTreeApp/radial_tidy_tree_partial.html"
        ).read_text()
        self.assertIn("sm-tree-props", partial)
        self.assertIn("sm-tree-breadcrumbs", partial)
        self.assertIn("sm-tree-props--issuer", partial)
        self.assertIn("rgba(63, 44, 112", partial)
        # Pinned overlays (must not flex-center with the SVG)
        self.assertIn("#radial-tree-container > .sm-tree-breadcrumbs", partial)
        self.assertIn("left: 10px !important", partial)
        self.assertIn("right: 12px !important", partial)
        self.assertIn("ensureTreeChrome", self.js)
        self.assertIn("host.appendChild(crumbs)", self.js)

    def test_mobile_controls_compact(self):
        self.assertIn("max-height: min(38vh", self.css)
        self.assertIn("viz-controls-toolbar", self.css)
        self.assertIn("viz-controls-toolbar", self.include)

    def test_angle_normalization_present(self):
        self.assertIn("Normalize angles", self.js)
        self.assertIn("minX", self.js)
        self.assertIn("2 * Math.PI", self.js)

    def test_mobile_controls_collapsible(self):
        self.assertIn("viz-controls-toggle", self.include)
        self.assertIn("is-collapsed", self.css)
        self.assertIn("max-width: 1024px", self.css)
        # Controls must never absolute-overlay the tree (looked like a pinned node)
        self.assertIn("position: relative", self.css)
        self.assertNotIn(
            "position: absolute;\n    top: 12px;\n    right: 12px;",
            self.css.replace("\r\n", "\n"),
        )
        self.assertIn("Default closed", self.include)

    def test_filter_debounce_present(self):
        self.assertIn("applyTreeFiltersDebounced", self.include)
