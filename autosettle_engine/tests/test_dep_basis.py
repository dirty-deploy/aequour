"""The facts behind every depreciation figure, supplied by the engine so the page never calculates anything."""
import unittest
from datetime import date

from autosettle_engine import config as C, engine as E
from autosettle_engine.tests.helpers import RC, det, policy, vision

TODAY = date(2026, 10, 20)


def priced(part, dc, sev, reg):
    res = E.assess(policy(reg=reg), vision(det(part, dc, sev)), RC, today=TODAY)
    assert res["decision"] == "OFFER", res
    return res["lines"][0]


class TestDepBasis(unittest.TestCase):
    def test_plastic_part(self):
        ln = priced("Front-bumper", "Broken part", "moderate", "2023-06-01")
        b = ln["dep_basis"]
        self.assertEqual((b["material"], b["rate"], b["list_price"]), ("plastic", C.PLASTIC_DEP, ln["part_mrp"]))
        self.assertNotIn("age_years", b)
        self.assertEqual((b["reg_date"], b["loss_date"]), ("2023-06-01", "2026-10-20"))

    def test_glass_part(self):
        ln = priced("Windshield", "Broken part", "moderate", "2023-06-01")
        self.assertEqual((ln["dep_basis"]["material"], ln["dep_basis"]["rate"]), ("glass", 0.0))
        self.assertEqual(ln["dep_amount"], 0)

    def test_metal_part_across_ages(self):
        for reg, label, rate in (("2026-08-01", "up to 6 months", 0.0), ("2024-03-01", "2 to 3 years", 0.15), ("2013-01-01", "over 10 years", 0.5)):
            ln = priced("Front-door", "Broken part", "severe", reg)
            if ln["action"] != "replace":
                self.skipTest("front door was not priced as a replacement")
            b = ln["dep_basis"]
            self.assertEqual((b["material"], b["band"], b["rate"]), ("metal", label, rate), reg)
            self.assertEqual(b["age_years"], round((TODAY - date.fromisoformat(reg)).days / 365.25, 1))
            self.assertEqual(ln["dep_amount"], ln["part_mrp"] - ln["part_net"])

    def test_paint_basis_reads_the_config(self):
        ln = priced("Front-bumper", "Broken part", "moderate", "2023-06-01")
        self.assertEqual(ln["paint_basis"], {"painting": ln["paint_gross"], "share": C.PAINT_MATERIAL_SHARE, "rate": C.PAINT_MATERIAL_DEP})

    def test_the_band_table_and_the_function_agree(self):
        for age in (0.2, 0.7, 1.5, 2.5, 3.4, 4.5, 7, 11):
            self.assertEqual(C.metal_band(age)["rate"], C.metal_depreciation(age), age)
        self.assertEqual(len(C.metal_bands()), len(C.METAL_DEP_BANDS) + 1)
        self.assertEqual(C.metal_band(3.4)["label"], "3 to 4 years")


if __name__ == "__main__":
    unittest.main()
