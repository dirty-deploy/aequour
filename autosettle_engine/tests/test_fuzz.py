"""Seeded fuzz of the engine (TASKS RUN1, Task 1): 5,000 random claims over every model, part, damage class,
severity and confidence band. CPU only, single thread, no models."""
import math
import random
import re
import unittest
from datetime import date

from autosettle_engine import config as C, engine as E, rationale as R
from autosettle_engine.tests.helpers import RC

N_CLAIMS = 5000
SEED = 20261021
MODELS = sorted(C.SEGMENT)
PARTS = sorted(C.PRICED_PARTS | C.REPAIR_ONLY | C.UNPRICEABLE)
DAMAGES = sorted(C.DAMAGE_MAP)
DECISIONS = {"OFFER", "ASK_MORE", "ESCALATE", "SURVEYOR"}
TODAY = date(2026, 10, 21)
NUM_KEYS = ("part_mrp", "dep_amount", "part_net", "labour", "paint_gross", "paint_dep", "paint_net", "line_total")


def rand_claim(rng):
    model = rng.choice(MODELS)
    reg = date(rng.randint(2012, 2026), rng.randint(1, 12), rng.randint(1, 28))
    if reg > TODAY:
        reg = TODAY
    pol = E.Policy("FZ", "DL3CAB1234", "X", model, reg.isoformat(), rng.choice([998, 1197, 1497, 1956]),
                   rng.choice([300000, 600000, 1200000]))
    dets = []
    for _ in range(rng.randint(1, 4)):
        dets.append({"part_class": rng.choice(PARTS), "part_conf": rng.choice([0.3, 0.55, 0.8, 0.95]),
                     "damage_class": rng.choice(DAMAGES), "damage_conf": rng.choice([0.2, 0.35, 0.6, 0.9]),
                     "severity": rng.choice(C.SEVERITIES), "damage_area_fraction": round(rng.random(), 3)})
    vision = {"image_id": "fz", "plate_read": "DL 3C AB 1234", "integrity_flags": [], "flags": [], "detections": dets}
    return pol, vision


def finite(x):
    return x is None or (isinstance(x, (int, float)) and math.isfinite(x))


class EngineFuzz(unittest.TestCase):
    def test_random_claims_keep_every_invariant(self):
        rng = random.Random(SEED)
        stats = {d: 0 for d in DECISIONS}
        for i in range(N_CLAIMS):
            pol, v = rand_claim(rng)
            res = E.assess(pol, v, RC, TODAY)
            ctx = (i, pol.model, v["detections"], res["decision"], res["reasons"])
            self.assertIn(res["decision"], DECISIONS, ctx)
            stats[res["decision"]] += 1
            for k in ("gross", "offer", "ceiling", "deductible", "tci"):
                self.assertTrue(finite(res[k]), (k, ctx))
            for ln in res["lines"] + res["ceiling_lines"]:
                for k in NUM_KEYS:
                    self.assertTrue(finite(ln[k]) and ln[k] >= 0, (k, ln, ctx))
            if res["decision"] != "OFFER":
                self.assertIsNone(res["offer"], ctx)
                continue
            self.assertGreaterEqual(res["offer"], 0, ctx)
            self.assertLessEqual(res["offer"], res["ceiling"], ctx)

            # duplicate detections of one part never pay twice (and order does not matter)
            dup = {**v, "detections": list(reversed(v["detections"])) + [dict(v["detections"][0])]}
            r2 = E.assess(pol, dup, RC, TODAY)
            self.assertEqual((r2["decision"], r2["offer"]), (res["decision"], res["offer"]), ("duplicate", ctx))

            # a more severe call on one detection never lowers the price
            j = rng.randrange(len(v["detections"]))
            d = v["detections"][j]
            if d["severity"] != "severe":
                up = C.SEVERITIES[C.SEVERITIES.index(d["severity"]) + 1]
                worse = {**v, "detections": [*v["detections"][:j], {**d, "severity": up}, *v["detections"][j + 1:]]}
                r3 = E.assess(pol, worse, RC, TODAY)
                if r3["decision"] == "OFFER":
                    self.assertGreaterEqual(r3["gross"], res["gross"], ("severity_up", d, up, ctx))

            # the customer text never states the ceiling (unless that figure is also a legitimate shown amount)
            text = R.build_rationale(res, E.customer_pivots(E.pivots(pol, v, RC, TODAY)))
            shown = {int(a.replace(",", "")) for a in R.RUPEE.findall(text)}
            if res["ceiling"] != res["offer"] and res["ceiling"] not in R.allowed_amounts(res):
                self.assertNotIn(res["ceiling"], shown, ("ceiling_in_text", ctx))
                self.assertNotIn(R.money(res["ceiling"]), text, ("ceiling_in_text", ctx))
        # the fuzz must actually exercise offers, not only refusals
        self.assertGreater(stats["OFFER"], 300, stats)
        print(f"\nfuzz decisions over {N_CLAIMS} claims: {stats}")


if __name__ == "__main__":
    unittest.main()
