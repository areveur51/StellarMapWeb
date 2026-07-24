"""
PR6b: search UI prefers server tree when algorithm matches.
"""
from pathlib import Path

from django.test import SimpleTestCase

from apiApp.helpers.sm_lineage_aggregate import TREE_ALGORITHM


class FrontendServerTreeSourceTests(SimpleTestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        self.search_html = (
            root / "webApp/templates/webApp/search.html"
        ).read_text()

    def test_algorithm_constant_matches_server(self):
        self.assertEqual(TREE_ALGORITHM, "buildTreeFromLineage_v1")
        self.assertIn(f"SERVER_TREE_ALGORITHM: '{TREE_ALGORITHM}'", self.search_html)

    def test_fetch_prefers_server_tree(self):
        self.assertIn("canUseServerTree", self.search_html)
        self.assertIn("applyTreeData", self.search_html)
        self.assertIn("applyLineageApiPayload", self.search_html)
        self.assertIn("this.canUseServerTree(data)", self.search_html)
        self.assertIn("this.applyTreeData(data.tree,", self.search_html)
        self.assertIn("this.buildTreeFromLineage(allAccountsForTree)", self.search_html)

    def test_fallback_path_still_present(self):
        # Client builder remains for mismatched/missing algorithm
        self.assertIn("buildTreeFromLineage(accountData)", self.search_html)
        self.assertIn("XLM_SIBLING_TREE_THRESHOLD", self.search_html)
