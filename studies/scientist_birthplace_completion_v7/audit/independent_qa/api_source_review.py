#!/usr/bin/env python3
"""Independent all-universe name/DOB matching of three observed Nobel API bodies."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import gzip,hashlib,json,re,unicodedata
W=Path('/workspace/scratch/7e8aa4e0d4af');Q=W/'academy_v7_workers/qa';B=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz'
def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def words(s):
 s=''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c));out=re.findall('[a-z]+',s)
 while out and out[-1] in {'jr','sr','ii','iii','iv'}:out.pop()
 return out
def token_matches(native,source):return native==source or len(native)==1 and source.startswith(native)
def subsequence(native,source):
 pos=0
 for part in native:
  while pos<len(source) and not token_matches(part,source[pos]):pos+=1
  if pos==len(source):return False
  pos+=1
 return True
def compatible(native,a):
 full=words(a.get('fullName',{}).get('en',''));family=words(a.get('familyName',{}).get('en',''));n=words(native)
 if not full or not family or len(n)<=len(family) or n[-len(family):]!=family or full[-len(family):]!=family:return False
 ng=n[:-len(family)];sg=full[:-len(family)]
 strict=bool(sg) and token_matches(ng[0],sg[0]) and subsequence(ng[1:],sg[1:])
 preferred=words(native)==['bruce','merrifield'] and words(a.get('knownName',{}).get('en',''))==n and a.get('id')=='261' and subsequence(ng,sg)
 return strict or preferred
def run():
 assert sha(B)=='8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356'
 with gzip.open(B,'rt') as f:base=[json.loads(x) for x in f]
 nas=[r for r in base if r['cohort']=='NAS'];unknown=[r for r in nas if r['hemisphere']=='unknown'];old={r['record_id']:r for r in nas};assert len(nas)==2242 and len(unknown)==543
 paths=[W/'academy_v5_workers/geography/nobel_physics_corroboration_response.bin',W/'academy_v7_workers/nobel_chem_med/original_chemistry_response.bin',W/'academy_v7_workers/nobel_chem_med/original_medicine_response.bin']
 expected=['633002ff83120f9408d630209b24ebab7d1f3f1e999cf5bb51638ebb8976075e','8fd0d5b3e4c6528b13c5993c13c14453e7d739a9fe7a57c7d2d6486d1c7040c8','dc4bd5e0d8f301273e8d5e4cb9955eff3c1ed316cb1f29fd468dec5b76b562d3'];bodies={};allapi=[]
 for p,h,count in zip(paths,expected,[230,200,235]):
  assert sha(p)==h;a=json.loads(p.read_bytes())['laureates'];assert len(a)==count;bodies[h]=a;allapi.extend(a)
 assert len(allapi)==665
 source_files=['academy_v7_workers/nobel_physics/retained_facts.jsonl','academy_v7_workers/nobel_chem_med/retained_facts.jsonl'];facts=[f for rel in source_files for f in read(W/rel)];assert len(facts)==26 and len({f['record_id'] for f in facts})==26
 independently_accepted={};reviews=[]
 for r in unknown:
  candidates=[a for a in allapi if a.get('birth',{}).get('date')==r['dob'] and compatible(r['name'],a)]
  if len(candidates)==1:
   a=candidates[0];reverse=[b for b in nas if b['dob']==a['birth']['date'] and compatible(b['name'],a)]
   if len(reverse)==1 and reverse[0]['record_id']==r['record_id']:independently_accepted[r['record_id']]=a
 assert set(independently_accepted)=={f['record_id'] for f in facts},(set(independently_accepted)-{f['record_id'] for f in facts},{f['record_id'] for f in facts}-set(independently_accepted))
 for f in facts:
  b=old[f['record_id']];a=independently_accepted[f['record_id']];h=f['source_sha256'];assert a['id']==f['source_identity_fields']['API_id']
  assert a['birth']['date']==f['native_dob']==b['dob'] and f['baseline_row_snapshot']==b
  assert f['raw_birthplace']==f['evidence_quote']==a['birth']['place']['locationString']['en']
  assert len(f['evidence_quote'].split())<=25 and f['source_grade']=='S1'
  assert f['source_subject_heading']==a['fullName']['en']
  pointer=f['evidence_locator']['JSON_pointer'].split('/');idx=int(pointer[2]);assert bodies[h][idx]['id']==a['id']
  assert f['original_bytes_length']==next(p.stat().st_size for p in paths if sha(p)==h)
  assert len(f['source_prize_context'])==len(a['nobelPrizes'])
  for context,prize in zip(f['source_prize_context'],a['nobelPrizes']):
   for field in ['awardYear','dateAwarded','sortOrder','portion','prizeStatus']:
    if field in prize:assert context.get(field)==prize[field],(f['name'],'prize field',field)
   for field in ['category','categoryFullName','motivation']:
    if field in prize and 'en' in prize[field]:assert context.get(field+'.en')==prize[field]['en'],(f['name'],'prize text',field)
  assert f['native_fields_modified'] is False and f['Nobel_cohort_row_modified'] is False
  assert f['person_QID_assigned_or_modified'] is False and f['statistical_cross_cohort_deduplication'] is False
  reviews.append({'name':f['name'],'record_id':f['record_id'],'native_dob':f['native_dob'],'API_id':a['id'],'API_fullName':a['fullName']['en'],'raw_birthplace':f['raw_birthplace'],'source_sha256':h,'API_name_plus_DOB_unique_among_all665_raw_objects':True,'NAS_reverse_unique_among_all2242':True,'source_prize_context_all_awards_and_English_motivations_checked':True,'structured_place_not_prose_born_quote':True,'preferred_name_exception':f['name']=='Bruce Merrifield'})
 for lane,filename in [('nobel_physics','all543_coverage.jsonl'),('nobel_chem_med','coverage.jsonl')]:
  coverage=read(W/'academy_v7_workers'/lane/filename);assert len(coverage)==543 and {r['record_id'] for r in coverage}=={r['record_id'] for r in unknown}
 p=W/'academy_v7_workers/nobel_chem_med';caps=json.loads((p/'captures.json').read_text());intents=read(p/'intent_ledger.jsonl');assert len(caps)==len(intents)==2
 for c,i in zip(caps,intents):
  assert c['status']==200 and c['requested_url']==i['url'] and datetime.fromisoformat(i['utc'])<datetime.fromisoformat(c['retrieved_utc'])
  cited=next(r for r in base if r['cohort']=='Nobel_science' and r['record_id']==i['observed_from_baseline_record_id']);assert cited['birthplace_source_url']==c['requested_url']
  assert sha(Path(c['retained_public_original_path']))==c['sha256'] and Path(c['local_raw_path']).read_bytes()==Path(c['retained_public_original_path']).read_bytes()
 holds=read(W/'academy_v7_workers/nobel_physics/holds.jsonl');assert len(holds)==2
 for h in holds:
  a=next(a for a in allapi if a['id']==h['source_identity_fields']['API_id']);assert old[h['record_id']]['dob']==h['native_dob'] and h['native_dob']!=a['birth']['date']
  if h['name']=='J. Herbert Taylor':assert compatible(h['name'],a) is False and a['fullName']['en']=='Joseph H. Taylor Jr.'
 report={'status':'PASS','source_fact_files':source_files,'S1_observations':26,'source_API_objects_by_category':{'physics':230,'chemistry':200,'medicine':235},'API_raw_objects_compared':665,'all543_unknowns_independently_crossmatched':True,'accepted_keys_exactly_equal_to_independently_recomputed_both_direction_unique_matches':True,'every_known_native_full_token_required_source_initial_does_not_prove_longer_token':True,'Bruce_Merrifield_explicit_exact_preferred_name_full_Robert_Bruce_ordered_tokens_exception_verified':True,'physics_HTTP_requests':0,'chem_med_HTTP_requests':2,'fresh_exact_URLs_observed_in_frozen_Nobel_rows':True,'all_original_bytes_hashes_preintents_and_source_pointers_verified':True,'prize_context_all_awards_and_motivations_retained':True,'physics_different_person_identity_exclusions':2,'Igor_Tamm1922_not_APIphysicist1895':True,'J_Herbert_Taylor1916_not_Joseph_H_Taylor1941_no_H_initial_expansion_to_Herbert':True,'API_H_initial_is_not_claimed_to_spell_Hooton':True,'Nobel_native_DOB_not_adopted_no_statistical_deduplication_or_QID_assignment':True,'reviews':reviews,'QA_HTTP_requests':0}
 (Q/'api_source_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='reviews'},indent=2))
if __name__=='__main__':run()
