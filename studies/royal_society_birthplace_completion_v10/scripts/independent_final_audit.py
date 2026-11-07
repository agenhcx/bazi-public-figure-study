"""Independent v10 output audit; no network; writes only qa/ and qa/replay/."""
import csv,gzip,hashlib,json,os,subprocess,sys
from collections import Counter,defaultdict
from pathlib import Path
Q=Path(__file__).resolve().parent; ROOT=Q.parents[1]; REPO=ROOT/'uk_birthplace_checkout'; S=REPO/'studies/royal_society_birthplace_completion_v10'; P=REPO/'studies/royal_society_birthplace_completion_v9'; O=S/'outputs'
GEO={'hemisphere','raw_birthplace','country','lat','lon','birthplace_source_grade','birthplace_source_urls','birthplace_source_url','birthplace_evidence_kind','birthplace_claim_excerpt','source_sha256','reason','northern_birthplace_candidate','southern_birthplace_separate','geographic_conflict_pending_review','geography_decision','birthplace_discrepancy_retained','birthplace_evidence_candidates','selected_birthplace_evidence','active_geography_lookup_qid','geography_lookup_qid_quarantined','geography_lookup_identity_pending','geography_lookup_identity_review'}
def read(p):return [json.loads(l) for l in gzip.open(p,'rt') if l.strip()]
def cr(p):return list(csv.DictReader(p.open()))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cv(v):return '' if v is None else str(v)
assert sha(P/'outputs/uk_birthplace_rows.jsonl.gz')=='e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
before=read(P/'outputs/uk_birthplace_rows.jsonl.gz');after=read(O/'uk_birthplace_rows.jsonl.gz');old={r['record_id']:r for r in before};new={r['record_id']:r for r in after};assert len(before)==len(after)==len(old)==len(new)==4983 and old.keys()==new.keys()
facts=read(S/'inputs/new_birthplace_facts.jsonl.gz');expected={f['record_id'] for f in facts};add=defaultdict(list)
for f in facts:
 assert f['native_dob']==old[f['record_id']]['dob'];assert f['source_grade']=='S2';assert len(f.get('evidence_quote','').split())<=25;add[f['record_id']].append(f)
for name in ['geographic_reviews.jsonl.gz','current_lookup_replacements.jsonl.gz']:assert read(S/'inputs'/name)==[]
changed=[];diffs={}
for rid,b in old.items():
 r=new[rid];d={k for k in b if r.get(k)!=b[k]};a=set(r)-set(b)
 if r!=b:changed.append(rid);diffs[rid]={'changed_existing_fields':sorted(d),'added_fields':sorted(a)}
 assert d<=GEO and a<={'v9_geography_before_this_overlay'}
 assert all(r.get(k)==v for k,v in b.items() if k not in GEO)
 for k in ['active_geography_lookup_qid','geography_lookup_identity_review','geography_lookup_qid_quarantined','geography_lookup_identity_pending','quarantined_birthplace_evidence_candidates']:assert r.get(k)==b.get(k)
 assert all(c in r['birthplace_evidence_candidates'] for c in b['birthplace_evidence_candidates'])
 bad={c['candidate_id'] for c in r.get('quarantined_birthplace_evidence_candidates',[])};assert not bad&{c['candidate_id'] for c in r['birthplace_evidence_candidates']}
 if b['hemisphere']!='unknown':assert r['hemisphere']==b['hemisphere']
 if rid in expected:
  assert b['hemisphere']=='unknown';assert r['country']=='' and r['lat'] is None and r['lon'] is None
  assert len(r['birthplace_evidence_candidates'])==len(b['birthplace_evidence_candidates'])+len(add[rid])
 else:assert r==b
assert set(changed)==expected
counts=Counter(r['hemisphere'] for r in after);priorcounts=Counter(r['hemisphere'] for r in before);window=[r for r in after if 1835<=int(r['dob'][:4])<=1985];assert len(window)==2644
unknown=[r for r in after if r['hemisphere']=='unknown']; no_bp=sum(not r['birthplace_evidence_candidates'] for r in unknown);held=sum(bool(r['birthplace_evidence_candidates']) for r in unknown)
allcsv=cr(O/'uk_birthplaces.csv');ucsv=cr(O/'remaining_unknown.csv');ccsv=cr(O/'changed_records.csv');cjson=read(O/'changes.jsonl.gz');assert len(allcsv)==4983 and len(ucsv)==counts['unknown'] and len(ccsv)==len(cjson)==len(expected)
for r in allcsv+ucsv:assert all(v==cv(new[r['record_id']].get(k,'')) for k,v in r.items())
assert {r['record_id'] for r in ucsv}=={r['record_id'] for r in unknown};assert {r['record_id'] for r in ccsv}==expected
for r in ccsv:assert all(v==cv(next(x for x in cjson if x['record_id']==r['record_id']).get(k,'')) for k,v in r.items())
s=json.loads((O/'summary.json').read_text());assert s['hemisphere_counts']==dict(counts);assert s['previous_counts']==dict(priorcounts);assert s['hemisphere_net_change']=={k:counts[k]-priorcounts[k] for k in ['north','south','unknown']}
assert s['previous_unknown_newly_classified']==sum(old[r['record_id']]['hemisphere']=='unknown' and r['hemisphere']!='unknown' for r in after);assert s['prior_known_reverted_to_unknown']==0
assert s['new_fact_candidates']==len(facts) and s['new_fact_unique_people']==len(expected);assert s['new_fact_source_grade_counts']==dict(Counter(f['source_grade'] for f in facts));assert s['new_fact_people_first_explicit_birthplace']==sum(not old[rid]['birthplace_evidence_candidates'] for rid in expected)
assert s['unknown_breakdown']=={'no_active_explicit_birthplace_evidence':no_bp,'explicit_place_but_geography_unresolved':held};assert s['current_lookup_state']=={'active':94,'legacy_lookup_quarantined':2,'held_identity_unverified':3};assert s['verified_lookup_replacements']==0
assert s['native_DOB_calendar_identity_eligibility_fields_preserved'] is True and s['source_quality_DOB_groups_unchanged'] is True and s['birth_window_changed'] is False
for rel,h in s['inputs_sha256'].items():assert sha(REPO/rel)==h
assert [r for r in cr(P/'outputs/all_country_birthplace_summary.csv') if r['cohort']!='UK_Royal_Society']==[r for r in cr(O/'all_country_birthplace_summary.csv') if r['cohort']!='UK_Royal_Society']
assert sum(len(r.get('quarantined_birthplace_evidence_candidates',[])) for r in after)==9
files=['uk_birthplace_rows.jsonl.gz','changes.jsonl.gz','uk_birthplaces.csv','remaining_unknown.csv','changed_records.csv','summary.json','all_country_birthplace_summary.csv'];assert set(p.name for p in O.iterdir() if p.is_file())==set(files)
replay=Q/'replay';env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');subprocess.run([sys.executable,str(S/'scripts/assemble.py'),'--output',str(replay)],env=env,check=True,capture_output=True)
for f in files:assert (O/f).read_bytes()==(replay/f).read_bytes(),f
report={'status':'PASS','rows':4983,'facts':len(facts),'changed_rows':sorted(changed),'unchanged_rows_identical':4983-len(changed),'hemisphere_counts':dict(counts),'native_window_1835_1985_counts':dict(Counter(r['hemisphere'] for r in window)),'unknown_breakdown':{'no_explicit_birthplace':no_bp,'geography_held':held},'every_existing_non_geographic_field_equal':True,'all_prior_candidates_preserved':True,'nine_quarantined_candidates_still_inactive':True,'lookup_state_94_2_3_unchanged':True,'all_csv_cells_consistent_with_json':True,'summary_and_input_hashes_verified':True,'other_country_rows_equal':True,'seven_output_byte_replay_sha256':{f:sha(O/f) for f in files},'field_differences':diffs,'network_requests':0,'written_only_under_qa':True};(Q/'final_audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
