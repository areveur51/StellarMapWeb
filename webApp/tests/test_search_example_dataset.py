"""
Default /search/ landing shows a canned example radial tree (not live data).
"""
import json
from pathlib import Path

from django.test import Client, SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LineageExampleFixtureTests(SimpleTestCase):
    def test_lineage_example_json_matches_aggregate_schema(self):
        path = (
            PROJECT_ROOT
            / "radialTidyTreeApp/static/radialTidyTreeApp/json/lineage_example.json"
        )
        self.assertTrue(path.is_file(), "lineage_example.json missing")
        tree = json.loads(path.read_text())
        self.assertEqual(tree.get("node_type"), "ISSUER")
        self.assertTrue(tree.get("stellar_account", "").startswith("G"))
        for key in (
            "is_lineage_path",
            "is_sibling",
            "is_searched_account",
            "is_issuer",
            "children",
            "creator_account",
            "home_domain",
            "xlm_balance",
        ):
            self.assertIn(key, tree, f"missing {key}")

        # Must include a searched leaf and at least one sibling somewhere
        found_searched = False
        found_sibling = False
        found_asset = False

        def walk(n):
            nonlocal found_searched, found_sibling, found_asset
            if not isinstance(n, dict):
                return
            if n.get("is_searched_account"):
                found_searched = True
            if n.get("is_sibling"):
                found_sibling = True
            if n.get("node_type") == "ASSET":
                found_asset = True
            for c in n.get("children") or []:
                walk(c)

        walk(tree)
        self.assertTrue(found_searched, "example must flag is_searched_account")
        self.assertTrue(found_sibling, "example must include a sibling branch")
        self.assertTrue(found_asset, "example must include ASSET children")


class SearchExampleLandingHttpTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_search_landing_is_example_not_live_inquiry(self):
        resp = self.client.get("/search/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("Example dataset", html)
        self.assertIn("isExampleDataset: true", html)
        # Must not default-fill a fake inquiry account in the empty-state message path
        self.assertIn("EXAMPLE_DATASET", html)
