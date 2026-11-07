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
spec = importlib.util.spec_from_file_location('v10_continue', ROOT / 'scripts/continue.py')
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
        self.assertTrue(all(not r['v10_source_claim_added'] and not r['final_cohort_accepted'] for r in rows))

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
        exceptional = next(c for c in m.js(m.V9.V8.V7.V6.BASE / 'source_batches/japan_c/claims.json') if c['member_key'] == 'jpa:suzuki_atsuto')
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
        for key, (_, year, month, day) in dict(m.V9.V8.V7.EXACT_CALENDAR_ROUTING_RELEASES, **m.V9.V8.EXACT_CALENDAR_ROUTING_RELEASES).items():
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
            with self.assertRaisesRegex(ValueError, 'No new v10 calendar routing'):
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
        self.assertEqual(summary['current'], dict(identity_accepted=755, membership_accepted=394, dob_accepted=744))
        self.assertEqual(summary['all_three_accepted'], 392)
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
        self.assertEqual({k:len(v) for k,v in selected.items()}, dict(japan=47, france=82))
        self.assertTrue(selected['japan'] <= {r['member_key'] for r in self.jp})
        self.assertTrue(selected['france'] <= {r['candidate_group_id'] for r in self.fr})

    def test_prepare_does_not_count_claims_as_completed_processing(self):
        with tempfile.TemporaryDirectory(prefix='academy-v10-test-') as folder:
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
                with self.assertRaisesRegex(ValueError, 'Unselected v10 Japan claim'):
                    m.prepare(fixture)

    def test_section_only_queries_do_not_mark_birthdays_searched(self):
        person = next(r for r in self.jp if r['dob_status']=='not_body_source_processed')
        with tempfile.TemporaryDirectory(prefix='academy-v10-scope-test-') as folder:
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

    def test_exact_direct_section_actions_change_scope_only_after_pinned_root_and_QA(self):
        decisions=m.reviewed_section_decisions()
        self.assertEqual(len(decisions),10)
        rows,ledger,queue,summary=m.japan([],{},[],decisions)
        self.assertEqual(ledger,self.old_claims)
        self.assertEqual((summary['broad_section_ii_supported'],summary['section_unresolved'],summary['section_i_excluded']),(438,37,7))
        self.assertEqual((summary['body_day_no_known_conflict'],summary['section_ii_and_body_day_no_known_conflict'],len(queue)),(368,360,115))
        changed={d['member_key'] for d in decisions}
        for before,after in zip(self.jp,rows):
            allowed={'broad_section_supported','section_evidence_status'} if before['member_key'] in changed else set()
            self.assertEqual({k:after[k] for k in before if k not in allowed},{k:v for k,v in before.items() if k not in allowed})
            self.assertEqual(after['dob_status'],before['dob_status'])
        original_js=m.js;approval_path=ROOT/'inputs/japan_section_approvals.json';actual=original_js(approval_path)
        for change in [dict(root_approved=False),dict(independent_section_qa_passed=False),dict(source_sha256='a'*64),
                       dict(new_broad_section='1'),dict(independent_section_qa_sha256='a'*64),dict(section_proposals_sha256='a'*64),
                       dict(independent_section_qa_file='../escape.json')]:
            tampered=copy.deepcopy(actual);tampered[0].update(change)
            with self.subTest(approval_tamper=change),patch.object(m,'js',side_effect=lambda p:tampered if p==approval_path else original_js(p)),self.assertRaises(ValueError):
                m.reviewed_section_decisions()
        proposals_path=ROOT/'source_batches/japan_scope/section_proposals.json';actual_props=original_js(proposals_path)
        for change in [dict(degree_rule_extended=True),dict(source_image_visually_verified=False),dict(new_exact_subsection='4'),
                       dict(source_printed_broad_section='理学'),dict(body_verified=False),dict(new_broad_section='1')]:
            tampered=copy.deepcopy(actual_props);tampered[0].update(change)
            with self.subTest(source_tamper=change),patch.object(m,'js',side_effect=lambda p:tampered if p==proposals_path else original_js(p)),self.assertRaises(ValueError):
                m.reviewed_section_decisions()
        forged=copy.deepcopy(decisions);forged[0]['member_key']=next(r['member_key'] for r in self.jp if r['broad_section_supported']=='1')
        with self.assertRaises(ValueError):m.japan([],{},[],forged)

    def test_exact_DOB_conflict_quarantine_preserves_both_claims_and_no_other_DOB(self):
        quarantines=m.reviewed_france_dob_quarantines()
        self.assertEqual(len(quarantines),1)
        person=next(r for r in self.fr if r['candidate_group_id']=='CTHS_112065')
        rows,accepted,gaps,_,summary=m.france([decision(person)],quarantines)
        after=next(r for r in rows if r['candidate_group_id']==person['candidate_group_id'])
        self.assertEqual((after['membership_accepted'],after['dob_accepted'],after['exact_dob_conflict'],after['accepted_dob_iso']),('1','0','1',''))
        self.assertEqual(after['exact_dob_claims'],'1882-01-13|1882-01-18')
        self.assertEqual(after['v10_previous_accepted_dob_iso'],'1882-01-13')
        self.assertEqual(after['v10_previous_exact_dob_claims'],person['exact_dob_claims'])
        self.assertNotIn(person['candidate_group_id'],{r['candidate_group_id'] for r in accepted})
        self.assertIn(person['candidate_group_id'],{r['candidate_group_id'] for r in gaps})
        self.assertEqual(summary['current']['dob_accepted'],743)
        for before,row in zip(self.fr,rows):
            if before['candidate_group_id']!=person['candidate_group_id']:
                for k in ['identity_accepted','dob_accepted','accepted_dob_iso','exact_dob_claims','exact_dob_conflict']:
                    self.assertEqual(before[k],row[k])
        original_js=m.js;approval_path=ROOT/'inputs/france_dob_conflict_approvals.json';actual=original_js(approval_path)
        for change in [dict(root_approved=False),dict(independent_qa_passed=False),dict(candidate_group_id=self.fr_gap['candidate_group_id']),
                       dict(baseline_accepted_dob_iso='1882-01-18'),dict(observed_competing_dates=['1882-01-13']),
                       dict(source_claims_sha256='a'*64),dict(independent_qa_sha256='a'*64),dict(sources_not_assumed_independent=False),
                       dict(independent_qa_file='/tmp/escape.json')]:
            tampered=copy.deepcopy(actual);tampered[0].update(change)
            with self.subTest(approval_tamper=change),patch.object(m,'js',side_effect=lambda p:tampered if p==approval_path else original_js(p)),self.assertRaises(ValueError):
                m.reviewed_france_dob_quarantines()
        forged=copy.deepcopy(quarantines);forged[0]['accepted_new_dob_iso']='1882-01-18'
        with self.assertRaises(ValueError):m.france([],forged)


if __name__ == '__main__':
    unittest.main()
