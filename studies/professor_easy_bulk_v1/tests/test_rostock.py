import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('rostock', Path(__file__).resolve().parents[1] / 'scripts/build_rostock.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def row(date='01.02.1950'):
    return {'purl': 'http://purl.uni-rostock.de/cpr/_test', 'profkat.idx_profname.headline': 'Synthetic Person',
            'profkat.birthdate': date, 'profkat.birthplace': '', 'profkat.last_professorship': 'Honorarprofessor',
            'profkat.last_faculty': '', 'profkat.period': '', 'profkat.gnd': ''}


class Tests(unittest.TestCase):
    def test_partial_and_missing_dates_are_not_filled(self):
        self.assertEqual(m.parse_date('1950')['source_date_components_iso'], '1950')
        self.assertEqual(m.parse_date('')['birth_year'], None)
        self.assertEqual(m.parse_date('c. 1950')['precision'], 'unparsed')

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            m.parse_date('31.02.1950')

    def test_shared_purl_is_one_person_with_two_memberships(self):
        rows, memberships, summary = m.assemble({'physics': [row()], 'chemistry': [row()]})
        self.assertEqual((len(rows), len(memberships)), (1, 2))
        self.assertEqual(summary['shared_subject_purls'], 1)
        self.assertTrue(rows[0]['honorary_title_indicator'])
        self.assertFalse(rows[0]['individually_dob_verified'])

    def test_conflicting_duplicate_is_not_silently_overwritten(self):
        with self.assertRaises(ValueError):
            m.assemble({'physics': [row()], 'chemistry': [row('02.02.1950')]})

    def test_year_only_is_not_full_date_candidate_and_unknown_stays_unknown(self):
        rows, _, summary = m.assemble({'physics': [row('1950')]})
        self.assertEqual(summary['full_date_window_candidates'], 0)
        self.assertEqual(rows[0]['birth_year_window_1835_1985'], 'inside')
        rows, _, _ = m.assemble({'physics': [row('')]})
        self.assertEqual(rows[0]['birth_year_window_1835_1985'], 'unknown')


if __name__ == '__main__':
    unittest.main()
