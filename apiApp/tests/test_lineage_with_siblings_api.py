"""
Regression tests for /api/lineage-with-siblings/ (no pytest dependency).

HTTP contract tests mock LineageAggregateService (lab may lack test DB CREATE).
Path/sibling parity covered by real service + mocked ORM in test_sm_lineage_aggregate.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import Client, SimpleTestCase

from apiApp.helpers import sm_lineage_response_cache as resp_cache
from apiApp.helpers.sm_lineage_aggregate import (
    AggregateOptions,
    LineageAggregateService,
    build_tree_from_nodes,
)

# Cryptographically valid public keys
ROOT = "GAS4TDOMWVJSWA4WNU4VYNWG6LQYTQ2DXYWI62UKISMGMJBTPVKUPG76"
CHILD1 = "GCQPYKTMMZ6EQYUZOYO4CXDZMTX45AVOSSF3B7KMEZOVZPCY4FV4VCR4"
CHILD2 = "GCHNWVRNAXQOPA2HWWPIPBPUCW32SJSZ6L23WAIJ6QJQ2JP5R2Z7JQIS"
GRAND1 = "GAAJJ4I6H4TYQCS64PJBRH372UPCAIMRHM4UFWNEBWMVKLNI6ON233X6"
GRAND2 = "GDGK2UK5AKGSSWOQJWY36YV2J572EZNOPMUIF4WASRTWBME575WLUFQR"
UNKNOWN = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"


def _rec(account, creator, xlm=0.0, horizon_json=""):
    return SimpleNamespace(
        stellar_account=account,
        stellar_creator_account=creator or "",
        network_name="public",
        stellar_account_created_at=None,
        home_domain="",
        xlm_balance=xlm,
        horizon_accounts_json=horizon_json or "",
        status="COMPLETE",
        created_at=None,
        updated_at=None,
    )


class LineageWithSiblingsHTTPContractTests(SimpleTestCase):
    def setUp(self):
        resp_cache.clear_all()
        self.client = Client()

    def tearDown(self):
        resp_cache.clear_all()

    def test_missing_account_parameter(self):
        r = self.client.get("/api/lineage-with-siblings/", {"network": "public"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Missing required parameters", r.json()["error"])

    def test_missing_network_parameter(self):
        r = self.client.get("/api/lineage-with-siblings/", {"account": UNKNOWN})
        self.assertEqual(r.status_code, 400)

    def test_invalid_account_address(self):
        r = self.client.get(
            "/api/lineage-with-siblings/",
            {"account": "INVALID_ADDRESS", "network": "public"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("Invalid stellar account address", r.json()["error"])

    def test_invalid_network(self):
        r = self.client.get(
            "/api/lineage-with-siblings/",
            {"account": UNKNOWN, "network": "invalid_network"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("Invalid network", r.json()["error"])

    @patch("apiApp.helpers.sm_lineage_aggregate.LineageAggregateService")
    def test_successful_response_shape(self, mock_cls):
        tree = {
            "name": ROOT,
            "node_type": "ISSUER",
            "stellar_account": ROOT,
            "children": [],
            "is_lineage_path": True,
        }
        payload = {
            "account": GRAND1,
            "network": "public",
            "lineage_path": [ROOT, CHILD1, GRAND1],
            "siblings_by_creator": {
                ROOT: [CHILD2],
                CHILD1: [GRAND2],
            },
            "all_account_data": {
                ROOT: {"stellar_account": ROOT, "in_lineage_path": True, "is_issuer": False},
                CHILD1: {"stellar_account": CHILD1, "in_lineage_path": True, "is_issuer": False},
                CHILD2: {"stellar_account": CHILD2, "in_lineage_path": False, "is_issuer": False},
                GRAND1: {"stellar_account": GRAND1, "in_lineage_path": True, "is_issuer": False},
                GRAND2: {"stellar_account": GRAND2, "in_lineage_path": False, "is_issuer": False},
            },
            "total_accounts": 5,
            "total_siblings": 2,
            "tree": tree,
            "meta": {
                "tree_build": {
                    "algorithm": "buildTreeFromLineage_v1",
                    "xlm_sibling_threshold": 1000,
                }
            },
        }
        svc = MagicMock()
        svc.get_projection.return_value = {"meta": {}}
        svc.to_siblings_response.return_value = payload
        mock_cls.return_value = svc

        with patch(
            "apiApp.helpers.sm_validator.StellarMapValidatorHelpers.validate_stellar_account_address",
            return_value=True,
        ):
            r = self.client.get(
                "/api/lineage-with-siblings/",
                {"account": GRAND1, "network": "public"},
            )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["lineage_path"], [ROOT, CHILD1, GRAND1])
        self.assertIn(CHILD2, data["siblings_by_creator"][ROOT])
        self.assertTrue(data["all_account_data"][GRAND1]["in_lineage_path"])
        self.assertIn("tree", data)
        self.assertIn("meta", data)
        self.assertTrue(data["meta"].get("include_siblings"))


class LineageWithSiblingsServiceParityTests(SimpleTestCase):
    """Real LineageAggregateService with mocked ORM (DB-free)."""

    @patch("apiApp.helpers.sm_lineage_aggregate.StellarCreatorAccountLineage.objects")
    def test_build_path_and_siblings(self, mock_objects):
        recs = {
            ROOT: _rec(ROOT, None, 10000),
            CHILD1: _rec(CHILD1, ROOT, 5000),
            CHILD2: _rec(CHILD2, ROOT, 3000),
            GRAND1: _rec(GRAND1, CHILD1, 1000),
            GRAND2: _rec(GRAND2, CHILD1, 800),
        }

        def filter_side_effect(**kwargs):
            qs = MagicMock()
            if "stellar_account" in kwargs and "stellar_account__in" not in kwargs:
                acct = kwargs["stellar_account"]
                rec = recs.get(acct)
                qs.first = lambda: rec
                qs.limit = lambda n: [rec] if rec else []
                return qs
            if "stellar_creator_account__in" in kwargs:
                creators = set(kwargs["stellar_creator_account__in"])
                children = [r for r in recs.values() if r.stellar_creator_account in creators]
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

        with patch("apiApp.helpers.sm_lineage_aggregate.USE_CASSANDRA", False):
            svc = LineageAggregateService()
            proj = svc.build_projection(
                GRAND1,
                "public",
                AggregateOptions(
                    include_siblings=True,
                    max_siblings_per_level=50,
                    use_search_cache=False,
                ),
            )
            resp = svc.to_siblings_response(proj)

        self.assertEqual(resp["lineage_path"], [ROOT, CHILD1, GRAND1])
        self.assertIn(CHILD2, resp["siblings_by_creator"].get(ROOT, []))
        self.assertIn(GRAND2, resp["siblings_by_creator"].get(CHILD1, []))
        self.assertTrue(resp["all_account_data"][GRAND1]["in_lineage_path"])
        self.assertFalse(resp["all_account_data"][GRAND2]["in_lineage_path"])
        # Tree excludes low-XLM sibling GRAND2 (800 < 1000)
        tree = resp["tree"]
        self.assertEqual(tree.get("stellar_account") or tree.get("name"), ROOT)
