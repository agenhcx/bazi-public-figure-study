import sys
sys.dont_write_bytecode = True
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v15_continue', ROOT / 'scripts/continue.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp, cls.claims, cls.queue, cls.jp_summary = m.previous_japan()
        cls.fr = m.readcsv(m.BASE / 'outputs/france_master877.csv')
        cls.by = {r['candidate_group_id']: r for r in cls.fr}

    def test_complete_predecessor_japan_claims_holds_and_calendar_outcomes(self):
        rows, claims, queue, summary = m.japan([], {}, [])
        self.assertEqual((rows, claims, queue), (self.jp, self.claims, self.queue))
        self.assertEqual((len(rows), len(claims), len(queue)), (482, 528, 112))
        self.assertEqual(summary['inherited_v14_raw_source_claim_rows'], 528)
        self.assertEqual(m.final_japan(), (rows, claims, queue, summary))
        holds=m.inherited_holds()
        self.assertEqual(len(holds), 46)
        releases = m.js(m.V12.ROOT / 'source_audits/v12_final_read_only_audit.json')['four_prior_calendar_releases_preserved']
        by = {r['member_key']: r for r in rows}
        self.assertEqual(len(releases), 4)
        for key, date in releases.items():
            self.assertEqual((by[key]['dob_status'], by[key]['source_date_components_iso']), ('body_day_no_known_conflict', date))
        for row in self.jp:
            if row['dob_status'].endswith('_hold'):
                self.assertEqual((holds[row['member_key']]['status'], holds[row['member_key']]['reason']), (row['dob_status'], row['dob_hold_note']))

    def test_empty_france_delta_keeps_every_field_and_both_full_histories(self):
        rows, accepted, gaps, history, summary = m.france([])
        self.assertEqual(rows, self.fr)
        self.assertEqual(history, m.readcsv(m.BASE / 'outputs/france_membership_decisions.csv'))
        self.assertEqual(m.france_case_adjudications(), m.readcsv(m.BASE / 'outputs/france_case_adjudications.csv'))
        self.assertEqual((len(history), len(m.france_case_adjudications())), (483, 32))
        self.assertEqual((len(accepted), len(gaps)), (639, 238))
        self.assertEqual(summary['current'], m.baseline_summary()['france']['current'])

    def test_machine_birthyear_hold_and_accepted_son_are_preserved(self):
        father = self.by['CTHS_102829']
        self.assertEqual(father['v12_dob_review_status'], m.UNRESOLVED_BIRTHYEAR_STATUS)
        self.assertEqual(father['v12_dob_review_observed_birthyears'], '[1862, 1867]')
        self.assertTrue(all(father[k+'_accepted'] == '0' for k in ('identity', 'dob', 'membership')))
        for key in ('CTHS_102829', 'CTHS_112057'):
            self.assertEqual({r['candidate_group_id']:r for r in m.france([])[0]}[key], self.by[key])
        with self.assertRaisesRegex(ValueError, 'Unresolved actual-source birthyear conflict'):
            m.france([dict(candidate_group_id='CTHS_102829')])
        with patch.object(m, 'birthyear_control', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Unresolved actual-source birthyear conflict'): m.block_unresolved_birthyear(father)

    def test_no_raw_dob_japan_activity_case_or_conflict_release_is_authorized(self):
        for args in (([self.claims[0]], {}, [], []), ([], {'x':{}}, [], []), ([], {}, ['x'], []), ([], {}, [], [{'member_key':'x'}])):
            with self.subTest(args=args), self.assertRaises(ValueError): m.japan(*args)
        with self.assertRaises(ValueError): m.france([], dob_quarantines=[{'candidate_group_id':'x'}])
        with self.assertRaises(ValueError): m.france_case_adjudications([{'candidate_group_id':'CTHS_128379'}])
        with self.assertRaises(ValueError): m.france([], individual_cases=m.V14.reviewed_individual_case_decisions())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'inputs').mkdir(); m.dump(root/'inputs/france_individual_case_approvals.json', [{'candidate_group_id':'CTHS_128379'}])
            with self.assertRaises(ValueError): m.reviewed_individual_case_decisions(root)

    def test_fixed_scope_is_a2_membership_only(self):
        self.assertEqual(m.selections(), {'japan':set(), 'france':{'CTHS_128379', 'PROFILE2_08407b6d0479b1d0'}})
        self.assertEqual(m.reviewed_individual_case_decisions(), [])
        self.assertEqual(m.js(ROOT/'inputs/batch_selection.json')['france_individual_case_proposal_files'], [])
        self.assertEqual(set(m.EXACT_MEMBERSHIP_ACCEPTANCES), {d['candidate_group_id'] for d in m.reviewed_membership_decisions() if str(d['membership_accepted'])=='1'})

    def test_selection_cardinality_identity_disjointness_and_path_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'inputs').mkdir(); (root/'selection_queues').mkdir()
            (root/'selection_queues/fr.csv').write_text('candidate_group_id\nCTHS_128379\n')
            config=dict(selection_frozen=True, japan=[], france=[dict(path='selection_queues/fr.csv',count=1)], expected_totals=dict(japan=0,france=1))
            def write(): m.dump(root/'inputs/selection_config.json',config)
            write(); self.assertEqual(m.selections(root)['france'], {'CTHS_128379'})
            for attack in ('overlap','cardinality','traversal','unknown'):
                c=copy.deepcopy(config)
                if attack=='overlap': c['france']*=2
                elif attack=='cardinality': c['france'][0]['count']=2
                elif attack=='traversal': c['france'][0]['path']='selection_queues/../fr.csv'
                else: (root/'selection_queues/fr.csv').write_text('candidate_group_id\nUNKNOWN\n')
                m.dump(root/'inputs/selection_config.json', c)
                with self.subTest(attack=attack), self.assertRaises(ValueError): m.selections(root)

    def test_predecessor_approvals_do_not_authorize_new_actions(self):
        with self.assertRaisesRegex(ValueError, 'exact reviewed source approvals'): m.france(m.V14.reviewed_membership_decisions())
        with self.assertRaisesRegex(ValueError, 'exact reviewed source approvals'): m.france_case_adjudications(m.V14.reviewed_individual_case_decisions())

    def test_predecessor_pin_includes_complete_histories(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'inputs').mkdir()
            prov=m.js(ROOT/'inputs/baseline_provenance.json'); prov['baseline_sha256']['outputs/france_case_adjudications.csv']='0'*64
            m.dump(root/'inputs/baseline_provenance.json',prov)
            with self.assertRaisesRegex(ValueError, 'Changed v14 baseline'): m.check_baseline(root)

    def test_source_processing_separates_not_searched_from_body_review(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'p.csv'; path.write_text('candidate_group_id,status\nx,not_searched\ny,pending\nz,body_reviewed_held\n')
            self.assertEqual(m.reviewed_ids(path,'candidate_group_id'), {'z'})
            path.write_text('candidate_group_id,status\nx,not_searched\nx,body_reviewed\n')
            with self.assertRaisesRegex(ValueError, 'Duplicate processing disposition'): m.reviewed_ids(path,'candidate_group_id')

    def test_prepare_contains_complete_claims_and_full_histories(self):
        prepared=m.prepare()
        self.assertEqual(prepared['japan_claims.json'], self.claims)
        self.assertEqual(len(prepared['inherited_france_decisions.json']), 483)
        self.assertEqual(len(prepared['inherited_france_case_adjudications.json']), 32)
        self.assertEqual(prepared['france_individual_case_decisions.json'], [])
        self.assertEqual(prepared['japan_delta_processed_ids.json'], [])
        self.assertEqual(set(prepared['france_processed_ids.json']), m.selections()['france'])

    def test_positive_membership_needs_actual_ordinary_subject_and_direct_start(self):
        positives=[d for d in m.reviewed_membership_decisions() if str(d['membership_accepted'])=='1']
        for d in positives:
            before=self.by[d['candidate_group_id']]
            m.validate_france_positive(d,before)
            for changes in (dict(role='foreign_associate'),dict(role='correspondent'),dict(event_year_is_relative=True),dict(event_type='reception_as_of'),dict(event_subject_role='author'),dict(source_role='secondary_reference'),dict(body_verified=False)):
                attack=copy.deepcopy(d)
                for e in attack['evidence']: e.update(changes)
                with self.subTest(candidate=d['candidate_group_id'],changes=changes), self.assertRaises(ValueError): m.validate_france_positive(attack,before)
            attack=copy.deepcopy(before); attack['election_date_conflict']='1'
            with self.assertRaisesRegex(ValueError,'Inherited France conflict'): m.validate_france_positive(d,attack)

    def test_exact_source_handoff_and_root_qa_cannot_self_expand(self):
        original=m.js
        for field in ('root_approved','independent_qa_passed','independent_qa_sha256','decisions_sha256','worker_manifest_sha256'):
            approvals=m.js(ROOT/'inputs/france_membership_approvals.json')
            if not approvals: continue
            approvals[0][field]=False if field in ('root_approved','independent_qa_passed') else '0'*64
            with self.subTest(field=field),patch.object(m,'js',side_effect=lambda p: approvals if p==ROOT/'inputs/france_membership_approvals.json' else original(p)):
                with self.assertRaises(ValueError): m.reviewed_membership_decisions()

    def test_production_keeps_every_identity_dob_raw_warning_and_history_prefix(self):
        decisions=m.reviewed_membership_decisions(); rows,_,_,ledger,summary=m.france(decisions)
        by={r['candidate_group_id']:r for r in rows}; changed={d['candidate_group_id'] for d in decisions}
        preserve=('identity_accepted','dob_accepted','accepted_canonical_person_name','accepted_dob_iso','exact_dob_claims','exact_dob_conflict','firstparty_day_claims','has_firstparty_day_claim','source_families','source_urls','review_flags','v12_dob_review_status','v12_dob_review_control_sha256','election_date_conflict')
        for old in self.fr:
            key=old['candidate_group_id']
            if key not in changed: self.assertEqual(by[key], old)
            for k in preserve: self.assertEqual(by[key][k],old[k],(key,k))
            for dimension in ('identity','dob','membership'):
                if old[dimension+'_accepted']=='1': self.assertEqual(by[key][dimension+'_accepted'],'1')
        nicole=by['PROFILE2_08407b6d0479b1d0']
        self.assertEqual((nicole['election_date_conflict'],nicole['v15_election_source_conflict_retained'],nicole['v15_election_source_conflict_status']), ('', '1', m.UNRESOLVED_ELECTION_SOURCE_STATUS))
        self.assertEqual(nicole['v15_election_source_observed_years'],[1982,2006])
        self.assertEqual(summary['inherited_formal_election_conflict_rows'],25)
        self.assertEqual(summary['new_actual_same_subject_election_source_conflict_rows'],1)
        self.assertEqual(summary['actual_same_subject_election_source_conflict_rows'],1)
        self.assertEqual(sum(r['election_date_conflict']=='1' for r in rows),25)
        self.assertEqual(sum(r['exact_dob_conflict']=='1' for r in rows),4)
        self.assertEqual(ledger[:483],m.readcsv(m.BASE/'outputs/france_membership_decisions.csv'))
        self.assertEqual([d['election_date_conflict'] for d in ledger[483:]], ['', ''])
        self.assertEqual(m.france_case_adjudications(),m.readcsv(m.BASE/'outputs/france_case_adjudications.csv'))
        self.assertEqual(summary['current']['identity_accepted'],787)
        self.assertEqual(summary['current']['dob_accepted'],775)

    def test_actual_election_source_hold_blocks_even_with_blank_legacy_flag_and_no_map(self):
        row=copy.deepcopy(self.by['PROFILE2_08407b6d0479b1d0'])
        self.assertEqual(row['election_date_conflict'], '')
        row['v15_election_source_conflict_status']=m.UNRESOLVED_ELECTION_SOURCE_STATUS
        with patch.object(m,'EXACT_SOURCE_ASSIGNMENT_CONTROLS',{}):
            with self.assertRaisesRegex(ValueError,'Unresolved actual same-subject election-source conflict'):
                m.block_unresolved_membership_source_conflict(row)
        positives=[d for d in m.reviewed_membership_decisions() if str(d['membership_accepted'])=='1']
        for d in positives:
            before=copy.deepcopy(self.by[d['candidate_group_id']]); before['v15_election_source_conflict_status']=m.UNRESOLVED_ELECTION_SOURCE_STATUS
            with self.assertRaisesRegex(ValueError,'Unresolved actual same-subject election-source conflict'):m.validate_france_positive(d,before)

    def test_same_subject_actual_source_year_conflict_cannot_select_a_date(self):
        decisions=m.reviewed_membership_decisions()
        qa=m.js(ROOT/m.EXACT_BATCH_HANDOFFS['france_a']['independent_qa_file'])
        held=next(d for d in decisions if d['candidate_group_id']=='PROFILE2_08407b6d0479b1d0')
        for changes in (dict(membership_accepted='1'),dict(accepted_full_member_election_year=1982),dict(accepted_full_member_election_date='1982-02-15')):
            attack=copy.deepcopy(held);attack.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):m.validate_source_assignment_disposition(attack,self.by[held['candidate_group_id']],qa)
        badqa=copy.deepcopy(qa)
        q=next(c for c in badqa['decision_checks'] if c['candidate_group_id']==held['candidate_group_id'])
        q['genuine_current_same_subject_year_conflict_held']=False
        with self.assertRaises(ValueError):m.validate_source_assignment_disposition(held,self.by[held['candidate_group_id']],badqa)

    def test_mixed_maternal_profile_cannot_replace_sole_own_subject_pdf_event(self):
        decisions=m.reviewed_membership_decisions()
        qa=m.js(ROOT/m.EXACT_BATCH_HANDOFFS['france_a']['independent_qa_file'])
        own=next(d for d in decisions if d['candidate_group_id']=='CTHS_128379')
        attack=copy.deepcopy(own);attack['evidence'][0]['source_sha256']='0'*64
        with self.assertRaises(ValueError):m.validate_source_assignment_disposition(attack,self.by[own['candidate_group_id']],qa)
        badqa=copy.deepcopy(qa)
        q=next(c for c in badqa['decision_checks'] if c['candidate_group_id']==own['candidate_group_id'])
        q['old_warnings_preserved']=False
        with self.assertRaises(ValueError):m.validate_source_assignment_disposition(own,self.by[own['candidate_group_id']],badqa)

    def test_output_replay_keeps_japan_bytes_and_collection_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'outputs'; summary=m.assemble(output)
            for name in m.INHERITED_CSV_FILES[:3]: self.assertEqual((output/name).read_bytes(),(m.BASE/'outputs'/name).read_bytes())
            self.assertEqual(summary['actual_processed_counts'],dict(japan=0,france=2))
            self.assertEqual(summary['existing_singleton_DOB_cases_approved'],0)
            self.assertFalse(summary['analysis_cohort_frozen'])
            self.assertEqual(summary['bazi_variables_computed'],0)
            self.assertEqual(summary['outreach_count'],0)
            self.assertEqual(summary['new_raw_DOB_claims'],0)
            with self.assertRaisesRegex(ValueError,'Fresh output directory'):m.assemble(output)


if __name__=='__main__': unittest.main()
