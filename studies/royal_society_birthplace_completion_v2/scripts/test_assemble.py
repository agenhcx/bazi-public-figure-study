import unittest
from assemble import candidate, choose


class EvidenceSelectionTests(unittest.TestCase):
    def make(self, grade, sign, name='place', **kw):
        return candidate('test', name, grade, sign, ['https://example.org/source'], **kw)

    def test_official_field_replaces_conflicting_S3_but_retains_discrepancy(self):
        strong, weak = self.make('S1', 'north'), self.make('S3', 'south')
        selected, status, discrepancy = choose([weak, strong])
        self.assertEqual(selected, strong)
        self.assertTrue(discrepancy)
        self.assertEqual(status, 'higher_tier_birthplace_preferred_with_discrepancy_retained')

    def test_verified_edited_body_can_resolve_known_S3_error(self):
        strong, weak = self.make('S2', 'south'), self.make('S3', 'north')
        self.assertEqual(choose([weak, strong])[0], strong)

    def test_same_tier_opposite_hemispheres_are_held(self):
        selected, status, discrepancy = choose([self.make('S1', 'north'), self.make('S1', 'south')])
        self.assertIsNone(selected)
        self.assertTrue(status.endswith('_hold'))
        self.assertTrue(discrepancy)

    def test_no_geographic_sign_does_not_imply_north(self):
        unresolved = self.make('S1', 'unknown')
        self.assertEqual(choose([unresolved])[0]['hemisphere'], 'unknown')
        self.assertEqual(choose([])[1], 'no_birthplace_evidence')

    def test_ambiguous_strong_source_alternatives_not_overruled_by_weak_point(self):
        unresolved = self.make('S1', 'unknown', geography={
            'reason': 'explicit_alternatives_unresolved_or_cross_hemispheres'})
        self.assertTrue(choose([unresolved, self.make('S3', 'north')])[1].endswith('_hold'))


if __name__ == '__main__':
    unittest.main()
