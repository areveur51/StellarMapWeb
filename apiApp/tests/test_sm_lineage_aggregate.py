"""
PR1: LineageAggregateService unit tests + golden fixtures.

No view wiring — pure service / adapters / tree parity with client rules.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apiApp.helpers.sm_lineage_aggregate import (
    XLM_SIBLING_TREE_THRESHOLD,
    TREE_ALGORITHM,
    AggregateOptions,
    LineageAggregateService,
    build_tree_from_nodes,
    extract_assets,
    parse_cache_body,
)


def _node(
    account,
    creator=None,
    xlm=0.0,
    assets=None,
    status="COMPLETE",
    network="public",
    in_path=False,
):
    return {
        "stellar_account": account,
        "stellar_creator_account": creator,
        "network_name": network,
        "stellar_account_created_at": "2023-01-01T00:00:00",
        "home_domain": "",
        "xlm_balance": xlm,
        "assets": assets or [],
        "status": status,
        "created_at": None,
        "updated_at": None,
        "is_issuer": bool(assets),
        "in_lineage_path": in_path,
    }


class ParseCacheBodyTests(SimpleTestCase):
    def test_invalid_str_dict_is_miss(self):
        kind, data = parse_cache_body("{'xlm_balance': 1.0, 'pipeline_source': 'API'}")
        self.assertEqual(kind, "miss")
        self.assertIsNone(data)

    def test_empty_is_miss(self):
        self.assertEqual(parse_cache_body("")[0], "miss")
        self.assertEqual(parse_cache_body(None)[0], "miss")

    def test_legacy_tree(self):
        tree = {"name": "GABC", "node_type": "ISSUER", "children": []}
        kind, data = parse_cache_body(json.dumps(tree))
        self.assertEqual(kind, "legacy_tree")
        self.assertEqual(data["name"], "GABC")

    def test_projection(self):
        proj = {
            "schema_version": 1,
            "nodes": {"G1": {"stellar_account": "G1"}},
            "lineage_path": ["G1"],
        }
        kind, data = parse_cache_body(json.dumps(proj))
        self.assertEqual(kind, "projection")
        self.assertIn("G1", data["nodes"])


class ExtractAssetsTests(SimpleTestCase):
    def test_extracts_non_native(self):
        horizon = {
            "balances": [
                {"asset_type": "native", "balance": "10"},
                {
                    "asset_type": "credit_alphanum4",
                    "asset_code": "USD",
                    "asset_issuer": "GISSUER",
                    "balance": "5.5",
                },
            ]
        }
        assets = extract_assets(json.dumps(horizon))
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["asset_code"], "USD")
        self.assertEqual(assets[0]["node_type"], "ASSET")
        self.assertEqual(assets[0]["balance"], 5.5)


class BuildTreeParityTests(SimpleTestCase):
    """Golden: depth-3 path + high/low XLM siblings + assets."""

    def setUp(self):
        self.root = "GROOT"
        self.mid = "GMID"
        self.leaf = "GLEAF"  # searched
        self.sib_hi = "GSIBHI"  # xlm >= 1000
        self.sib_lo = "GSIBLO"  # xlm < 1000
        self.nodes = {
            self.root: _node(self.root, None, 10000, in_path=True),
            self.mid: _node(
                self.mid,
                self.root,
                5000,
                assets=[
                    {
                        "name": "USD",
                        "node_type": "ASSET",
                        "asset_type": "credit_alphanum4",
                        "asset_code": "USD",
                        "asset_issuer": "GISSUER",
                        "balance": 1.0,
                    }
                ],
                in_path=True,
            ),
            self.leaf: _node(self.leaf, self.mid, 100, in_path=True),
            self.sib_hi: _node(self.sib_hi, self.mid, 1500, in_path=False),
            self.sib_lo: _node(self.sib_lo, self.mid, 50, in_path=False),
        }
        self.path = [self.root, self.mid, self.leaf]
        self.siblings = {self.mid: [self.sib_hi, self.sib_lo]}

    def test_tree_includes_high_xlm_sibling_excludes_low(self):
        tree = build_tree_from_nodes(
            self.nodes,
            self.path,
            self.siblings,
            searched_account=self.leaf,
            xlm_threshold=XLM_SIBLING_TREE_THRESHOLD,
        )
        self.assertEqual(tree["stellar_account"], self.root)
        self.assertTrue(tree.get("is_lineage_path"))

        # Find mid under root
        mid_nodes = [
            c
            for c in tree["children"]
            if c.get("node_type") == "ISSUER" and c.get("stellar_account") == self.mid
        ]
        self.assertEqual(len(mid_nodes), 1)
        mid = mid_nodes[0]
        child_accounts = {
            c.get("stellar_account")
            for c in mid["children"]
            if c.get("node_type") == "ISSUER"
        }
        self.assertIn(self.leaf, child_accounts)
        self.assertIn(self.sib_hi, child_accounts)
        self.assertNotIn(self.sib_lo, child_accounts)

        # High sibling flagged
        hi = next(
            c
            for c in mid["children"]
            if c.get("stellar_account") == self.sib_hi
        )
        self.assertTrue(hi["is_sibling"])
        self.assertFalse(hi["is_lineage_path"])

        # Assets under mid
        asset_names = [
            c.get("name") for c in mid["children"] if c.get("node_type") == "ASSET"
        ]
        self.assertIn("USD", asset_names)

    def test_threshold_constant_is_1000(self):
        self.assertEqual(XLM_SIBLING_TREE_THRESHOLD, 1000)


class AdapterGoldenTests(SimpleTestCase):
    def setUp(self):
        self.svc = LineageAggregateService()
        self.root, self.mid, self.leaf = "GROOT", "GMID", "GLEAF"
        self.sib_hi, self.sib_lo = "GSIBHI", "GSIBLO"
        self.projection = {
            "schema_version": 1,
            "account": self.leaf,
            "network": "public",
            "source": "database",
            "status": "COMPLETE",
            "lineage_path": [self.root, self.mid, self.leaf],
            "nodes": {
                self.root: _node(self.root, None, 10000, in_path=True),
                self.mid: _node(self.mid, self.root, 5000, in_path=True),
                self.leaf: _node(self.leaf, self.mid, 100, in_path=True),
                self.sib_hi: _node(self.sib_hi, self.mid, 1500, in_path=False),
                self.sib_lo: _node(self.sib_lo, self.mid, 50, in_path=False),
            },
            "siblings_by_creator": {self.mid: [self.sib_hi, self.sib_lo]},
            "edges": [],
            "tree": None,
            "tree_build": {
                "xlm_sibling_threshold": 1000,
                "algorithm": TREE_ALGORITHM,
            },
            "meta": {"build_ms": 1, "db_only": True},
        }
        # Attach tree
        self.projection["tree"] = build_tree_from_nodes(
            self.projection["nodes"],
            self.projection["lineage_path"],
            self.projection["siblings_by_creator"],
            self.leaf,
        )

    def test_table_has_three_path_rows_only(self):
        rows = self.svc.to_table_rows(self.projection)
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            [r["stellar_account"] for r in rows],
            [self.root, self.mid, self.leaf],
        )
        self.assertEqual(rows[0]["hierarchy_level"], 0)
        self.assertEqual(rows[2]["hierarchy_level"], 2)
        # No siblings in table
        accounts = {r["stellar_account"] for r in rows}
        self.assertNotIn(self.sib_hi, accounts)
        self.assertNotIn(self.sib_lo, accounts)

    def test_siblings_response_shape(self):
        resp = self.svc.to_siblings_response(self.projection)
        self.assertEqual(resp["account"], self.leaf)
        self.assertEqual(resp["network"], "public")
        self.assertEqual(resp["lineage_path"], [self.root, self.mid, self.leaf])
        self.assertIn(self.mid, resp["siblings_by_creator"])
        self.assertEqual(set(resp["siblings_by_creator"][self.mid]), {self.sib_hi, self.sib_lo})
        self.assertEqual(resp["total_siblings"], 2)
        self.assertIn(self.leaf, resp["all_account_data"])
        self.assertTrue(resp["all_account_data"][self.leaf]["in_lineage_path"])
        self.assertFalse(resp["all_account_data"][self.sib_hi]["in_lineage_path"])
        self.assertIn("tree", resp)
        self.assertIn("meta", resp)
        self.assertEqual(resp["meta"]["tree_build"]["algorithm"], TREE_ALGORITHM)

    def test_lineage_api_path_only(self):
        resp = self.svc.to_lineage_api_response(self.projection)
        self.assertEqual(resp["total_records"], 3)
        self.assertEqual(len(resp["lineage"]), 3)
        self.assertEqual(resp["source"], "database")

    def test_display_bundle_keys(self):
        with patch.object(
            LineageAggregateService, "get_projection", return_value=self.projection
        ):
            bundle = self.svc.get_display_bundle(self.leaf, "public")
        self.assertIn("tree_data", bundle)
        self.assertIn("account_lineage_data", bundle)
        self.assertIn("radial_tidy_tree_variable", bundle)
        self.assertEqual(bundle["account_genealogy_items"], [])
        self.assertEqual(len(bundle["account_lineage_data"]), 3)


class BuildProjectionDbTests(SimpleTestCase):
    """Mock ORM path walk + siblings."""

    def _rec(self, account, creator, xlm=0.0, horizon_json=None):
        return SimpleNamespace(
            stellar_account=account,
            stellar_creator_account=creator,
            network_name="public",
            stellar_account_created_at=None,
            home_domain="",
            xlm_balance=xlm,
            horizon_accounts_json=horizon_json or "",
            status="COMPLETE",
            created_at=None,
            updated_at=None,
        )

    @patch("apiApp.helpers.sm_lineage_aggregate.StellarCreatorAccountLineage.objects")
    def test_build_projection_depth3_and_siblings(self, mock_objects):
        root, mid, leaf = "GROOT", "GMID", "GLEAF"
        sib_hi, sib_lo = "GSIBHI", "GSIBLO"
        recs = {
            root: self._rec(root, None, 10000),
            mid: self._rec(mid, root, 5000),
            leaf: self._rec(leaf, mid, 100),
            sib_hi: self._rec(sib_hi, mid, 2000),
            sib_lo: self._rec(sib_lo, mid, 10),
        }

        def filter_side_effect(**kwargs):
            qs = MagicMock()
            if "stellar_account" in kwargs and "stellar_account__in" not in kwargs:
                acct = kwargs["stellar_account"]
                rec = recs.get(acct)

                def first():
                    return rec

                qs.first = first
                qs.limit = lambda n: [rec] if rec else []
                return qs
            if "stellar_creator_account__in" in kwargs:
                creators = set(kwargs["stellar_creator_account__in"])
                children = [
                    r
                    for r in recs.values()
                    if r.stellar_creator_account in creators
                ]
                qs.__iter__ = lambda self: iter(children)
                # list() on MagicMock needs __iter__
                type(qs).__iter__ = lambda self: iter(children)
                return qs
            if "stellar_creator_account" in kwargs:
                creator = kwargs["stellar_creator_account"]
                children = [
                    r for r in recs.values() if r.stellar_creator_account == creator
                ]
                qs.limit = lambda n: children[:n]
                type(qs).__iter__ = lambda self: iter(children)
                return qs
            return qs

        mock_objects.filter.side_effect = filter_side_effect

        # Force SQL path (not Cassandra limit API)
        with patch("apiApp.helpers.sm_lineage_aggregate.USE_CASSANDRA", False):
            svc = LineageAggregateService()
            proj = svc.build_projection(
                leaf,
                "public",
                AggregateOptions(
                    max_depth=50,
                    max_nodes=500,
                    max_siblings_per_level=50,
                    include_siblings=True,
                    use_search_cache=False,
                ),
            )

        self.assertEqual(proj["lineage_path"], [root, mid, leaf])
        self.assertEqual(proj["schema_version"], 1)
        self.assertTrue(proj["meta"]["db_only"])
        self.assertIn(sib_hi, proj["nodes"])
        self.assertIn(sib_lo, proj["nodes"])
        table = svc.to_table_rows(proj)
        self.assertEqual(len(table), 3)
        tree = proj["tree"]
        # Walk to mid's issuer children
        mid_node = next(
            c
            for c in tree["children"]
            if c.get("stellar_account") == mid
        )
        issuer_kids = {
            c["stellar_account"]
            for c in mid_node["children"]
            if c.get("node_type") == "ISSUER"
        }
        self.assertIn(sib_hi, issuer_kids)
        self.assertNotIn(sib_lo, issuer_kids)

    @patch("apiApp.helpers.sm_lineage_aggregate.StellarAccountSearchCache.objects")
    def test_get_projection_legacy_tree_wrap(self, mock_cache_objects):
        tree = {"name": "GONLY", "node_type": "ISSUER", "children": []}
        entry = SimpleNamespace(
            cached_json=json.dumps(tree),
            status="DONE_MAKE_PARENT_LINEAGE",
        )
        mock_cache_objects.filter.return_value.first.return_value = entry
        svc = LineageAggregateService()
        proj = svc.get_projection(
            "GONLY",
            "public",
            AggregateOptions(use_search_cache=True, force_rebuild=False),
        )
        self.assertEqual(proj["source"], "legacy_cache_tree")
        self.assertEqual(proj["tree"]["name"], "GONLY")
        self.assertTrue(proj["meta"].get("legacy_tree"))

    @patch("apiApp.helpers.sm_lineage_aggregate.StellarAccountSearchCache.objects")
    @patch.object(LineageAggregateService, "build_projection")
    def test_invalid_cache_falls_through_to_build(self, mock_build, mock_cache_objects):
        entry = SimpleNamespace(
            cached_json="{'xlm_balance': 1.0}",
            status="DONE_MAKE_PARENT_LINEAGE",
        )
        mock_cache_objects.filter.return_value.first.return_value = entry
        mock_build.return_value = {
            "schema_version": 1,
            "account": "G1",
            "network": "public",
            "lineage_path": ["G1"],
            "nodes": {},
            "tree": {"name": "G1", "children": []},
            "meta": {},
        }
        svc = LineageAggregateService()
        svc.get_projection("G1", "public", AggregateOptions(use_search_cache=True))
        mock_build.assert_called_once()
