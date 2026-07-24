"""
PR5: progressive / structure-first lineage API + include_siblings param.
"""
from unittest.mock import MagicMock, patch

from django.test import Client, SimpleTestCase, override_settings

from apiApp.helpers import sm_lineage_response_cache as resp_cache


class IncludeSiblingsParamTests(SimpleTestCase):
    def setUp(self):
        resp_cache.clear_all()
        self.client = Client()
        self.account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"

    def tearDown(self):
        resp_cache.clear_all()

    def _mock_projection(self, with_siblings=True):
        path = ["GROOT", self.account]
        nodes = {
            "GROOT": {
                "stellar_account": "GROOT",
                "stellar_creator_account": None,
                "network_name": "public",
                "xlm_balance": 0,
                "assets": [],
                "status": "COMPLETE",
                "is_issuer": False,
                "in_lineage_path": True,
            },
            self.account: {
                "stellar_account": self.account,
                "stellar_creator_account": "GROOT",
                "network_name": "public",
                "xlm_balance": 0,
                "assets": [],
                "status": "COMPLETE",
                "is_issuer": False,
                "in_lineage_path": True,
            },
        }
        sibs = {"GROOT": ["GSIB"]} if with_siblings else {}
        if with_siblings:
            nodes["GSIB"] = {
                "stellar_account": "GSIB",
                "stellar_creator_account": "GROOT",
                "network_name": "public",
                "xlm_balance": 2000,
                "assets": [],
                "status": "COMPLETE",
                "is_issuer": False,
                "in_lineage_path": False,
            }
        return {
            "account": self.account,
            "network": "public",
            "lineage_path": path,
            "nodes": nodes,
            "siblings_by_creator": sibs,
            "tree": {"name": "GROOT", "node_type": "ISSUER", "children": []},
            "meta": {"build_ms": 1, "db_only": True},
            "schema_version": 1,
            "source": "database",
            "tree_build": {
                "algorithm": "buildTreeFromLineage_v1",
                "xlm_sibling_threshold": 1000,
            },
        }

    @override_settings(LINEAGE_API_RESPONSE_CACHE=True)
    def test_structure_only_sets_meta_flags(self):
        proj = self._mock_projection(with_siblings=False)
        with patch(
            "apiApp.helpers.sm_lineage_aggregate.LineageAggregateService"
        ) as mock_cls:
            svc = MagicMock()
            svc.get_projection.return_value = proj
            svc.to_siblings_response.return_value = {
                "account": self.account,
                "network": "public",
                "lineage_path": proj["lineage_path"],
                "siblings_by_creator": {},
                "all_account_data": {},
                "total_accounts": 2,
                "total_siblings": 0,
                "tree": proj["tree"],
                "meta": {"tree_build": proj["tree_build"]},
            }
            mock_cls.return_value = svc
            with patch(
                "apiApp.helpers.sm_validator.StellarMapValidatorHelpers.validate_stellar_account_address",
                return_value=True,
            ):
                r = self.client.get(
                    "/api/lineage-with-siblings/",
                    {
                        "account": self.account,
                        "network": "public",
                        "structure_only": "1",
                    },
                )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["meta"].get("structure_only"))
        self.assertFalse(body["meta"].get("include_siblings"))
        # build was called with include_siblings False
        call_opts = svc.get_projection.call_args[0][2]
        self.assertFalse(call_opts.include_siblings)

    @override_settings(LINEAGE_API_RESPONSE_CACHE=True)
    def test_include_siblings_default_true(self):
        proj = self._mock_projection(with_siblings=True)
        with patch(
            "apiApp.helpers.sm_lineage_aggregate.LineageAggregateService"
        ) as mock_cls:
            svc = MagicMock()
            svc.get_projection.return_value = proj
            svc.to_siblings_response.return_value = {
                "account": self.account,
                "network": "public",
                "lineage_path": proj["lineage_path"],
                "siblings_by_creator": proj["siblings_by_creator"],
                "all_account_data": {},
                "total_accounts": 3,
                "total_siblings": 1,
                "tree": proj["tree"],
                "meta": {},
            }
            mock_cls.return_value = svc
            with patch(
                "apiApp.helpers.sm_validator.StellarMapValidatorHelpers.validate_stellar_account_address",
                return_value=True,
            ):
                r = self.client.get(
                    "/api/lineage-with-siblings/",
                    {"account": self.account, "network": "public"},
                )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["meta"].get("include_siblings"))
        self.assertFalse(body["meta"].get("structure_only"))
        call_opts = svc.get_projection.call_args[0][2]
        self.assertTrue(call_opts.include_siblings)

    def test_separate_cache_keys_for_structure_vs_full(self):
        k1 = resp_cache.cache_key(
            self.account, "public", kind="structure", max_siblings=0, include_siblings=0
        )
        k2 = resp_cache.cache_key(
            self.account, "public", kind="siblings", max_siblings=50, include_siblings=1
        )
        self.assertNotEqual(k1, k2)


class FrontendProgressiveSourceTests(SimpleTestCase):
    def test_search_html_has_progressive_helpers(self):
        from pathlib import Path

        html = (
            Path(__file__).resolve().parents[2]
            / "webApp/templates/webApp/search.html"
        ).read_text()
        self.assertIn("lineage_progressive_siblings", html)
        self.assertIn("fetchLineageApiPayload", html)
        self.assertIn("applyLineageApiPayload", html)
        self.assertIn("structure_only", html)
        self.assertIn("include_siblings", html)
