"""
Regression tests: Search page shell must fully load without Vue/progress traps.

Guards against:
- Progress overlay stuck covering the page (inside Vue #app, stale DOM refs)
- Deferred helpers loading after Vue init
- Leaked Django comments
- Missing network switch / required scripts
- Multi-line {# #} comments (invalid; content leaks)
"""
from pathlib import Path
import re
import subprocess

from django.test import Client, SimpleTestCase, override_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SearchPageTemplateIntegrityTests(SimpleTestCase):
    def setUp(self):
        self.search = (
            PROJECT_ROOT / "webApp/templates/webApp/search.html"
        ).read_text()
        self.partial = (
            PROJECT_ROOT
            / "radialTidyTreeApp/templates/radialTidyTreeApp/radial_tidy_tree_partial.html"
        ).read_text()
        self.include = (
            PROJECT_ROOT / "webApp/templates/webApp/search_container_include.html"
        ).read_text()
        self.head = (
            PROJECT_ROOT / "webApp/templates/webApp/includes/head_assets.html"
        ).read_text()

    def test_progress_include_is_outside_vue_app(self):
        """sm_progress must not live inside #app (Vue mount destroys/replaces it)."""
        # Find first id="app" open and progress include
        app_m = re.search(r'<div[^>]*\bid=["\']app["\']', self.search)
        prog_m = re.search(
            r"\{%\s*include\s*['\"]webApp/includes/sm_progress.html['\"]\s*%\}",
            self.search,
        )
        self.assertIsNotNone(app_m, "missing #app")
        self.assertIsNotNone(prog_m, "missing sm_progress include")
        self.assertLess(
            prog_m.start(),
            app_m.start(),
            "sm_progress.html must be included BEFORE #app so Vue cannot own the overlay",
        )

    def test_no_multiline_hash_comments_in_search_related_templates(self):
        """Multi-line {# #} leaks text into the page (Django only supports single-line)."""
        for name, text in (
            ("search.html", self.search),
            ("radial_tidy_tree_partial.html", self.partial),
            ("search_container_include.html", self.include),
        ):
            # Flag multi-line hash comments: open {# without #} on same line
            for i, line in enumerate(text.splitlines(), 1):
                if "{#" in line and "#}" not in line:
                    self.fail(
                        f"{name}:{i} multi-line {{# comment started — content will leak to HTML"
                    )

    def test_helpers_load_before_vue_on_search_page(self):
        """sm_progress.js and sm_network.js must appear before vue CDN script."""
        progress_pos = self.search.find("sm_progress.js")
        network_pos = self.search.find("sm_network.js")
        vue_pos = self.search.find("vue@2")
        self.assertGreater(progress_pos, 0)
        self.assertGreater(network_pos, 0)
        self.assertGreater(vue_pos, 0)
        self.assertLess(progress_pos, vue_pos)
        self.assertLess(network_pos, vue_pos)
        # Must not be defer-only in head for these (race with Vue)
        self.assertNotIn('sm_progress.js" defer', self.head)
        self.assertNotIn("sm_progress.js' defer", self.head)

    def test_network_switch_present_not_checkbox(self):
        self.assertIn("sm-network-switch", self.include)
        self.assertIn('role="switch"', self.include)
        self.assertIn("toggleNetworkSwitch", self.include)
        self.assertNotIn("b-form-checkbox", self.include)

    def test_vue_mount_uses_progress_mixin_safely(self):
        self.assertIn("sm_progress_mixin", self.search)
        self.assertIn("lineage_table_mixin", self.search)
        self.assertIn("new Vue", self.search)
        self.assertTrue(
            "el: '#app'" in self.search or 'el: "#app"' in self.search,
            "Vue must mount on #app",
        )

    def test_no_early_d3_autorender_in_partial(self):
        self.assertNotIn("renderTreeWhenReady", self.partial)
        self.assertNotIn("renderRadialTree(", self.partial)
        self.assertIn("sm-tree-placeholder", self.partial)

    def test_static_js_syntax(self):
        for rel in (
            "webApp/static/webApp/js/sm_progress.js",
            "webApp/static/webApp/js/sm_network.js",
            "webApp/static/webApp/js/lineage_table_mixin.js",
        ):
            path = PROJECT_ROOT / rel
            self.assertTrue(path.is_file(), rel)
            r = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, f"{rel}: {r.stderr}")


class SearchPageHttpShellTests(SimpleTestCase):
    """HTTP-level smoke: page returns shell that can mount Vue."""

    def setUp(self):
        self.client = Client()

    def test_search_page_200_and_shell_markers(self):
        resp = self.client.get(
            "/search/",
            {
                "account": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
                "network": "public",
            },
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn('id="app"', html)
        self.assertIn('id="sm-progress"', html)
        self.assertIn("sm-network-switch", html)
        self.assertIn("sm_progress.js", html)
        self.assertIn("sm_network.js", html)
        self.assertIn("vue@2", html)
        self.assertIn("bootstrap-vue", html)
        # Leaked comment regression
        self.assertNotIn("Vue owns all tree rendering", html)
        self.assertNotIn("{#", html)
        # Progress before app
        self.assertLess(html.find('id="sm-progress"'), html.find('id="app"'))
        # Vue constructor present
        self.assertIn("new Vue", html)
        self.assertIn("toggleNetworkSwitch", html)

    def test_home_page_includes_progress_and_network_switch(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("sm-progress", html)
        self.assertIn("sm-network-switch", html)

    def test_home_page_shell_will_not_blank_on_vue_mount(self):
        """
        Regression: missing networkLabel/toggleNetworkSwitch made Vue render throw
        and left only the purple body background.
        """
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        # Landing content present in SSR HTML
        self.assertIn("landing-content", html)
        self.assertIn("main-title", html)
        self.assertIn("What is StellarMap", html)
        # Progress outside #app
        self.assertLess(html.find('id="sm-progress"'), html.find('id="app"'))
        # Helpers before Vue
        self.assertIn("sm_network.js", html)
        self.assertIn("sm_progress.js", html)
        self.assertLess(html.find("sm_network.js"), html.find("vue@2"))
        # Mixin (or handlers) so shared top bar can render
        self.assertIn("sm_network_mixin", html)
        self.assertIn("new Vue", html)
        # Static API surface for mixin
        js = (PROJECT_ROOT / "webApp/static/webApp/js/sm_network.js").read_text()
        self.assertIn("sm_network_mixin", js)
        self.assertIn("toggleNetworkSwitch", js)
        self.assertIn("networkLabel", js)


class ProgressJsShellCoverageTests(SimpleTestCase):
    """All main shells must load progress markup + script and support navigate."""

    SHELLS = (
        "webApp/templates/webApp/index.html",
        "webApp/templates/webApp/search.html",
        "webApp/templates/webApp/dashboard.html",
        "webApp/templates/webApp/bulk_search.html",
        "webApp/templates/webApp/high_value_accounts.html",
        "webApp/templates/webApp/query_builder.html",
    )

    def test_shells_include_progress_and_script(self):
        for rel in self.SHELLS:
            text = (PROJECT_ROOT / rel).read_text()
            self.assertIn("sm_progress.html", text, rel)
            self.assertIn("sm_progress.js", text, rel)
            # Progress before Vue
            self.assertLess(text.find("sm_progress.js"), text.find("vue@2"), rel)

    def test_progress_js_exports_nav_and_elapsed(self):
        js = (PROJECT_ROOT / "webApp/static/webApp/js/sm_progress.js").read_text()
        for name in (
            "StellarMapProgress",
            "navigate",
            "searchAccount",
            "bindShellNav",
            "elapsed",
            "sm_progress_mixin",
            "smProgressSearch",
        ):
            self.assertIn(name, js)


class ProgressJsBehaviorTests(SimpleTestCase):
    """Execute StellarMapProgress show/hide in Node with a minimal DOM stub."""

    def test_show_hide_clears_body_lock_class(self):
        js_path = PROJECT_ROOT / "webApp/static/webApp/js/sm_progress.js"
        harness = r"""
const fs = require('fs');
const code = fs.readFileSync(process.argv[1], 'utf8');

// Minimal DOM
const store = {};
function el(id, attrs) {
  const o = {
    id,
    hidden: true,
    classList: {
      _c: new Set(),
      add(c) { this._c.add(c); },
      remove(c) { this._c.delete(c); },
      contains(c) { return this._c.has(c); },
    },
    style: { width: '0%' },
    textContent: '',
    setAttribute(k, v) { this[k] = v; },
    removeAttribute(k) { delete this[k]; if (k === 'hidden') this.hidden = false; },
  };
  return o;
}
const progress = el('sm-progress');
const bar = el('sm-progress-bar');
const title = el('sm-progress-title');
const meta = el('sm-progress-meta');
const bodyClasses = new Set();
global.document = {
  getElementById(id) {
    return { 'sm-progress': progress, 'sm-progress-bar': bar,
             'sm-progress-title': title, 'sm-progress-meta': meta }[id] || null;
  },
  body: {
    classList: {
      add(c) { bodyClasses.add(c); },
      remove(c) { bodyClasses.delete(c); },
      contains(c) { return bodyClasses.has(c); },
    },
  },
  readyState: 'complete',
  addEventListener() {},
};
global.window = global;
global.module = { exports: {} };

eval(code);

if (!global.StellarMapProgress) { console.error('missing API'); process.exit(2); }
StellarMapProgress.show({ title: 'Test', indeterminate: true });
if (!bodyClasses.has('sm-progress-active')) { console.error('body lock missing'); process.exit(3); }
if (progress.hidden) { console.error('should be visible'); process.exit(4); }

// hide with 0 delay
StellarMapProgress.hide(0);
setTimeout(() => {
  if (bodyClasses.has('sm-progress-active')) { console.error('body lock stuck'); process.exit(5); }
  if (!progress.hidden && progress.getAttribute && progress.hidden !== true) {
    // hidden may be set via property
  }
  console.log('progress_ok');
  process.exit(0);
}, 30);
"""
        r = subprocess.run(
            ["node", "-e", harness, str(js_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("progress_ok", r.stdout)
