"""Every kind of reply the API gives is short, ends with a Next step, and shows only figures the engine produced."""
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from autosettle_api.app import Settings, create_app
from autosettle_engine import rationale as R

AMOUNT = re.compile(r"₹([0-9][0-9,]*)")


def client():
    return TestClient(create_app(Settings(replay=True, runtime=Path(tempfile.mkdtemp()), qwen=False)))


def figures(c, cid):
    """Every amount the engine produced for this claim: offers, totals and each line component."""
    v = c.get(f"/claims/{cid}").json()
    ok = {x for x in (v["offer"], v["updated_offer"], v["original_offer"], v["gross"], v["deductible"]) if x is not None}
    for ln in v["lines"]:
        ok |= {x for x in ln.values() if isinstance(x, int)}
    return ok


def turns(c, cid):
    return c.get(f"/claims/{cid}/transcript").json()["turns"]


def sentences(text):
    return [s for s in re.split(r"[.!?\n]+", text) if s.strip()]


class TestReplyShape(unittest.TestCase):
    def check(self, c, cid, itemised_first=False):
        ceiling = c.get(f"/adjuster/{cid}/range").json().get("ceiling")
        ok = None
        for t in turns(c, cid):
            if t["from"] != "system":
                continue
            text = t["text"]
            ok = figures(c, cid)
            self.assertRegex(text.splitlines()[-1], r"^Next step: ", text)
            self.assertEqual(text.count("Next step:"), 1, text)
            self.assertIsNone(R.BANNED.search(text), text)
            for a in AMOUNT.findall(text):
                self.assertIn(int(a.replace(",", "")), ok, f"{a} in: {text}")
                if ceiling:
                    self.assertNotEqual(int(a.replace(",", "")), ceiling)
            if not (itemised_first and t["n"] == 1 and "- " in text):          # an itemised offer is a list, so it is exempt
                self.assertLessEqual(len(text.split()), 70, text)
                for s in sentences(text):
                    self.assertLessEqual(len(s.split()), 20, s)

    def test_offer_is_itemised_and_ends_with_a_next_step(self):
        c = client()
        v = c.post("/claims", json={"scenario": "offer", "silent": True}).json()
        self.assertTrue(v["message"].startswith("Your offer is ₹2,763."))
        self.assertIn("depreciation", v["message"])
        self.assertEqual(v["next_step"], v["message"].split("Next step: ")[-1])
        self.check(c, v["claim_id"], itemised_first=True)

    def test_surveyor_and_ask_more_replies(self):
        c = client()
        for sc in ("surveyor", "street"):
            v = c.post("/claims", json={"scenario": sc}).json()
            self.assertRegex(v["message"].splitlines()[-1], r"^Next step: ")
            self.check(c, v["claim_id"])

    def test_the_scripted_counter_claim_every_turn(self):
        c = client()
        v = c.post("/claims", json={"scenario": "counter"}).json()
        texts = [t["text"] for t in turns(c, v["claim_id"]) if t["from"] == "system"]
        self.assertGreaterEqual(len(texts), 6)
        self.check(c, v["claim_id"], itemised_first=True)
        self.assertTrue(any("your garage's quote helped" in t for t in texts))
        self.assertTrue(any("the offer stays at" in t for t in texts))

    def test_messages_and_choices(self):
        c = client()
        for text, needle in (("thanks", "recorded your message"), ("Please pay ₹9,000", "I can't change the amount"),
                             ("this is a scam, I will sue you in court", "claims specialist")):
            v = c.post("/claims", json={"scenario": "offer", "silent": True}).json()
            r = c.post(f"/claims/{v['claim_id']}/message", json={"text": text}).json()
            self.assertIn(needle, r["reply"])
            self.assertRegex(r["reply"].splitlines()[-1], r"^Next step: ")
            self.check(c, v["claim_id"], itemised_first=True)
        for opt in ("accept", "partner_garage", "surveyor"):
            v = c.post("/claims", json={"scenario": "offer", "silent": True}).json()
            c.post(f"/claims/{v['claim_id']}/choose", json={"option": opt})
            self.check(c, v["claim_id"], itemised_first=True)

    def test_the_offer_card_shows_the_same_next_step_as_the_chat(self):
        c = client()
        v = c.post("/claims", json={"scenario": "offer", "silent": True}).json()
        r = c.post(f"/claims/{v['claim_id']}/message", json={"text": "thanks"}).json()
        self.assertEqual(r["next_step"], r["reply"].split("Next step: ")[-1])

    def test_a_priced_claim_returns_the_facts_behind_depreciation(self):
        c = client()
        v = c.post("/claims", json={"scenario": "offer", "silent": True}).json()
        ln = v["lines"][0]
        self.assertEqual(ln["dep_basis"]["material"], "plastic")
        self.assertEqual(ln["dep_basis"]["list_price"], ln["part_mrp"])
        self.assertEqual(ln["paint_basis"]["painting"], ln["paint_gross"])
        rules = v["dep_rules"]
        self.assertEqual(rules["metal_bands"][4], {"label": "3 to 4 years", "rate": 0.25})
        self.assertNotIn("ceiling", str(v).lower())


if __name__ == "__main__":
    unittest.main()
