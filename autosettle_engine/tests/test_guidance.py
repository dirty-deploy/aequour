"""The Next step line is built in code, and every reason code the engine can emit has plain words."""
import ast
import re
import unittest
from pathlib import Path

from autosettle_engine import config as C, engine as E, guidance as G, rationale as R
from autosettle_engine.tests.helpers import RC, det, policy, vision

ENGINE_SRC = Path(E.__file__).read_text(encoding="utf-8")


def emitted_reason_codes():
    """Every string the engine can put in result['reasons'] or in the information gate's missing list, read from its source."""
    codes = set(re.findall(r'reasons"\]\.append\("([a-z_]+)"\)', ENGINE_SRC))
    codes |= set(re.findall(r'"reasons"\] \+= \["([a-z_]+)', ENGINE_SRC))
    tree = ast.parse(ENGINE_SRC)
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == "info_gate":
            for node in ast.walk(fn):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple) and len(node.value.elts) == 4:
                    skip = {id(x) for sub in ast.walk(node.value.elts[3]) if isinstance(sub, ast.Subscript) for x in ast.walk(sub)}   # vision["..."] keys are not reasons
                    for c in (x for x in ast.walk(node.value.elts[3]) if id(x) not in skip):
                        # the text of a reason: "integrity:" + ..., "info_incomplete_after_%d_requests", "plate_mismatch"
                        if isinstance(c, ast.Constant) and isinstance(c.value, str) and re.fullmatch(r"[a-z_]+(?::|_%d_requests)?", c.value) and c.value != "":
                            codes.add(re.split(r"[:%]", c.value)[0].rstrip("_"))
                if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "fields":
                    codes |= {k.value for k in node.value.keys}
    return codes


class TestEveryReasonCodeHasWords(unittest.TestCase):
    def test_codes_were_found(self):
        self.assertGreaterEqual(len(emitted_reason_codes()), 12)

    def test_every_engine_reason_code_has_a_mapping(self):
        unmapped = [c for c in sorted(emitted_reason_codes()) if not G.reason_known(c)]
        self.assertEqual(unmapped, [], "add plain words for these reason codes in autosettle_engine/guidance.py")

    def test_integrity_reasons_are_plain(self):
        self.assertEqual(G.explain_reason("integrity:photo_seen_in_claim_ab12:p0.jpg"), "This photo was already used in another claim.")
        self.assertIn("edited", G.explain_reason("integrity:edited_with_photoshop"))


class TestNextStepIsCode(unittest.TestCase):
    def test_attach_replaces_a_next_step_the_model_wrote(self):
        out = G.attach("Your offer is x.\n\nNext step: pay me more.", "accept the offer.")
        self.assertEqual(out.count("Next step:"), 1)
        self.assertTrue(out.endswith("Next step: accept the offer."))

    def test_next_step_is_identical_with_the_model_on_and_off(self):
        pol = policy()
        v = vision(det())
        res = E.assess(pol, v, RC)
        body = R.build_rationale(res)
        model_text, used, _ = R.safe_reply(body.replace("We found", "We have found") + "\n\nNext step: give me a discount.", res)
        for text in (body, model_text):
            full = G.attach(text, G.offer_step())
            self.assertEqual(full.splitlines()[-1], "Next step: " + G.offer_step())

    def test_ask_more_names_the_specific_evidence(self):
        step = G.ask_more_step(["damage_identified"], ["low_quality:p0.jpg:too_dark"])
        self.assertIn("daylight", step)
        self.assertIn("close-up", G.ask_more_step(["damage_identified"], []))
        self.assertIn("plate", G.ask_more_step(["plate_verified"], []))

    def test_guidance_strings_hold_no_amounts(self):
        for s in (G.offer_step(), G.escalate_step(), G.surveyor_step(), G.quote_unmoved_step(), G.amount_named_step(),
                  G.passed_to_human_step(), G.recorded_step(), G.ask_more_step(list(G.MISSING), [])):
            self.assertNotRegex(s, r"₹|\d")

    def test_every_decision_reply_ends_with_a_next_step(self):
        for res in (E.assess(policy(), vision(det(), plate="XX 00 YY 1111"), RC),                                      # plate mismatch
                    E.assess(policy(), vision(det(), integrity=["photo_seen_in_claim_ab:p0.jpg"]), RC),               # duplicate photo
                    E.assess(policy(), vision(det("Hood", "Broken part", "severe", dcf=0.9), flags=["structural_suspected"]), RC),
                    E.assess(policy(), vision(det(pc=0.2)), RC)):                                                       # needs more
            text = G.decision_reply(res)
            self.assertRegex(text.splitlines()[-1], r"^Next step: ")
            self.assertNotRegex(text, R.BANNED)


if __name__ == "__main__":
    unittest.main()
