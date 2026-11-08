import sys
sys.dont_write_bytecode = True
import copy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v5_continue', ROOT / 'scripts/continue.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def claim(person, **changes):
    c = dict(member_key=person['member_key'], name_jp=person['name_jp'], year=1900, month=2, day=3,
             precision='day', calendar='not_stated', calendar_comparable=True,
             body_verified=True, identity_body_supported=True, source_url='https://example.org/fixture',
             source_tier='commercial_edited_biographical_reference_secondary', raw_birth_statement='Fixture born1900-02-03',
             identity_support='Same named researcher, professional field and university career.',
             source_sha256='a' * 64, retrieved_utc='2026-10-29T00:00:00Z')
    c.update(changes)
    return c


def decision(person, **changes):
    year = int(person['accepted_dob_iso'][:4]) + 40
    d = dict(candidate_group_id=person['candidate_group_id'], name=person['display_name'],
             membership_accepted=1, membership_role_supported=1, election_cutoff_stable=1,
             election_date_conflict=0, accepted_full_member_election_date=None,
             accepted_full_member_election_year=year, accepted_full_member_election_precision='year',
             decision_status='fixture_strict_full_member', reason='Fixture ordinary election, not correspondent event.',
             reviewed=True, evidence=[dict(body_verified=True, source_url='https://www.academie-sciences.fr/fixture',
                 source_role='academy_owned_firstparty', role='ordinary_full_member',
                 quote='Fixture elected ordinary full member.', identity_note='Same name, specialty and career.',
                 event_date=None, event_year=year, event_precision='year')])
    d.update(changes)
    return d


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp, cls.old_claims, _, cls.old_jp_summary = m.previous_japan()
        cls.fr = m.readcsv(m.BASE / 'outputs/france_master877.csv')
        cls.gap = next(r for r in cls.jp if r['dob_status'] == 'bounded_search_no_body_birth_claim' and r['broad_section_supported'] == '2')
        cls.fr_gap = next(r for r in cls.fr if r['identity_accepted'] == r['dob_accepted'] == '1' and r['membership_accepted'] == '0' and r['election_date_conflict'] != '1')

    def test_empty_japan_delta_inherits_all_claims_holds_and_tiers(self):
        m.check_baseline()
        rows, ledger, _, summary = m.japan([], {}, [])
        self.assertEqual((summary['baseline_day_no_known_conflict'], summary['body_day_no_known_conflict'], summary['day_status_net_change']), (310, 310, 0))
        self.assertEqual((summary['institutional_or_university_supported_day_no_known_conflict'], summary['edited_reference_only_day_no_known_conflict'], summary['other_attributed_secondary_only_day_no_known_conflict']), (195, 114, 1))
        self.assertEqual(ledger, self.old_claims)
        self.assertEqual([(r['member_key'], r['dob_status'], r['v4_source_claim_added'], r['body_source_reviewed']) for r in rows], [(r['member_key'], r['dob_status'], r['v4_source_claim_added'], r['body_source_reviewed']) for r in self.jp])
        self.assertTrue(all(not r['v5_source_claim_added'] and not r['final_cohort_accepted'] for r in rows))

    def test_secondary_day_is_not_promoted_by_institutional_year(self):
        person = next(r for r in self.jp if r['dob_status'] == 'body_year_only' and r['broad_section_supported'] == '2')
        y = int(person['source_date_components_iso'])
        for tier, expected in [('commercial_edited_biographical_reference_secondary', 'edited_reference_only'), ('commercial_financial_filing_reproduction_secondary', 'other_attributed_secondary_only')]:
            with self.subTest(tier=tier):
                rows, _, _, _ = m.japan([claim(person, year=y, source_tier=tier)], {}, [])
                row = next(r for r in rows if r['member_key'] == person['member_key'])
                self.assertEqual(row['day_evidence_tier'], expected)
                self.assertFalse(row['has_institution_or_university_day_claim'])

    def test_hold_inheritance_and_historical_alternate_do_not_release_dates(self):
        person = next(r for r in self.jp if r['name_jp'] == '志賀 潔')
        alternate = claim(person, year=1870, month=12, day=18, calendar='lunar_explicit', calendar_comparable=False)
        rows, _, _, _ = m.japan([alternate], {}, [])
        row = next(r for r in rows if r['member_key'] == person['member_key'])
        self.assertEqual((row['dob_status'], row['source_date_components_iso']), ('body_day_no_known_conflict', '1871-02-07'))
        with self.assertRaisesRegex(ValueError, 'Historical alternate'):
            m.japan([alternate], {person['member_key']:dict(status='source_calendar_hold', reason='Unconverted old-calendar alternative')}, [])
        merged = m.merge_holds({'x':dict(status='source_date_conflict_hold', reason='Inherited two-body conflict')}, {'x':dict(status='source_calendar_hold', reason='Another calendar statement')})
        self.assertEqual(merged['x']['status'], 'source_date_conflict_hold')
        self.assertIn('Inherited two-body conflict', merged['x']['reason'])
        combined = m.normalize_holds([dict(member_key='x', hold_type='calendar_and_source_year_hold', reason='1867 era versus1868 lifespan')])
        self.assertEqual(combined['x']['status'], 'source_calendar_hold')
        with self.assertRaisesRegex(ValueError, 'Unrecognized member-wide hold'):
            m.normalize_holds([dict(member_key='x', hold_type='unmapped_but_important_hold', reason='Do not drop')])

    def test_bad_birth_precision_identity_and_capture_are_rejected(self):
        bad = [dict(precision='year'), dict(member_key='unknown'), dict(body_verified=False),
               dict(source_sha256=''), dict(source_sha256=None), dict(source_tier='unreviewed'), dict(source_url='https://en.wikipedia.org/fixture')]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                m.japan([claim(self.gap, **changes)], {}, [])
        # Only the exact source reviewed independently by root may lack original bytes.
        exceptional = next(c for c in m.js(ROOT / 'source_batches/japan_c/claims.json') if c['member_key'] == 'jpa:suzuki_atsuto')
        _, ledger, _, _ = m.japan([exceptional], {}, [])
        retained = next(c for c in ledger if c['source_url'] == exceptional['source_url'])
        self.assertIsNone(retained['source_sha256'])
        self.assertEqual(retained['extracted_body_sha256'], exceptional['extracted_body_sha256'])
        for changed in [dict(source_url='https://example.org/unapproved.pdf'), dict(member_key=self.gap['member_key'], name_jp=self.gap['name_jp']), dict(extracted_body_sha256='b' * 64)]:
            with self.subTest(exception_changed=changed), self.assertRaisesRegex(ValueError, 'explicitly approved source exception'):
                m.japan([dict(exceptional, **changed)], {}, [])

    def test_france_empty_delta_preserves_provenance_and_all_inherited_conflicts(self):
        rows, _, _, ledger, summary = m.france([])
        self.assertEqual(summary['current'], dict(identity_accepted=755, membership_accepted=290, dob_accepted=744))
        self.assertEqual(summary['all_three_accepted'], 288)
        self.assertEqual(len(ledger), len(m.readcsv(m.BASE / 'outputs/france_membership_decisions.csv')))
        for before, after in zip(self.fr, rows):
            for field in ['accepted_dob_iso', 'accepted_full_member_election_date', 'accepted_full_member_election_year', 'membership_as_of_year', 'v3_evidence_urls', 'v4_evidence_urls', 'election_date_conflict']:
                self.assertEqual(before[field], after[field])
        louis = next(r for r in rows if r['candidate_group_id'] == 'CTHS_107107')
        self.assertEqual((louis['membership_accepted'], louis['election_date_conflict']), ('0', '1'))
        attack = decision(louis, previous_conflict_explicitly_resolved=True)
        with self.assertRaisesRegex(ValueError, 'inherited France'):
            m.france([attack])

    def test_france_acceptance_requires_matching_ordinary_academy_event(self):
        original = decision(self.fr_gap)
        attacks = []
        for role in ['correspondent', 'foreign_associate']:
            d = copy.deepcopy(original);d['evidence'][0]['role'] = role;attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['source_role'] = 'secondary_reference';attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['event_year'] += 1;attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['event_year_is_derived'] = True;attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['source_url'] = 'https://mirror.example/fixture';attacks.append(d)
        d = copy.deepcopy(original);d['accepted_full_member_election_precision'] = 'day';d['accepted_full_member_election_date'] = str(d['accepted_full_member_election_year'])+'-04-05';attacks.append(d)
        for d in attacks:
            with self.subTest(evidence=d['evidence']), self.assertRaises(ValueError):
                m.france([d])
        # A parent-institution original and an explicit ordinary nonresident event are valid.
        d = copy.deepcopy(original);d['evidence'][0].update(role='ordinary_full_member_nonresident', source_role='parent_institution_firstparty', source_url='https://podcasts.institutdefrance.fr/fixture')
        rows, _, _, _, _ = m.france([d])
        self.assertEqual(next(r for r in rows if r['candidate_group_id']==self.fr_gap['candidate_group_id'])['membership_accepted'], '1')

    def test_fixed_selections_are_exact_and_disjoint(self):
        selected = m.selections()
        self.assertEqual({k:len(v) for k,v in selected.items()}, dict(japan=89, france=120))
        self.assertTrue(selected['japan'] <= {r['member_key'] for r in self.jp})
        self.assertTrue(selected['france'] <= {r['candidate_group_id'] for r in self.fr})

    def test_prepare_does_not_count_claims_as_completed_processing(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as folder:
            fixture = Path(folder);(fixture/'inputs').mkdir();(fixture/'source_batches').mkdir()
            config=dict(japan_claim_files=['claims.json'], japan_processed_files=['jp.csv'], japan_hold_files=[], france_decision_files=[], france_processed_files=['fr.csv'])
            m.dump(fixture/'inputs/batch_selection.json', config)
            m.dump(fixture/'source_batches/claims.json',[claim(self.gap)])
            (fixture/'source_batches/jp.csv').write_text('member_key,status\n'+self.gap['member_key']+',not_processed\n')
            (fixture/'source_batches/fr.csv').write_text('candidate_group_id,status\n')
            with patch.object(m,'check_baseline'),patch.object(m,'selections',return_value=dict(japan={self.gap['member_key']},france=set())):
                with self.assertRaisesRegex(ValueError, 'actual processing'):
                    m.prepare(fixture)
                (fixture/'source_batches/jp.csv').write_text('member_key,status\n'+self.gap['member_key']+',bounded_new_route_checked\n')
                prepared = m.prepare(fixture)
            old = m.js(m.BASE/'inputs/japan_claims.json')
            self.assertEqual(prepared['japan_claims.json'][:len(old)], old)
            self.assertEqual(prepared['japan_holds.json'], m.js(m.BASE/'inputs/japan_holds.json'))
            self.assertTrue(set(m.js(m.BASE/'inputs/japan_processed_ids.json')) <= set(prepared['japan_processed_ids.json']))
            self.assertEqual(prepared['inherited_france_decisions.json'], m.js(m.BASE/'inputs/france_decisions.json'))
            (fixture/'source_batches/fr.csv').write_text('candidate_group_id,status\n'+self.fr_gap['candidate_group_id']+',not_searched\n')
            with patch.object(m,'check_baseline'),patch.object(m,'selections',return_value=dict(japan={self.gap['member_key']},france={self.fr_gap['candidate_group_id']})):
                truthful = m.prepare(fixture)
                self.assertEqual(truthful['france_processed_ids.json'], [])
                (fixture/'source_batches/fr.csv').write_text('candidate_group_id,status\n'+self.fr_gap['candidate_group_id']+',not_searched\n'+self.fr_gap['candidate_group_id']+',not_searched\n')
                with self.assertRaisesRegex(ValueError, 'Duplicate processing disposition'):
                    m.prepare(fixture)


if __name__ == '__main__':
    unittest.main()
