"""The adjuster estimate: it agrees with the engine, changes nothing, and never reaches a customer route or the language model.
No GPU: recorded replay data and a fake vision backend."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from autosettle_api import chat as CHAT
from autosettle_api.app import Settings, create_app
from autosettle_api.tests.test_api import FakeVision, all_keys, jpeg, replay_client
from autosettle_engine.estimate import estimate_from_evidence
from autosettle_vision.claim import POLICIES, RC, get_policy

HIDDEN_KEYS = {"estimate", "gross_low", "gross_high", "payable_high", "ceiling"}
INTENTS = ("greeting_or_meta", "how_calculated", "depreciation", "what_next", "why_not_more", "payout_timing", "other")


class NoSeverityVision(FakeVision):
    """The recorded Swift output with the severity of one detection removed, so the engine must ask for more."""
    def run(self, paths, claim_id):
        v = super().run(paths, claim_id)
        v["detections"][0]["severity"] = None
        return v


def crafted_client():
    app = create_app(Settings(runtime=Path(tempfile.mkdtemp()), qwen=False), vision=NoSeverityVision())
    return TestClient(app), app


def crafted_claim(c):
    cid = c.post("/claims", json={"policy_id": "POL-DEMO-001", "plate_text": "DL3CAB1234"}).json()["claim_id"]
    c.post(f"/claims/{cid}/photos", files=[("files", ("a.jpg", jpeg(), "image/jpeg"))])
    return cid, c.post(f"/claims/{cid}/assess").json()


def customer_texts(c, cid):
    return [c.get(f"/claims/{cid}").text, c.get(f"/claims/{cid}/transcript").text, c.get(f"/claims/{cid}/audit").text,
            json.dumps(c.post(f"/claims/{cid}/message", json={"text": "how was this calculated?"}).json())]


def digits(n):
    return [str(n), f"{n:,}"]


class TestEstimateMatchesEngine(unittest.TestCase):
    def test_offer_estimate_agrees_with_the_engine(self):
        c, app = replay_client()
        cid = c.post("/claims", json={"scenario": "offer"}).json()["claim_id"]
        res = app.state.claims[cid].session.result
        e = c.get(f"/adjuster/{cid}/estimate").json()
        self.assertTrue(e["applies"] and e["complete"])
        self.assertEqual(e["decision"], "OFFER")
        self.assertEqual(e["gross_low"], res["gross"])
        self.assertEqual(e["payable_low"], res["offer"])
        self.assertGreaterEqual(e["payable_high"], e["payable_low"])
        self.assertEqual(e["payable_high"], res["ceiling"])
        self.assertIn("DEMO ONLY", e["label"])
        self.assertIn("not an offer", e["reading"])
        self.assertEqual(c.get(f"/adjuster/{cid}").json()["estimate"], {k: v for k, v in e.items() if k not in ("label", "claim_id", "mode")})

    def test_every_recorded_scenario_with_detections_has_an_estimate(self):
        c, app = replay_client()
        for s in c.get("/scenarios").json():
            cid = c.post("/claims", json={"scenario": s["id"]}).json()["claim_id"]
            e = c.get(f"/adjuster/{cid}/estimate").json()
            self.assertEqual(e["applies"], bool(app.state.claims[cid].ev["detections"]), s["id"])
            if e["applies"]:
                self.assertEqual(e["decision"], app.state.claims[cid].session.result["decision"])
                self.assertTrue(e["lines"] or e["not_priced"])


class TestIncompleteEstimates(unittest.TestCase):
    def test_surveyor_claim_still_gets_an_estimate_and_changes_nothing(self):
        c, app = replay_client()
        cid = c.post("/claims", json={"scenario": "surveyor"}).json()["claim_id"]
        s = app.state.claims[cid].session
        before = (copy.deepcopy(s.result), s.current_offer, s.state, len(s.log), s.last_hash)
        e1 = c.get(f"/adjuster/{cid}/estimate").json()
        e2 = c.get(f"/adjuster/{cid}/estimate").json()
        self.assertEqual(e1, e2)
        self.assertEqual(e1["decision"], "SURVEYOR")
        self.assertTrue(e1["applies"] and e1["gross_low"] > 0 and e1["payable_high"] >= e1["payable_low"])
        self.assertEqual(before, (s.result, s.current_offer, s.state, len(s.log), s.last_hash))
        self.assertIsNone(s.result["gross"])                     # the engine itself priced nothing

    def test_ask_more_claim_lists_the_unpriced_detection_with_its_reason(self):
        c, app = crafted_client()
        cid, v = crafted_claim(c)
        self.assertEqual(v["decision"], "ASK_MORE")
        s = app.state.claims[cid].session
        before = (copy.deepcopy(s.result), s.current_offer, s.state, len(s.log), s.last_hash, copy.deepcopy(app.state.claims[cid].ev))
        e1 = c.get(f"/adjuster/{cid}/estimate").json()
        e2 = c.get(f"/adjuster/{cid}/estimate").json()
        self.assertEqual(e1, e2)
        self.assertTrue(e1["applies"])
        self.assertFalse(e1["complete"])
        self.assertEqual(e1["decision"], "ASK_MORE")
        self.assertTrue(any("severity not determined" in n["reason"] for n in e1["not_priced"]), e1["not_priced"])
        self.assertIn("floor on what is visible", e1["reading"])
        self.assertIn("not an offer", e1["reading"])
        self.assertEqual(before, (s.result, s.current_offer, s.state, len(s.log), s.last_hash, app.state.claims[cid].ev))
        self.assertIsNone(s.result["offer"])

    def test_the_estimate_route_adds_no_audit_event(self):
        c, app = crafted_client()
        cid, _ = crafted_claim(c)
        n = len(app.state.claims[cid].session.log)
        for path in (f"/adjuster/{cid}/estimate", f"/adjuster/{cid}"):
            c.get(path)
        self.assertEqual(len(app.state.claims[cid].session.log), n)
        self.assertTrue(c.get(f"/claims/{cid}/audit").json()["chain_ok"])


class TestNeverRaises(unittest.TestCase):
    def setUp(self):
        self.p = get_policy("POL-DEMO-001") if callable(get_policy) else POLICIES["POL-DEMO-001"]

    def det(self, **kw):
        return {**{"part_class": "Front-bumper", "part_conf": 0.9, "damage_class": "Dent", "damage_conf": 0.9, "severity": "moderate", "damage_area_fraction": 0.1}, **kw}

    def test_unassigned_unknown_damage_and_empty(self):
        e = estimate_from_evidence(self.p, {"detections": [self.det(part_class="unassigned"), self.det(damage_class="Weird", part_class="Hood"),
                                                           self.det(part_class=None)]}, RC)
        self.assertTrue(e["applies"] and not e["complete"])
        self.assertEqual(len(e["not_priced"]), 3)
        self.assertEqual((e["gross_low"], e["gross_high"], e["payable_low"], e["payable_high"]), (0, 0, 0, 0))
        e = estimate_from_evidence(self.p, {"detections": []}, RC)
        self.assertFalse(e["applies"])
        self.assertFalse(estimate_from_evidence(self.p, None, RC)["applies"])

    def test_does_not_mutate_its_inputs(self):
        v = {"detections": [self.det(), self.det(part_class="unassigned")]}
        rows = copy.deepcopy(RC.rows)
        before = copy.deepcopy(v)
        estimate_from_evidence(self.p, v, RC)
        self.assertEqual(v, before)
        self.assertEqual(RC.rows, rows)

    def test_a_price_calculation_that_fails_is_reported_not_raised(self):
        e = estimate_from_evidence(self.p, {"detections": [self.det(part_class="Not-a-part")]}, RC)
        self.assertTrue(e["applies"])
        self.assertEqual(len(e["lines"]) + len(e["not_priced"]), 1)

    def test_route_answers_when_there_is_no_vision_yet(self):
        c, app = replay_client()
        cid = c.post("/claims", json={"policy_id": "POL-DEMO-001"}).json()["claim_id"]
        e = c.get(f"/adjuster/{cid}/estimate")
        self.assertEqual(e.status_code, 200)
        self.assertFalse(e.json()["applies"])
        self.assertIn("note", e.json())


class TestPrivacy(unittest.TestCase):
    def check_claim(self, c, app, cid):
        e = c.get(f"/adjuster/{cid}/estimate").json()
        res = app.state.claims[cid].session.result
        legit = set()
        for k in ("offer", "gross", "deductible"):
            if res.get(k) is not None:
                legit.add(res[k])
        for t in customer_texts(c, cid):
            self.assertFalse(all_keys(json.loads(t)) & HIDDEN_KEYS, t[:80])
            for n in (e.get("payable_high"), e.get("gross_high")):
                if n and n not in legit:
                    for d in digits(n):
                        self.assertNotIn(d, t)

    def test_no_customer_route_carries_the_estimate(self):
        c, app = replay_client()
        for sc in ("offer", "surveyor", "street", "counter"):
            resp = c.post("/claims", json={"scenario": sc}).json()
            self.assertFalse(all_keys(resp) & HIDDEN_KEYS, sc)
            self.check_claim(c, app, resp["claim_id"])
        c2, app2 = crafted_client()
        cid, v = crafted_claim(c2)
        self.assertFalse(all_keys(v) & HIDDEN_KEYS)
        self.check_claim(c2, app2, cid)

    def test_scenario_listing_carries_none_of_it(self):
        c, _ = replay_client()
        self.assertFalse(all_keys(c.get("/scenarios").json()) & HIDDEN_KEYS)

    def test_language_model_facts_carry_none_of_it(self):
        c, app = replay_client()
        for sc in ("offer", "surveyor", "counter"):
            cid = c.post("/claims", json={"scenario": sc}).json()["claim_id"]
            e = c.get(f"/adjuster/{cid}/estimate").json()
            claim = app.state.claims[cid]
            for intent in INTENTS:
                facts = CHAT.build_facts(claim, intent)
                self.assertFalse(all_keys(facts) & HIDDEN_KEYS, (sc, intent))
                text = json.dumps(facts, ensure_ascii=False)
                self.assertNotIn("estimate", text.lower())
                if claim.session.result["decision"] == "OFFER":
                    for n in (e["payable_high"], e["gross_high"]):
                        for d in digits(n):
                            self.assertNotIn(d, text.replace("₹", ""))


if __name__ == "__main__":
    unittest.main()
