import unittest

from assemble import merge, supplement_hemisphere


def base(hemisphere="unknown"):
    return {"cohort": "test", "record_id": "one", "name": "Person",
            "dob": "1950-01-01", "hemisphere": hemisphere, "dob_status": "native_hold",
            "raw_birthplace": "old place", "birthplace_source_grade": "S1"}


def supplement(sign="north"):
    return {"dob": "1950-01-01", "hemisphere": sign, "qid": "Q1",
            "raw_birthplace": "new place", "reason": "direct_coordinate",
            "lat": 20, "lon": 10}


def place(qid, latitudes, broad=False):
    return {"qid": qid, "instance_of_claims": [{"qid": "Q6256"}] if broad else [],
            "coordinates": [{"lat": lat, "lon": 10, "precision": 0.001}
                            for lat in latitudes]}


class MergeTests(unittest.TestCase):
    def test_opposite_hemispheres_are_held_without_changing_native_dates(self):
        result = merge(base("north"), supplement("south"))
        self.assertEqual(result["hemisphere"], "unknown")
        self.assertTrue(result["geographic_conflict_pending_review"])
        self.assertEqual(result["dob"], "1950-01-01")
        self.assertEqual(result["dob_status"], "native_hold")
        self.assertFalse(result["final_analysis_eligibility_assigned"])

    def test_geography_S3_does_not_regrade_DOB(self):
        result = merge(base(), supplement())
        self.assertEqual(result["birthplace_source_grade"], "S3")
        self.assertEqual(result["dob_status"], "native_hold")
        self.assertTrue(result["northern_birthplace_candidate"])

    def test_different_DOB_cannot_be_silently_joined(self):
        other = supplement()
        other["dob"] = "1950-01-02"
        with self.assertRaises(ValueError):
            merge(base(), other)

    def test_two_northern_cities_only_resolve_hemisphere(self):
        other = supplement("unknown")
        other.update(reason="multiple_distinct_birthplace_P19_conflict",
                     place_evidence=[place("Q10", [40, 40.01]), place("Q20", [41])])
        result = merge(base(), other)
        self.assertEqual(result["hemisphere"], "north")
        self.assertTrue(result["place_alternatives_retained"])
        self.assertIsNone(result["lat"])
        self.assertIsNone(result["lon"])

    def test_broad_country_mixed_sign_and_missing_place_remain_unknown(self):
        for evidence in ([place("Q10", [40], broad=True)],
                         [place("Q10", [40]), place("Q20", [-40])],
                         [place("Q10", [40]), place("Q20", [])]):
            with self.subTest(evidence=evidence):
                other = supplement("unknown")
                other.update(reason="multiple_distinct_birthplace_P19_conflict", place_evidence=evidence)
                self.assertEqual(supplement_hemisphere(other)[0], "unknown")

    def test_unknown_and_CAS_unadjudicated_DOB_stay_unadjudicated(self):
        original = base()
        original.update(dob="", accepted_gregorian_dob="", dob_status="not_adjudicated")
        result = merge(original, None)
        self.assertEqual(result["hemisphere"], "unknown")
        self.assertEqual(result["accepted_gregorian_dob"], "")
        self.assertEqual(result["dob"], "")

    def test_known_north_is_held_if_supplement_has_both_hemispheres(self):
        other = supplement("unknown")
        other.update(reason="multiple_distinct_birthplace_P19_conflict",
                     place_evidence=[place("Q10", [40]), place("Q20", [-40])])
        result = merge(base("north"), other)
        self.assertEqual(result["hemisphere"], "unknown")
        self.assertTrue(result["geographic_conflict_pending_review"])


if __name__ == "__main__":
    unittest.main()
