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
spec = importlib.util.spec_from_file_location('v11_continue', ROOT / 'scripts/continue.py')
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
                 quote='Fixture elected ordinary full member in '+str(year)+'.', identity_note='Same name, specialty and career.',
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
        self.assertEqual((summary['baseline_day_no_known_conflict'], summary['body_day_no_known_conflict'], summary['day_status_net_change']), (368, 368, 0))
        self.assertEqual((summary['institutional_or_university_supported_day_no_known_conflict'], summary['edited_reference_only_day_no_known_conflict'], summary['other_attributed_secondary_only_day_no_known_conflict']), (215, 150, 3))
        self.assertEqual(ledger, self.old_claims)
        for before, after in zip(self.jp, rows):
            self.assertEqual({k:after[k] for k in before}, before)
        self.assertTrue(all(not r['v11_source_claim_added'] and not r['final_cohort_accepted'] for r in rows))

    def test_secondary_day_is_not_promoted_by_institutional_year(self):
        person = next(r for r in self.jp if r['dob_status'] == 'body_year_only' and r['broad_section_supported'] == '2')
        y = int(person['source_date_components_iso'])
        for tier, expected in [('commercial_edited_biographical_reference_secondary', 'edited_reference_only'), ('commercial_financial_filing_reproduction_secondary', 'other_attributed_secondary_only')]:
            with self.subTest(tier=tier):
                rows, _, _, _ = m.japan([claim(person, year=y, source_tier=tier)], {}, [])
                row = next(r for r in rows if r['member_key'] == person['member_key'])
                self.assertEqual(row['day_evidence_tier'], expected)
                self.assertFalse(row['has_institution_or_university_day_claim'])
        # A comparable minority disagreement is held even against two agreeing bodies.
        dates = [claim(self.gap, source_url='https://example.org/a'), claim(self.gap, source_url='https://example.org/b'), claim(self.gap, day=4, source_url='https://example.org/c')]
        rows, _, _, _ = m.japan(dates, {}, [])
        self.assertEqual(next(r for r in rows if r['member_key']==self.gap['member_key'])['dob_status'], 'source_date_conflict_hold')

    def test_reviewed_third_party_reproduction_is_other_secondary_not_institution_or_dictionary(self):
        tier = 'third_party_attributed_university_publication_reproduction_secondary'
        addition = claim(self.gap, source_tier=tier)
        rows, _, _, summary = m.japan([addition], {}, [])
        row = next(r for r in rows if r['member_key'] == self.gap['member_key'])
        self.assertEqual(row['day_evidence_tier'], 'other_attributed_secondary_only')
        self.assertFalse(row['has_institution_or_university_day_claim'])
        self.assertFalse(row['has_edited_reference_day_claim'])
        self.assertTrue(row['has_other_attributed_secondary_day_claim'])
        self.assertEqual(summary['other_attributed_secondary_only_day_no_known_conflict'], self.old_jp_summary['other_attributed_secondary_only_day_no_known_conflict']+1)
        for old in self.jp:
            if old['dob_status'] == 'body_day_no_known_conflict':
                after = next(r for r in rows if r['member_key'] == old['member_key'])
                for field in ['day_evidence_tier', 'has_institution_or_university_day_claim', 'has_edited_reference_day_claim', 'has_other_attributed_secondary_day_claim']:
                    self.assertEqual(after[field], old[field])
        with self.assertRaisesRegex(ValueError, 'Unreviewed source tier'):
            m.japan([claim(self.gap, source_tier=tier+'_unapproved')], {}, [])

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
        # A newly found modern-looking source cannot silently release an old
        # automatic calendar hold that had no explicit v6 overlay.
        explicit = m.js(m.BASE / 'inputs/japan_holds.json')
        auto = next(r for r in self.jp if r['dob_status'] == 'source_calendar_hold')
        rows, ledger, _, _ = m.japan([claim(auto)], {}, [])
        retained = next(r for r in rows if r['member_key'] == auto['member_key'])
        self.assertEqual(retained['dob_status'], 'source_calendar_hold')
        self.assertTrue(any(c['member_key'] == auto['member_key'] and c['source_url'] == 'https://example.org/fixture' for c in ledger))
        self.assertIn(auto['member_key'], m.inherited_holds())

    def test_bad_birth_precision_identity_and_capture_are_rejected(self):
        bad = [dict(precision='year'), dict(member_key='unknown'), dict(body_verified=False),
               dict(source_sha256=''), dict(source_sha256=None), dict(source_tier='unreviewed'), dict(source_url='https://en.wikipedia.org/fixture')]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                m.japan([claim(self.gap, **changes)], {}, [])
        # Only the exact source reviewed independently by root may lack original bytes.
        exceptional = next(c for c in m.js(m.V10.V9.V8.V7.V6.BASE / 'source_batches/japan_c/claims.json') if c['member_key'] == 'jpa:suzuki_atsuto')
        _, ledger, _, _ = m.japan([], {}, [])
        retained = next(c for c in ledger if c['source_url'] == exceptional['source_url'])
        self.assertIsNone(retained['source_sha256'])
        self.assertEqual(retained['extracted_body_sha256'], exceptional['extracted_body_sha256'])
        for old in self.old_claims:
            if old.get('source_sha256') is None:
                self.assertEqual(next(c for c in ledger if c['claim_id'] == old['claim_id']), old)
        for changed in [dict(source_url='https://example.org/unapproved.pdf'), dict(member_key=self.gap['member_key'], name_jp=self.gap['name_jp']), dict(extracted_body_sha256='b' * 64)]:
            with self.subTest(exception_changed=changed), self.assertRaisesRegex(ValueError, 'explicitly approved source exception'):
                m.japan([dict(exceptional, **changed)], {}, [])
        # A failed original capture is eligible only for a root-approved exact source exception.
        web_only = claim(self.gap, source_sha256=None, extracted_body_sha256='c'*64,
                         source_capture_status='original_capture_failed_body_verified_via_web',
                         source_original_capture_http_status=404, web_body_ref='turn100view0')
        approval = {k:web_only[k] for k in ['member_key', 'source_url', 'extracted_body_sha256', 'source_original_capture_http_status', 'web_body_ref']}
        approval['root_verification_ref'] = 'turn101search0'
        config = m.js(ROOT/'inputs/batch_selection.json');config['web_body_capture_exceptions']=[approval]
        original_js = m.js
        with patch.object(m, 'js', side_effect=lambda p:config if p==ROOT/'inputs/batch_selection.json' else original_js(p)):
            _, ledger, _, _ = m.japan([web_only], {}, [])
            self.assertIsNone(next(c for c in ledger if c['source_url']==web_only['source_url'])['source_sha256'])
            with self.assertRaisesRegex(ValueError, 'explicitly approved source exception'):
                m.japan([dict(web_only, source_original_capture_http_status=403)], {}, [])
            with self.assertRaisesRegex(ValueError, 'explicitly approved source exception'):
                m.japan([dict(web_only, web_body_ref='turn100view1')], {}, [])

    def test_inherited_exact_calendar_releases_remain_and_no_new_release_is_implicit(self):
        rows, ledger, _, summary = m.japan([], {}, [])
        self.assertEqual(summary['approved_calendar_routing_releases'], 0)
        for key, (_, year, month, day) in dict(m.V10.V9.V8.V7.EXACT_CALENDAR_ROUTING_RELEASES, **m.V10.V9.V8.EXACT_CALENDAR_ROUTING_RELEASES).items():
            before = next(r for r in self.jp if r['member_key'] == key)
            after = next(r for r in rows if r['member_key'] == key)
            self.assertEqual((before['dob_status'], after['dob_status']), ('body_day_no_known_conflict', 'body_day_no_known_conflict'))
            self.assertEqual(after['source_date_components_iso'], f'{year:04d}-{month:02d}-{day:02d}')
            for old in [c for c in self.old_claims if c['member_key'] == key]:
                self.assertEqual(next(c for c in ledger if c['claim_id'] == old['claim_id']), old)
        # A collector's proposed equivalence cannot authorize itself.
        person = next(r for r in self.jp if r['dob_status'] == 'source_calendar_hold')
        proposed = claim(person, source_supplied_calendar_pair=True)
        after, _, _, _ = m.japan([proposed], {}, [])
        self.assertEqual(next(r for r in after if r['member_key'] == person['member_key'])['dob_status'], 'source_calendar_hold')
        original_js = m.js
        unapproved = dict(member_key=person['member_key'], decision_type='release_inherited_calendar_routing', source_sha256='a'*64, year=1900, month=2, day=3, root_approved=True, independent_dates_qa_passed=True)
        with patch.object(m, 'js', side_effect=lambda p:[unapproved] if p == ROOT/'inputs/calendar_routing_decisions.json' else original_js(p)):
            with self.assertRaisesRegex(ValueError, 'No new v11 calendar routing'):
                m.japan([proposed], {}, [])

    def test_all_four_prior_releases_and_new_comparable_conflict_reduction(self):
        rows, ledger, _, _ = m.japan([], {}, [])
        dates = {'jpa-unlinked-a9d1e2cde713ae0e':'1865-06-08', 'jpa-unlinked-d4cbc74833986120':'1870-04-10',
                 'jpa-unlinked-7ecae30c03b86d5f':'1865-08-01', 'jpa-unlinked-eabfb6c33df81d73':'1855-11-04'}
        for key, expected in dates.items():
            before = next(r for r in self.jp if r['member_key'] == key)
            after = next(r for r in rows if r['member_key'] == key)
            self.assertEqual(after['source_date_components_iso'], expected)
            self.assertEqual({k:after[k] for k in before}, before)
        person = next(r for r in self.jp if r['member_key']=='jpa-unlinked-eabfb6c33df81d73')
        addition = claim(person, year=1855, month=11, day=5, source_url='https://example.org/competing')
        after, old, _, _ = m.japan([addition], {}, [])
        changed = next(r for r in after if r['member_key']==person['member_key'])
        self.assertEqual(changed['dob_status'], 'source_date_conflict_hold')
        self.assertEqual(changed['source_date_components_iso'], '')
        for c in self.old_claims:
            self.assertEqual(next(x for x in old if x['claim_id']==c['claim_id']),c)

    def test_france_empty_delta_preserves_provenance_and_all_inherited_conflicts(self):
        rows, _, _, ledger, summary = m.france([])
        self.assertEqual(summary['current'], dict(identity_accepted=755, membership_accepted=408, dob_accepted=743))
        self.assertEqual(summary['all_three_accepted'], 405)
        self.assertEqual(ledger, m.readcsv(m.BASE / 'outputs/france_membership_decisions.csv'))
        self.assertEqual(summary['known_election_conflict_rows'], 25)
        for before, after in zip(self.fr, rows):
            for field in ['accepted_dob_iso', 'accepted_full_member_election_date', 'accepted_full_member_election_year', 'membership_as_of_year', 'v3_evidence_urls', 'v4_evidence_urls', 'v5_evidence_urls', 'v6_evidence_urls', 'v7_evidence_urls', 'v8_evidence_urls', 'v3_membership_decision_status', 'v4_membership_decision_status', 'v5_membership_decision_status', 'v6_membership_decision_status', 'v7_membership_decision_status', 'v8_membership_decision_status', 'election_date_conflict']:
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
        d = copy.deepcopy(original);d['evidence'][0]['event_type'] = 'as_of';attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['event_type'] = 'relative_year_arithmetic';attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['event_year_is_relative'] = True;attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['event_subject_role'] = 'author';attacks.append(d)
        for kind in ['membership_attested_by_year', 'presidency_attesting_membership', 'perpetual_secretary_appointment_attesting_membership_by_year']:
            d = copy.deepcopy(original);d['evidence'][0]['event_type'] = kind;attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['source_url'] = 'https://mirror.example/fixture';attacks.append(d)
        d = copy.deepcopy(original);d['evidence'][0]['source_url'] = 'https://unreviewed.academie-sciences.fr/fixture';attacks.append(d)
        d = copy.deepcopy(original);d['accepted_full_member_election_precision'] = 'day';d['accepted_full_member_election_date'] = str(d['accepted_full_member_election_year'])+'-04-05';attacks.append(d)
        for d in attacks:
            with self.subTest(evidence=d['evidence']), self.assertRaises(ValueError):
                m.france([d])
        # A parent-institution original and an explicit ordinary nonresident event are valid.
        d = copy.deepcopy(original);d['evidence'][0].update(role='ordinary_full_member_nonresident', event_type='explicit_ordinary_membership_start', source_role='parent_institution_firstparty', source_url='https://podcasts.institutdefrance.fr/fixture')
        rows, _, _, _, _ = m.france([d])
        self.assertEqual(next(r for r in rows if r['candidate_group_id']==self.fr_gap['candidate_group_id'])['membership_accepted'], '1')
        d = copy.deepcopy(original);d['evidence'][0].update(event_type='explicit_ordinary_membership_start', source_url='https://comptes-rendus.academie-sciences.fr/fixture')
        rows, _, _, _, _ = m.france([d])
        self.assertEqual(next(r for r in rows if r['candidate_group_id']==self.fr_gap['candidate_group_id'])['membership_accepted'], '1')

    def test_fixed_selections_are_exact_and_disjoint(self):
        selected = m.selections()
        self.assertEqual({k:len(v) for k,v in selected.items()}, dict(japan=37, france=307))
        self.assertTrue(selected['japan'] <= {r['member_key'] for r in self.jp})
        self.assertTrue(selected['france'] <= {r['candidate_group_id'] for r in self.fr})

    def test_prepare_does_not_count_claims_as_completed_processing(self):
        with tempfile.TemporaryDirectory(prefix='academy-v11-test-') as folder:
            fixture = Path(folder);(fixture/'inputs').mkdir();(fixture/'source_batches').mkdir();(fixture/'source_batches/japan_scope').mkdir();m.dump(fixture/'source_batches/japan_scope/section_proposals.json', [])
            config=dict(japan_claim_files=['claims.json'], japan_processed_files=['jp.csv'], japan_hold_files=[], france_decision_files=[], france_processed_files=['fr.csv'])
            m.dump(fixture/'inputs/batch_selection.json', config)
            m.dump(fixture/'source_batches/claims.json',[claim(self.gap)])
            (fixture/'source_batches/jp.csv').write_text('member_key,status\n'+self.gap['member_key']+',not_processed\n')
            (fixture/'source_batches/fr.csv').write_text('candidate_group_id,status\n')
            with patch.object(m,'check_baseline'),patch.object(m,'selections',return_value=dict(japan={self.gap['member_key']},france=set())):
                truthful_japan = m.prepare(fixture)
                self.assertEqual(truthful_japan['japan_delta_processed_ids.json'], [])
                (fixture/'source_batches/jp.csv').write_text('member_key,status\n'+self.gap['member_key']+',bounded_new_route_checked\n')
                prepared = m.prepare(fixture)
            old = m.js(m.BASE/'inputs/japan_claims.json')
            self.assertEqual(prepared['japan_claims.json'][:len(old)], old)
            self.assertEqual(prepared['japan_holds.json'], m.inherited_holds())
            self.assertTrue(set(m.js(m.BASE/'inputs/japan_processed_ids.json')) <= set(prepared['japan_processed_ids.json']))
            self.assertEqual(prepared['inherited_france_decisions.json'], m.readcsv(m.BASE/'outputs/france_membership_decisions.csv'))
            (fixture/'source_batches/fr.csv').write_text('candidate_group_id,status\n'+self.fr_gap['candidate_group_id']+',not_searched\n')
            with patch.object(m,'check_baseline'),patch.object(m,'selections',return_value=dict(japan={self.gap['member_key']},france={self.fr_gap['candidate_group_id']})):
                truthful = m.prepare(fixture)
                self.assertEqual(truthful['france_processed_ids.json'], [])
                (fixture/'source_batches/fr.csv').write_text('candidate_group_id,status\n'+self.fr_gap['candidate_group_id']+',not_searched\n'+self.fr_gap['candidate_group_id']+',not_searched\n')
                with self.assertRaisesRegex(ValueError, 'Duplicate processing disposition'):
                    m.prepare(fixture)
            # Exact root-approved bulk addenda are separate from fixed selection and processing.
            config['japan_cross_source_member_keys']=[self.gap['member_key']]
            m.dump(fixture/'inputs/batch_selection.json', config)
            (fixture/'source_batches/jp.csv').write_text('member_key,status\n')
            (fixture/'source_batches/fr.csv').write_text('candidate_group_id,status\n')
            with patch.object(m,'check_baseline'),patch.object(m,'selections',return_value=dict(japan=set(),france=set())):
                bulk = m.prepare(fixture)
                self.assertEqual(bulk['japan_delta_processed_ids.json'], [])
                self.assertEqual(len(bulk['japan_delta_claims.json']), 1)
                config['japan_cross_source_member_keys']=[]
                m.dump(fixture/'inputs/batch_selection.json', config)
                with self.assertRaisesRegex(ValueError, 'Unselected v11 Japan claim'):
                    m.prepare(fixture)

    def test_section_only_queries_do_not_mark_birthdays_searched(self):
        person = next(r for r in self.jp if r['dob_status']=='not_body_source_processed')
        with tempfile.TemporaryDirectory(prefix='academy-v11-scope-test-') as folder:
            fixture=Path(folder);(fixture/'inputs').mkdir();(fixture/'source_batches/japan_scope').mkdir(parents=True)
            config=dict(japan_claim_files=['japan_scope/claims.json'], japan_processed_files=['japan_scope/processed.csv'],
                        japan_hold_files=[],france_decision_files=[],france_processed_files=[])
            m.dump(fixture/'inputs/batch_selection.json',config)
            m.dump(fixture/'source_batches/japan_scope/claims.json',[])
            m.dump(fixture/'source_batches/japan_scope/section_proposals.json',[])
            (fixture/'source_batches/japan_scope/processed.csv').write_text('member_key,status,dob_search_performed\n'+person['member_key']+',section_route_queried,False\n')
            with patch.object(m,'check_baseline'),patch.object(m,'selections',return_value=dict(japan={person['member_key']},france=set())):
                prepared=m.prepare(fixture)
            self.assertEqual(prepared['japan_delta_processed_ids.json'],[])
            self.assertEqual(m.processing_summary(fixture)['japan']['actually_processed_dispositions'],1)
            rows,_,_,_=m.japan([],{},prepared['japan_delta_processed_ids.json'])
            after=next(r for r in rows if r['member_key']==person['member_key'])
            self.assertEqual(after['dob_status'],person['dob_status'])
            self.assertFalse(after['body_source_reviewed'])

    def test_full_v10_scope_and_DOB_hold_state_is_inherited_without_reapplication(self):
        rows,ledger,queue,summary=m.japan([],{},[])
        self.assertEqual((summary['broad_section_ii_supported'],summary['section_unresolved'],summary['section_ii_and_body_day_no_known_conflict'],len(queue)),(438,37,360,115))
        self.assertEqual(ledger,self.old_claims)
        section_ids={d['member_key'] for d in m.js(m.BASE/'inputs/japan_section_decisions.json')}
        self.assertEqual(len(section_ids),10)
        for before,after in zip(self.jp,rows):
            self.assertEqual({k:after[k] for k in before},before)
            if before['member_key'] in section_ids:self.assertEqual(after['v10_section_evidence_as_of_year'],1906)
        fr,accepted,gaps,_,f=m.france([])
        self.assertEqual((f['current']['dob_accepted'],f['current']['membership_accepted'],f['all_three_accepted']),(743,408,405))
        before=next(r for r in self.fr if r['candidate_group_id']=='CTHS_112065');after=next(r for r in fr if r['candidate_group_id']=='CTHS_112065')
        for k in ['dob_accepted','accepted_dob_iso','exact_dob_claims','exact_dob_conflict','v10_previous_accepted_dob_iso','v10_previous_exact_dob_claims']:
            self.assertEqual(after[k],before[k])
        self.assertEqual((after['dob_accepted'],after['accepted_dob_iso'],after['exact_dob_claims']),('0','','1882-01-13|1882-01-18'))
        self.assertNotIn(after['candidate_group_id'],{r['candidate_group_id'] for r in accepted})
        self.assertIn(after['candidate_group_id'],{r['candidate_group_id'] for r in gaps})

    def test_CTHS_institutional_contribution_credit_and_member_start_are_both_required(self):
        original=decision(self.fr_gap)
        original['evidence'][0].update(source_url='https://cths.fr/an/savant.php?id='+self.fr_gap['candidate_group_id'].removeprefix('CTHS_'),
            source_sha256='a'*64,source_role='academy_authored_independent_host',academy_authored_or_issued_original=True,
            source_author_credit='Académie des sciences',source_author_credit_verified=True,
            source_author_credit_scope='explicit_credited_writer_or_cowriter',credited_authors=['Académie des sciences'],
            cths_society_id='506',cths_typed_ordinary_role_verified=True,cths_literal_full_member_start_verified=True,
            cths_same_body_authorship_role_start_verified=True,cths_identity_body_verified=True,event_type='ordinary_membership_start')
        for branch in ['Academy','Institut']:
            good=copy.deepcopy(original)
            if branch=='Institut':good['evidence'][0].update(source_role='parent_institution_firstparty',source_author_credit='Institut de France',
                parent_institution_authored_or_issued_original=True,academy_authored_or_issued_original=False,credited_authors=['Bruno Delmas','Institut de France'])
            self.assertEqual(next(r for r in m.france([good])[0] if r['candidate_group_id']==self.fr_gap['candidate_group_id'])['membership_accepted'],'1')
            for change in [dict(source_author_credit_verified=False),dict(source_author_credit_scope='affiliation_mention'),
                           dict(credited_authors=None),dict(credited_authors=['Personal writer only']),dict(credited_authors=['Académie des sciences et belles-lettres de Besançon']),dict(credited_authors=['Martine François (membre de l’Institut de France)']),dict(cths_society_id='999'),dict(cths_typed_ordinary_role_verified=False),
                           dict(cths_literal_full_member_start_verified=False),dict(cths_same_body_authorship_role_start_verified=False),
                           dict(cths_identity_body_verified=False),dict(source_sha256=''),dict(source_author_credit='Uncredited institution'),
                           dict(source_url='https://cths.fr/an/savant.php?id=999999'),dict(event_type='as_of')]:
                attack=copy.deepcopy(good);attack['evidence'][0].update(change)
                with self.subTest(branch=branch,attack=change),self.assertRaises(ValueError):m.france([attack])
            if branch=='Institut':
                attack=copy.deepcopy(good);attack['evidence'][0]['academy_authored_or_issued_original']=True
                with self.assertRaises(ValueError):m.france([attack])
                attack=copy.deepcopy(good);attack['evidence'][0]['parent_institution_authored_or_issued_original']=False
                with self.assertRaises(ValueError):m.france([attack])

    def test_explicit_nonordinary_same_event_and_exact_role_control_block_generic_member(self):
        original=decision(self.fr_gap)
        nonordinary=copy.deepcopy(original['evidence'][0]);nonordinary.update(role='foreign_associate',source_url='https://www.academie-sciences.fr/fixture_foreign')
        attack=copy.deepcopy(original);attack['evidence'].append(nonordinary)
        with self.assertRaisesRegex(ValueError,'same-event nonordinary'):m.france([attack])
        attack=copy.deepcopy(original);attack['known_nonordinary_role_conflict_for_same_event']=True
        with self.assertRaisesRegex(ValueError,'same-event nonordinary'):m.france([attack])
        # A distinct earlier correspondent event is retained as history and may
        # not be substituted for or confused with the later full-member start.
        earlier=copy.deepcopy(nonordinary);earlier.update(role='correspondent',event_year=nonordinary['event_year']-5)
        valid=copy.deepcopy(original);valid['evidence'].append(earlier)
        rows,_,_,_,_=m.france([valid]);self.assertEqual(next(r for r in rows if r['candidate_group_id']==self.fr_gap['candidate_group_id'])['membership_accepted'],'1')
        for key in ['CTHS_117210','CTHS_117212']:
            controlled=next(r for r in self.fr if r['candidate_group_id']==key)
            with self.assertRaisesRegex(ValueError,'Exact unresolved source-role control'):m.france([decision(controlled)])
        # A prior same-event nonordinary body is equally binding; no new generic
        # member assertion may silently erase the already-observed source role.
        with patch.object(m,'inherited_france_role_evidence',return_value={self.fr_gap['candidate_group_id']:[nonordinary]}),self.assertRaisesRegex(ValueError,'same-event nonordinary'):
            m.france([original])

    def test_new_1947_section_actions_require_exact_source_edition_and_external_QA(self):
        actions=m.reviewed_section_decisions()
        self.assertEqual(len(actions),3)
        rows,ledger,queue,summary=m.japan([],{},[],actions)
        self.assertEqual((summary['broad_section_ii_supported'],summary['section_i_excluded'],summary['section_unresolved'],len(queue)),(438,10,34,112))
        self.assertEqual(ledger,self.old_claims)
        changed={d['member_key'] for d in actions}
        for before,after in zip(self.jp,rows):
            allowed={'broad_section_supported','section_evidence_status'} if before['member_key'] in changed else set()
            self.assertEqual({k:after[k] for k in before if k not in allowed},{k:v for k,v in before.items() if k not in allowed})
        with tempfile.TemporaryDirectory(prefix='academy-v11-section-gate-') as folder:
            fixture=Path(folder)
            paths=['inputs/japan_section_approvals.json','source_batches/japan_scope/section_proposals.json','source_batches/japan_scope/MANIFEST.json','source_audits/japan_scope_independent_qa.json']
            originals={p:(ROOT/p).read_bytes() for p in paths}
            for p,data in originals.items():
                path=fixture/p;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            self.assertEqual(len(m.reviewed_section_decisions(fixture)),3)
            for attack in ['wrong_edition','missing_root','false_overlap']:
                for p,data in originals.items():(fixture/p).write_bytes(data)
                if attack=='wrong_edition':
                    p=fixture/paths[1];proposals=m.js(p);proposals[0]['source_edition_year']=1906;m.dump(p,proposals)
                else:
                    p=fixture/paths[0];approvals=m.js(p)
                    if attack=='missing_root':approvals[0]['root_approved']=False
                    else:
                        qa_path=fixture/paths[3];qa=m.js(qa_path);qa['proposal_checks'][0]['snapshot_year_overlap_passed']=False;m.dump(qa_path,qa)
                        for a in approvals:a['independent_section_qa_sha256']=m.sha(qa_path)
                    m.dump(p,approvals)
                with self.subTest(attack=attack),self.assertRaises(ValueError):m.reviewed_section_decisions(fixture)


if __name__ == '__main__':
    unittest.main()
