import tempfile
from pathlib import Path
import unittest
import zipfile

from collect_historical import extract_history, normalized_name, read_archive


def pre(group, name, month, fid, dob, rating):
    return ';'.join(['', group, name, month, str(fid), dob, '', 'AAA', str(rating), '', '', '', '', '', ''])


def modern(name, month, fid, dob, rating):
    return ';'.join([name, month, str(fid), dob, '', 'AAA', str(rating), '', '', '', ''])


class HistoricalTest(unittest.TestCase):
    def run_fixture(self, early, later, people):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'early.zip', Path(tmp)/'later.zip'
            with zipfile.ZipFile(a, 'w') as z:
                z.writestr('all.csv', '\n'.join(early).encode('latin-1'))
            with zipfile.ZipFile(b, 'w') as z:
                z.writestr('2002.txt', '\n'.join(later).encode('latin-1'))
                z.writestr('2003.txt', b'')
            return extract_history({'pre2002': a, '2002_2009': b}, people, verify_hash=False)

    @staticmethod
    def person(fid, name='Alpha, Anton', dob='1950-01-01'):
        return {'canonical_id':str(fid), 'name':name, 'exact_dob_frozen':dob}

    def test_old_id_reuse_does_not_join_wrong_person(self):
        r=self.run_fixture([
            pre('Wrong, X','Wrong, X','199001',101,'1955.02.03',2800),
            pre('Alpha, Anton','Alpha, Anton','199001',101,'1950.01.01',2400)],[],[self.person(101)])
        self.assertEqual([x['rating'] for x in r['records']],[2400])
        self.assertEqual(r['audit']['fatal_issues'],[])
        self.assertEqual(len(r['audit']['rejected_identity_candidates']),1)

    def test_canonical_group_preserves_old_id_history_and_excludes_unofficial(self):
        r=self.run_fixture([
            pre('Alpha, Anton','Older, Anton','197101',10,'1950.01.01',2900),
            pre('Alpha, Anton','Older, Anton','197107',10,'1950.01.01',2500),
            pre('Alpha, Anton','Alpha, Anton','200101',101,'1950.01.01',2400)],[],[self.person(101)])
        self.assertEqual([x['period'] for x in r['records']],['1971-07','2001-01'])
        self.assertEqual(r['records'][0]['historical_fide_id'],'10')
        self.assertEqual(r['records'][0]['source_line'],2)

    def test_modern_id_and_name_can_bridge_old_number(self):
        r=self.run_fixture([pre('Alpha, Anton','Alpha, Anton','199001',10,'1950.01.01',2600)],
            [modern('Alpha, Anton','200201',101,'1950.01.01',2500)],[self.person(101)])
        self.assertEqual(len(r['records']),2)
        self.assertEqual(r['audit']['canonical_group_matches'][0]['match_method'],'modern_id_name_to_canonical_historical_group')

    def test_explicit_name_alias_and_dob_discrepancy_are_audited(self):
        r=self.run_fixture([pre('Collins, Sam','Collins, Sam','200101',101,'1981.01.01',2300)],[],
            [self.person(101,'Collins, Sam E','1982-09-05')])
        self.assertEqual(len(r['records']),1)
        self.assertTrue(r['audit']['canonical_group_matches'][0]['explicit_name_alias_used'])
        self.assertEqual(r['records'][0]['identity_flags'],['source_dob_differs_from_frozen_dob'])

    def test_ambiguous_groups_stop(self):
        r=self.run_fixture([
            pre('Alpha, Anton','Alpha, Anton','199001',101,'1950.01.01',2600),
            pre('Alpha junior, Anton','Alpha junior, Anton','199001',101,'1950.01.01',2500)],[],[self.person(101)])
        self.assertEqual(r['status'],'requires_identity_resolution')
        self.assertEqual(r['audit']['fatal_issues'][0]['reason'],'ambiguous_historical_canonical_groups')

    def test_same_period_conflict_and_prebirth_are_fatal(self):
        r=self.run_fixture([
            pre('Alpha, Anton','Alpha, Anton','199001',101,'1950.01.01',2600),
            pre('Alpha, Anton','Alpha, Anton','199001',101,'1950.01.01',2500)],[],[self.person(101,dob='1991-01-01')])
        reasons={x['reason'] for x in r['audit']['fatal_issues']}
        self.assertIn('rating_before_frozen_birth_month',reasons)
        self.assertEqual(r['audit']['unresolved_period_conflicts'][0]['candidate_ratings'],[2500,2600])

    def test_source_conflict_candidates_are_retained_for_peak_identifiability(self):
        r=self.run_fixture([
            pre('Alpha, Anton','Alpha, Anton','199001',101,'1950.01.01',2500),
            pre('Alpha, Anton','Alpha, Anton','199001',101,'1950.01.01',2600)],[],[self.person(101)])
        self.assertEqual(r['status'],'complete')
        self.assertEqual(r['audit']['fatal_issues'],[])
        self.assertEqual([row['rating'] for row in r['records']],[2500,2600])
        self.assertEqual(r['audit']['unresolved_period_conflicts'][0]['candidate_ratings'],[2500,2600])

    def test_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake.zip';p.write_bytes(b'not official archive')
            with self.assertRaisesRegex(ValueError,'fingerprint'):
                list(read_archive(p,'pre2002'))

    def test_spelling_split_with_same_id_dob_and_disjoint_periods_merges(self):
        r=self.run_fixture([
            pre('Alpha, Anton','Alpha, Anton','199001',101,'1950.01.01',2500),
            pre('Alternate, Anton','Alpha, Anton','199101',101,'1950.01.01',2510)],[],[self.person(101)])
        self.assertEqual(len(r['records']),2)
        self.assertEqual(r['audit']['fatal_issues'],[])
        self.assertTrue(all(x['spelling_split_groups_merged'] for x in r['audit']['canonical_group_matches']))

    def test_overlapping_other_id_does_not_pollute_canonical_group(self):
        r=self.run_fixture([
            pre('Alpha, Anton','Alpha, Anton','199001',101,'1950.01.01',2500),
            pre('Alpha, Anton','Alpha, Anton','199001',202,'1950.01.01',2700)],[],[self.person(101)])
        self.assertEqual([x['rating'] for x in r['records']],[2500])
        self.assertEqual(r['audit']['rejected_identity_candidates'][0]['reason'],'other_id_overlaps_current_id_in_canonical_group')

    def test_year_only_source_dob_disagreement_is_preserved(self):
        r=self.run_fixture([pre('Alpha, Anton','Alpha, Anton','199001',101,'1951',2500)],[],[self.person(101)])
        flag=r['audit']['identity_discrepancies'][0]
        self.assertIsNone(flag['source_dob'])
        self.assertEqual(flag['source_dob_year'],'1951')

    def test_name_normalization_does_not_fuzzy_match(self):
        self.assertEqual(normalized_name('García, José'),normalized_name('Garcia Jose'))
        self.assertNotEqual(normalized_name('Petrov, Ivan'),normalized_name('Petrov, I'))


if __name__=='__main__':unittest.main()
