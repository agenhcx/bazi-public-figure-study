"""Independent read-only v9 audit; replay artifacts are written only under qa/."""
import csv,gzip,hashlib,json,os,subprocess,sys
from collections import Counter
from pathlib import Path
Q=Path(__file__).resolve().parent; ROOT=Q.parents[1]; REPO=ROOT/'uk_birthplace_checkout'; STUDY=REPO/'studies/royal_society_birthplace_completion_v9'; PRIOR=REPO/'studies/royal_society_birthplace_completion_v8'; OUT=STUDY/'outputs'
GEO={'hemisphere','raw_birthplace','country','lat','lon','birthplace_source_grade','birthplace_source_urls','birthplace_source_url','birthplace_evidence_kind','birthplace_claim_excerpt','source_sha256','reason','northern_birthplace_candidate','southern_birthplace_separate','geographic_conflict_pending_review','geography_decision','birthplace_discrepancy_retained','birthplace_evidence_candidates','selected_birthplace_evidence','active_geography_lookup_qid','geography_lookup_qid_quarantined','geography_lookup_identity_pending','geography_lookup_identity_review'}
def read(p): return list(map(json.loads,gzip.open(p,'rt')))
def csvread(p): return list(csv.DictReader(p.open()))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def cv(v): return '' if v is None else str(v)
assert sha(PRIOR/'outputs/uk_birthplace_rows.jsonl.gz')=='b13ba1336b5912e58cfc38aa79aa668772ece189623f32a23625e67eaabd4c92'
before=read(PRIOR/'outputs/uk_birthplace_rows.jsonl.gz'); after=read(OUT/'uk_birthplace_rows.jsonl.gz'); old={r['record_id']:r for r in before}; new={r['record_id']:r for r in after}
assert len(before)==len(after)==len(old)==len(new)==4983 and old.keys()==new.keys()
expected={'RS_PAST_NA4156','RS_PAST_NA4641'}; changes=[]; diffs={}
for rid,b in old.items():
 r=new[rid]
 if r!=b: changes.append(rid)
 changed={k for k in b if r.get(k)!=b[k]}; added=set(r)-set(b)
 assert changed<=GEO,(rid,changed-GEO)
 assert added<={'v8_geography_before_this_overlay'},(rid,added)
 if changed: diffs[rid]={'changed_existing_fields':sorted(changed),'added_fields':sorted(added)}
 assert all(r[k]==v for k,v in b.items() if k not in GEO)
 assert r.get('active_geography_lookup_qid')==b.get('active_geography_lookup_qid')
 assert r.get('geography_lookup_identity_review')==b.get('geography_lookup_identity_review')
 assert r.get('quarantined_birthplace_evidence_candidates')==b.get('quarantined_birthplace_evidence_candidates')
 bad={c['candidate_id'] for c in r.get('quarantined_birthplace_evidence_candidates',[])}
 assert not bad & {c['candidate_id'] for c in r['birthplace_evidence_candidates']}
 assert all(c in r['birthplace_evidence_candidates'] for c in b['birthplace_evidence_candidates'])
 if rid in expected:
  assert b['hemisphere']=='unknown' and r['hemisphere']=='north' and not b['raw_birthplace']
  assert r['country']=='' and r['lat'] is None and r['lon'] is None
  assert len(r['birthplace_evidence_candidates'])==len(b['birthplace_evidence_candidates'])+1
 else: assert r==b
assert set(changes)==expected
assert dict(Counter(r['hemisphere'] for r in after))=={'north':4155,'south':183,'unknown':645}
window=[r for r in after if 1835<=int(r['dob'][:4])<=1985];assert len(window)==2644 and dict(Counter(r['hemisphere'] for r in window))=={'north':2255,'south':178,'unknown':211}
unknown=[r for r in after if r['hemisphere']=='unknown']; no_bp=sum(not r['birthplace_evidence_candidates'] for r in unknown); held=sum(bool(r['birthplace_evidence_candidates']) for r in unknown);assert (no_bp,held)==(591,54)
allcsv=csvread(OUT/'uk_birthplaces.csv'); unknowncsv=csvread(OUT/'remaining_unknown.csv'); changedcsv=csvread(OUT/'changed_records.csv'); changejson=read(OUT/'changes.jsonl.gz')
assert len(allcsv)==4983 and len(unknowncsv)==645 and len(changedcsv)==len(changejson)==2
for cr in allcsv+unknowncsv:
 r=new[cr['record_id']]; assert all(v==cv(r.get(k,'')) for k,v in cr.items()),cr['record_id']
assert {r['record_id'] for r in unknowncsv}=={r['record_id'] for r in unknown}
assert {r['record_id'] for r in changedcsv}==expected
for cr in changedcsv:
 r=next(r for r in changejson if r['record_id']==cr['record_id']);assert all(v==cv(r.get(k,'')) for k,v in cr.items())
summary=json.loads((OUT/'summary.json').read_text());assert summary['hemisphere_counts']==dict(Counter(r['hemisphere'] for r in after));assert summary['hemisphere_net_change']=={'north':2,'south':0,'unknown':-2};assert summary['previous_unknown_newly_classified']==2 and summary['prior_known_reverted_to_unknown']==0
assert summary['new_fact_candidates']==summary['new_fact_unique_people']==summary['new_fact_people_first_explicit_birthplace']==summary['new_fact_people_classified']==2
assert summary['new_fact_source_grade_counts']=={'S2':2};assert summary['unknown_breakdown']=={'no_active_explicit_birthplace_evidence':591,'explicit_place_but_geography_unresolved':54}
assert summary['current_lookup_state']=={'active':94,'legacy_lookup_quarantined':2,'held_identity_unverified':3};assert summary['verified_lookup_replacements']==0
assert summary['native_DOB_calendar_identity_eligibility_fields_preserved'] is True and summary['source_quality_DOB_groups_unchanged'] is True and summary['birth_window_changed'] is False
for name in ['geographic_reviews.jsonl.gz','current_lookup_replacements.jsonl.gz']:assert read(STUDY/'inputs'/name)==[]
for rel,h in summary['inputs_sha256'].items():assert sha(REPO/rel)==h
priorcountry=csvread(PRIOR/'outputs/all_country_birthplace_summary.csv'); nowcountry=csvread(OUT/'all_country_birthplace_summary.csv');assert [r for r in priorcountry if r['cohort']!='UK_Royal_Society']==[r for r in nowcountry if r['cohort']!='UK_Royal_Society']
uk=next(r for r in nowcountry if r['cohort']=='UK_Royal_Society'); assert uk['north']=='4155' and uk['south']=='183' and uk['unknown']=='645'
assert sum(len(r.get('quarantined_birthplace_evidence_candidates',[])) for r in after)==9
files=['uk_birthplace_rows.jsonl.gz','changes.jsonl.gz','uk_birthplaces.csv','remaining_unknown.csv','changed_records.csv','summary.json','all_country_birthplace_summary.csv']; assert set(p.name for p in OUT.iterdir() if p.is_file())==set(files)
replay=Q/'replay'; env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');subprocess.run([sys.executable,str(STUDY/'scripts/assemble.py'),'--output',str(replay)],env=env,check=True,capture_output=True)
replayed={fn:sha(OUT/fn) for fn in files}
for fn in files:assert (OUT/fn).read_bytes()==(replay/fn).read_bytes(),fn
report={'status':'PASS','rows':4983,'changed_rows':sorted(changes),'hemisphere_counts':dict(Counter(r['hemisphere'] for r in after)),'native_window_1835_1985_counts':dict(Counter(r['hemisphere'] for r in window)),'unknown_breakdown':{'no_explicit_birthplace':no_bp,'geography_held':held},'every_existing_non_geographic_field_equal':True,'unchanged_rows_identical':4981,'all_prior_candidates_preserved':True,'nine_quarantined_candidates_still_inactive':True,'active_lookup_state_94_supported_2_quarantined_3_held_unchanged':True,'all_csv_cells_consistent_with_json':True,'summary_and_input_hashes_verified':True,'other_country_rows_equal':True,'seven_output_byte_replay_sha256':replayed,'field_differences':diffs,'network_requests':0,'written_only_under_qa':True}
(Q/'final_audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
