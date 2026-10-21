import json
import unittest
from pathlib import Path

from autosettle_engine import engine as E
from autosettle_engine.dispute import ClaimSession, check_quote
from autosettle_engine.tests.helpers import RC, det, policy, vision
from autosettle_vision.qwen import parse_quote_json, repair_json

ROOT = Path(__file__).resolve().parents[2]
CLEAN = '{"lines":[{"description":"Front Bumper","type":"part","qty":1,"unit_price":2250,"total":2250},' \
        '{"description":"Labour","type":"labour","qty":1,"unit_price":6000,"total":6000}],"gst_percent":18,"grand_total":8250}'


class TolerantQuoteParser(unittest.TestCase):
    def test_valid_reply_is_unchanged(self):
        q = parse_quote_json(CLEAN)
        self.assertEqual(len(q["lines"]), 2)
        self.assertNotIn("repaired", q)
        self.assertNotIn("parse_error", q)

    def test_missing_closing_bracket_before_next_key(self):
        raw = CLEAN.replace('}],"gst_percent"', '},"gst_percent"')
        q = parse_quote_json(raw)
        self.assertEqual(q["lines"], parse_quote_json(CLEAN)["lines"])
        self.assertEqual((q["gst_percent"], q["grand_total"], q.get("repaired")), (18, 8250, True))

    def test_missing_final_brace_and_code_fence(self):
        q = parse_quote_json("```json\n" + CLEAN[:-1] + "\n```")
        self.assertEqual(q["lines"], parse_quote_json(CLEAN)["lines"])
        q = parse_quote_json(CLEAN[:-1])
        self.assertEqual(q["grand_total"], 8250)

    def test_unrepairable_replies_give_an_empty_quote(self):
        for raw in ('{"lines":[{"description":"Front Bum', "no json here", "", None, '["not", "an", "object"]',
                    '{"lines":[{"description":"Front Bumper","type":"part","unit_price":22'):
            q = parse_quote_json(raw)
            self.assertEqual(q["lines"], [], raw)
            self.assertIn("parse_error", q, raw)
        self.assertIsNone(repair_json('{"a": "unterminated'))

    def test_repair_never_changes_a_value(self):
        raw = CLEAN.replace('}],"gst_percent"', '},"gst_percent"')
        self.assertEqual(json.loads(repair_json(raw)), json.loads(CLEAN))

    def test_rq08_from_run1_cache(self):
        reads = json.loads((ROOT / "run1" / "cache" / "quote_reads.json").read_text(encoding="utf-8"))
        truth = json.loads((ROOT / "run1" / "quotes" / "rq08.json").read_text(encoding="utf-8"))
        q = parse_quote_json(reads["rq08"]["raw"])
        self.assertTrue(q.get("repaired"))
        self.assertEqual([(l["description"], l["type"], l["total"]) for l in q["lines"]],
                         [(l["description"], l["type"], l["total"]) for l in truth["lines"]])
        self.assertEqual(q["grand_total"], truth["grand_total"])

    def test_repaired_quote_gets_exactly_the_checker_result_of_the_clean_quote(self):
        # the repair adds no route to extra money: same verdicts and same updated offer as the clean quote
        reads = json.loads((ROOT / "run1" / "cache" / "quote_reads.json").read_text(encoding="utf-8"))
        truth = json.loads((ROOT / "run1" / "quotes" / "rq08.json").read_text(encoding="utf-8"))
        clean = {k: truth[k] for k in ("lines", "gst_percent", "grand_total")}
        repaired = parse_quote_json(reads["rq08"]["raw"])
        pol, vis = policy(), vision(det("Front-bumper", "Dent", "moderate"))
        res = E.assess(pol, vis, RC)
        self.assertEqual(res["decision"], "OFFER")
        a = check_quote(pol, vis, res, clean, RC)
        b = check_quote(pol, vis, res, repaired, RC)
        self.assertEqual(a["updated_offer"], b["updated_offer"])
        self.assertEqual([(v["description"], v["verdict"]) for v in a["verdicts"]],
                         [(v["description"], v["verdict"]) for v in b["verdicts"]])
        self.assertLessEqual(b["updated_offer"], res["ceiling"])
        s = ClaimSession(pol, RC)
        s.submit(vis)
        s.dispute(repaired)
        self.assertLessEqual(s.current_offer, res["ceiling"])


if __name__ == "__main__":
    unittest.main()
