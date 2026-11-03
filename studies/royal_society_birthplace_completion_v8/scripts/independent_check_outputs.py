from pathlib import Path
from collections import Counter
import gzip,json,csv,hashlib
repo=Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_checkout');s=repo/'studies/royal_society_birthplace_completion_v8';prior=s.parent/'royal_society_birthplace_completion_v7';out=Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_v8_workers/final_qa')
def read(p):
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def cs(p):
 with p.open() as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=read(prior/'outputs/uk_birthplace_rows.jsonl.gz');rows=read(s/'outputs/uk_birthplace_rows.jsonl.gz');old={r['record_id']:r for r in base};new={r['record_id']:r for r in rows}
assert len(rows)==len(old)==len(new)==4983 and set(old)==set(new)
# v5 changes evidence only; even the geography-lookup identity layer must stay exactly as v4.
geo={'hemisphere','raw_birthplace','country','lat','lon','birthplace_source_grade','birthplace_source_urls','birthplace_source_url','birthplace_evidence_kind','birthplace_claim_excerpt','source_sha256','reason','northern_birthplace_candidate','southern_birthplace_separate','geographic_conflict_pending_review','geography_decision','birthplace_discrepancy_retained','birthplace_evidence_candidates','selected_birthplace_evidence'}
for rid,r in new.items():
 for k,v in old[rid].items():
  if k not in geo:assert r.get(k)==v,(rid,k)
 assert r['dob']==old[rid]['dob'] and r['lookup_qid']==old[rid]['lookup_qid'] and r['wikidata_qid']==old[rid]['wikidata_qid']
 for c in r['birthplace_evidence_candidates']:
  f=c.get('birthplace_fact_evidence')
  if f and 'native_dob' in f:assert f['native_dob']==r['dob']
counts=Counter(r['hemisphere'] for r in rows);window=[r for r in rows if 1835<=int(r['dob'][:4])<=1985];assert len(window)==2644
nq=0
for b in base:
 r=new[b['record_id']]
 assert r.get('quarantined_birthplace_evidence_candidates')==b.get('quarantined_birthplace_evidence_candidates')
 for bad in b.get('quarantined_birthplace_evidence_candidates',[]):
  nq+=1;assert all(c['candidate_id']!=bad['candidate_id'] for c in r['birthplace_evidence_candidates'])
  assert not r['selected_birthplace_evidence'] or r['selected_birthplace_evidence']['candidate_id']!=bad['candidate_id']
  badqid=bad.get('qid') or b['lookup_qid']
  for c in r['birthplace_evidence_candidates']:
   assert c.get('qid')!=badqid
   assert not any('/'+badqid+'#P19' in u for u in c.get('source_urls',[]))
assert nq==9
assert not read(s/'inputs/current_lookup_replacements.jsonl.gz')
current=[r for r in rows if r['record_id'].startswith('RS_CURRENT_')]
active={'active':sum(bool(r.get('active_geography_lookup_qid')) for r in current),'quarantined':sum(bool(r.get('geography_lookup_qid_quarantined')) for r in current),'identity_pending':sum(bool(r.get('geography_lookup_identity_pending')) for r in current)}
assert len(current)==99 and active=={'active':94,'quarantined':2,'identity_pending':3}
reviews=read(s/'inputs/geographic_reviews.jsonl.gz');resolved=[r for r in reviews if r['hemisphere']!='unknown'];assert not reviews and not resolved
for p in resolved:
 b=old[p['record_id']];r=new[p['record_id']];assert r['hemisphere']==p['hemisphere']=='north'
 assert r['country']=='' and r['lat'] is None and r['lon'] is None
 c=next(c for c in r['birthplace_evidence_candidates'] if c.get('parent_candidate_id')==p['target_candidate_id'])
 assert c['source_grade']==b['selected_birthplace_evidence']['source_grade'] and c['geography']['geographic_resolution_source_grade']=='S3'
 assert c['v7_candidate_before_geographic_review']==b['selected_birthplace_evidence']
facts=read(s/'inputs/new_birthplace_facts.jsonl.gz');fids={f['record_id'] for f in facts};assert facts and len({(f['record_id'],tuple(f['source_urls']),f['raw_birthplace']) for f in facts})==len(facts)
for f in facts:
 assert f['native_dob']==old[f['record_id']]['dob'] and old[f['record_id']]['hemisphere']=='unknown'
 rc=[c for c in new[f['record_id']]['birthplace_evidence_candidates'] if c.get('birthplace_fact_evidence')==f]
 assert len(rc)==1 and rc[0]['source_grade']==f['source_grade'] and rc[0]['hemisphere']==f['hemisphere']
 assert len(rc[0].get('evidence_quote','').split())<=25
 assert f['geography']['geographic_resolution_source_grade']=='S3'
 assert new[f['record_id']]['country']=='' and new[f['record_id']]['lat'] is None and new[f['record_id']]['lon'] is None
assert len(facts)==len(fids)==6 and Counter(f['source_grade'] for f in facts)=={'S2':4,'S3':2}
first_bp=[rid for rid in fids if not old[rid]['birthplace_evidence_candidates']];prior_bp=[rid for rid in fids if old[rid]['birthplace_evidence_candidates']]
assert len(first_bp)==5 and prior_bp==['RS_PAST_NA1510']
assert old['RS_PAST_NA1510']['raw_birthplace']==new['RS_PAST_NA1510']['raw_birthplace']=='Lindley'
assert new['RS_PAST_NA1510']['selected_birthplace_evidence']==old['RS_PAST_NA1510']['selected_birthplace_evidence']
assert len(new['RS_PAST_NA1510']['birthplace_evidence_candidates'])==len(old['RS_PAST_NA1510']['birthplace_evidence_candidates'])+1
for rid in set(new)-fids:assert new[rid]==old[rid],(rid,'unaffected row modified')
for f in facts:
 if f['record_id'] in ['RS_PAST_NA1510','RS_PAST_NA3559']:
  assert f['source_grade']=='S3' and f['scan_visually_verified'] is False
 if f['record_id']=='RS_PAST_NA4658':
  assert f['source_birth_date_precision']=='month' and f['observed_source_birth_month']=='1940-06' and f['native_dob']=='1940-06-05'
home=new['RS_PAST_NA5449'];assert home['hemisphere']=='unknown' and home['birthplace_discrepancy_retained']
assert home['selected_birthplace_evidence']['birthplace_fact_evidence']['alternate_birthplace_evidence']==old[home['record_id']]['selected_birthplace_evidence']['birthplace_fact_evidence']['alternate_birthplace_evidence']
prevglobal=cs(prior/'outputs/all_country_birthplace_summary.csv');nowglobal=cs(s/'outputs/all_country_birthplace_summary.csv');assert len(prevglobal)==len(nowglobal)
for a,b in zip(prevglobal,nowglobal):
 if a['cohort']!='UK_Royal_Society':assert a==b
csvrows=cs(s/'outputs/uk_birthplaces.csv');assert len(csvrows)==4983 and Counter(r['hemisphere'] for r in csvrows)==counts
assert len(cs(s/'outputs/remaining_unknown.csv'))==counts['unknown']
for r in csvrows:assert r['dob']==old[r['record_id']]['dob']
summary=json.loads((s/'outputs/summary.json').read_text());assert summary['new_fact_people_first_explicit_birthplace']==5
assert summary['existing_geography_inventory']=={'prior_explicit_unresolved':54,'new_dedicated_reviews':0,'resolved_from_dedicated_reviews':0}
assert summary['hemisphere_counts']==dict(counts)
assert summary['previous_counts']==dict(Counter(r['hemisphere'] for r in base))
windowcounts=dict(Counter(r['hemisphere'] for r in window));assert summary['descriptive_existing_native_DOB_window_1835_1985']['hemisphere_counts']==windowcounts
newknown=[r['record_id'] for r in rows if old[r['record_id']]['hemisphere']=='unknown' and r['hemisphere']!='unknown'];reverted=[r['record_id'] for r in rows if old[r['record_id']]['hemisphere']!='unknown' and r['hemisphere']=='unknown']
assert len(newknown)==summary['previous_unknown_newly_classified'] and len(reverted)==summary['prior_known_reverted_to_unknown']
new_known_in_window=sum(1835<=int(new[rid]['dob'][:4])<=1985 for rid in newknown)
assert summary['new_fact_candidates']==len(facts) and summary['new_fact_unique_people']==len(fids)
assert summary['new_fact_people_classified']==sum(new[rid]['hemisphere']!='unknown' for rid in fids)
for p,d in summary['inputs_sha256'].items():assert sha(repo/p)==d
result={'status':'PASS','baseline_rows':4983,'all_preexisting_non_geography_fields_equal':True,'native_DOB_calendar_identity_eligibility_source_groups_and_historical_QIDs_unchanged':True,'geography_lookup_identity_layer_unchanged':True,'hemisphere_counts':dict(counts),'window_1835_1985_counts':windowcounts,'new_unknown_to_known':len(newknown),'newly_classified_people_in_window':new_known_in_window,'known_to_unknown':reverted,'dedicated_prior_geography_reviews':0,'new_fact_candidates':len(facts),'new_fact_unique_people':len(fids),'new_fact_people_classified':summary['new_fact_people_classified'],'new_fact_source_grades':dict(Counter(f['source_grade'] for f in facts)),'first_active_birthplace_facts_added':len(first_bp),'new_source_for_preexisting_Lindley_fact':True,'all4977_untouched_rows_completely_equal':True,'DNB_editable_transcription_grade_S3_no_scan_claim':True,'Pickett_Heaps_month_only_source_does_not_supply_or_change_day':True,'geography_resolution_grade_separate':'S3','current_lookup_state':active,'all9_old_quarantined_candidates_inactive':True,'Home_unknown_and_original_alternatives_retained':True,'other_country_rows_exactly_unchanged':True,'unknown_breakdown':dict(Counter('no_active_explicit_birthplace_evidence' if not r['birthplace_evidence_candidates'] else 'explicit_place_but_geography_unresolved' for r in rows if r['hemisphere']=='unknown')),'inputs_sha256':{str(p.relative_to(repo)):sha(p) for p in [s/'outputs/uk_birthplace_rows.jsonl.gz',s/'outputs/summary.json',s/'scripts/assemble.py']}}
(out/'independent_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
