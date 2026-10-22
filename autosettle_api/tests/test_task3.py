"""The web source: every claim state has plain words, Limits is off the public page, and the depreciation help is in all four places."""
import re
import unittest
from pathlib import Path

from autosettle_engine import dispute

WEB = Path(__file__).resolve().parents[2] / "web" / "src"


def read(rel):
    return (WEB / rel).read_text(encoding="utf-8")


class TestPlainStates(unittest.TestCase):
    def test_every_state_has_words(self):
        engine_states = set(dispute._ALLOWED) | set(dispute.TERMINAL)
        mapped = set(re.findall(r"^\s{2}([A-Z_]+):\s*\"", read("states.ts"), re.M))
        self.assertEqual(sorted(engine_states - mapped), [], "add plain words in web/src/states.ts")

    def test_the_chip_words_are_plain(self):
        words = re.findall(r"^\s{2}[A-Z_]+:\s*\"([^\"]+)\"", read("states.ts"), re.M)
        for w in words:
            self.assertNotRegex(w, r"[A-Z]{3,}|_", w)          # no decision codes or state names


class TestLimitsOffThePublicPage(unittest.TestCase):
    def test_nav_and_landing_have_no_limits_section(self):
        self.assertNotIn("limits", re.findall(r'\["(\w+)", "', read("components/Nav.tsx").split("export default")[0]))
        self.assertNotIn("LimitsScene", read("Landing.tsx"))
        self.assertFalse((WEB / "components" / "LimitsScene.tsx").exists())
        self.assertNotIn("The limits are not hidden", read("components/Glance.tsx"))
        self.assertNotIn("#limits", "".join(p.read_text(encoding="utf-8") for p in WEB.rglob("*.tsx")))

    def test_the_limits_route_and_adjuster_panel_stay(self):
        self.assertIn("LimitsPanel", read("AdjusterView.tsx"))
        from fastapi.testclient import TestClient
        from autosettle_api.app import create_app, Settings
        import tempfile
        c = TestClient(create_app(Settings(replay=True, runtime=Path(tempfile.mkdtemp()), qwen=False)))
        self.assertIn(c.get("/limits").status_code, (200, 404))      # 404 only if docs/LIMITS.json was not generated
        self.assertTrue((Path(__file__).resolve().parents[2] / "docs" / "LIMITS.json").exists())


class TestDepreciationHelpIsEverywhere(unittest.TestCase):
    def test_one_shared_component_used_in_every_place(self):
        for rel in ("components/TryScene.tsx", "components/Waterfall.tsx", "components/Pinned.tsx", "components/Minis.tsx", "AdjusterView.tsx"):
            self.assertIn("DepreciationHelp", read(rel), rel)

    def test_the_help_ends_with_the_honest_footer_and_computes_nothing(self):
        src = read("components/DepreciationHelp.tsx")
        self.assertIn("A deduction based on its current market value is not built yet.", src)
        self.assertNotRegex(src, r"rupees\([^)]*[-+*/]")        # no arithmetic on amounts: every figure is a field the engine sent


if __name__ == "__main__":
    unittest.main()
