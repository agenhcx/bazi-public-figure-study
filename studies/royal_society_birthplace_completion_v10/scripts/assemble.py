#!/usr/bin/env python3
"""Replay the v10 UK birthplace overlay from immutable local evidence inputs."""
from collections import Counter,defaultdict
from copy import deepcopy
from pathlib import Path
import argparse,csv,gzip,hashlib,importlib.util,json

GEO_FIELDS={'hemisphere','raw_birthplace','country','lat','lon','birthplace_source_grade','birthplace_source_urls','birthplace_source_url','birthplace_evidence_kind','birthplace_claim_excerpt','source_sha256','reason','northern_birthplace_candidate','southern_birthplace_separate','geographic_conflict_pending_review','geography_decision','birthplace_discrepancy_retained','birthplace_evidence_candidates','selected_birthplace_evidence','active_geography_lookup_qid','geography_lookup_qid_quarantined','geography_lookup_identity_pending','geography_lookup_identity_review'}

def read(p):
 with (gzip.open(p,'rt',encoding='utf-8') if str(p).endswith('.gz') else p.open(encoding='utf-8')) as f:return [json.loads(l) for l in f if l.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,rows):
 b=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows).encode();p.write_bytes(gzip.compress(b,mtime=0) if str(p).endswith('.gz') else b)
def cid(c):return hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!='candidate_id'},ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:20]

def assemble(s,out):
 repo=s.parents[1];prior=repo/'studies/royal_society_birthplace_completion_v9';choose_source=repo/'studies/royal_society_birthplace_completion_v3';bp=prior/'outputs/uk_birthplace_rows.jsonl.gz'
 assert sha(bp)=='e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
 spec=importlib.util.spec_from_file_location('v3_assembler',choose_source/'scripts/assemble.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 before=read(bp);old={r['record_id']:r for r in before};assert len(old)==len(before)==4983
 reviews=read(s/'inputs/geographic_reviews.jsonl.gz');facts=read(s/'inputs/new_birthplace_facts.jsonl.gz');links=read(s/'inputs/current_lookup_replacements.jsonl.gz')
 assert not reviews  # No repeated review of the already-audited held inventory this round.
 assert {r['record_id'] for r in reviews}<={r['record_id'] for r in before if r['hemisphere']=='unknown' and r['birthplace_evidence_candidates']}
 patches={r['record_id']:r for r in reviews if r['hemisphere']!='unknown'}
 additions=defaultdict(list)
 for f in facts:
  rid=f['record_id'];b=old[rid];assert f['native_dob']==b['dob']
  assert b['hemisphere']=='unknown'
  assert f['hemisphere'] in {'north','south','unknown'}
  c={'origin':f['origin'],'raw_birthplace':f['raw_birthplace'],'source_grade':f['source_grade'],'hemisphere':f['hemisphere'],
     'reason':f['geographic_basis'],'source_urls':f['source_urls'],'source_sha256':f.get('source_sha256',''),
     'evidence_quote':f.get('evidence_quote',''),'geography':f['geography'],'birthplace_fact_evidence':f,
     'birthplace_discrepancy_retained':bool(f.get('birthplace_discrepancy_retained',False))}
  if f.get('source_place_name_timing_discrepancy'):c['source_place_name_timing_discrepancy']=f['source_place_name_timing_discrepancy']
  c['candidate_id']=cid(c);additions[rid].append(c)
 replacements={r['record_id']:r for r in links}
 assert len(replacements)==len(links)
 rows=[];changes=[]
 for rid,b in old.items():
  r=deepcopy(b);candidates=deepcopy(b['birthplace_evidence_candidates']);reselect=False
  if rid in patches:
   g=patches[rid];assert g['raw_birthplace']==b['raw_birthplace'];assert g['native_dob']==b['dob']
   target=g['target_candidate_id'];assert target==b['selected_birthplace_evidence']['candidate_id']
   i=next(i for i,c in enumerate(candidates) if c['candidate_id']==target)
   assert candidates[i].get('source_sha256')==g['original_birthplace_source_sha256']
   lock=next(x for x in g['locked_candidates'] if x['candidate_id']==target)
   assert hashlib.sha256(json.dumps(candidates[i],ensure_ascii=False,sort_keys=True).encode()).hexdigest()==lock['candidate_sha256']
   c=deepcopy(candidates[i]);c['v9_candidate_before_geographic_review']=deepcopy(c)
   c.update(parent_candidate_id=target,hemisphere=g['hemisphere'],reason=g['basis'],geography=g)
   c['candidate_id']=cid(c);candidates[i]=c;reselect=True
  if rid in additions:candidates.extend(additions[rid]);reselect=True
  if rid in replacements:
   link=replacements[rid];assert link['identity_verified'] is True and link['native_dob']==b['dob']
   assert link['new_active_qid'] and link['new_active_qid']!=b.get('lookup_qid') or link.get('old_active_qid_supported')
   r['v10_lookup_replacement_evidence']=link
   r['v9_lookup_identity_review']=deepcopy(b.get('geography_lookup_identity_review'))
   r['geography_lookup_identity_review']={'identity_status_for_geography_only':'verified_exact_P2070_name_DOB_v10','lookup_qid':link['new_active_qid'],'evidence':link}
   r['v9_active_lookup_state']={k:b.get(k) for k in ['active_geography_lookup_qid','geography_lookup_qid_quarantined','geography_lookup_identity_pending']}
   r['active_geography_lookup_qid']=link['new_active_qid'];r['geography_lookup_qid_quarantined']=False;r['geography_lookup_identity_pending']=False
  if reselect:
   selected,decision,discrepancy=mod.choose(candidates)
   sign=selected['hemisphere'] if selected and not decision.endswith('_hold') else 'unknown'
   r['v9_geography_before_this_overlay']={k:deepcopy(b.get(k)) for k in GEO_FIELDS if k in b}
   r.update(hemisphere=sign,geography_decision=decision,birthplace_discrepancy_retained=discrepancy,
    birthplace_evidence_candidates=candidates,selected_birthplace_evidence=selected,
    raw_birthplace=selected['raw_birthplace'] if selected else '',country='',lat=None,lon=None,
    birthplace_source_grade=selected['source_grade'] if selected else 'unknown',
    birthplace_source_urls=selected['source_urls'] if selected else [],birthplace_source_url=' | '.join(selected['source_urls']) if selected else '',
    birthplace_evidence_kind=selected['origin'] if selected else 'unresolved',birthplace_claim_excerpt=selected.get('evidence_quote','') if selected else '',
    source_sha256=selected.get('source_sha256','') if selected else '',reason=selected.get('reason','') if selected else decision,
    northern_birthplace_candidate=sign=='north',southern_birthplace_separate=sign=='south',geographic_conflict_pending_review=decision.endswith('_hold'))
  assert all(r.get(k)==v for k,v in b.items() if k not in GEO_FIELDS),(rid,'nongeography mutation')
  if reselect or rid in replacements:
   changes.append({'record_id':rid,'name':r['name'],'dob':r['dob'],'before_hemisphere':b['hemisphere'],'after_hemisphere':r['hemisphere'],
    'before_raw_birthplace':b['raw_birthplace'],'after_raw_birthplace':r['raw_birthplace'],'birthplace_source_grade':r['birthplace_source_grade'],
    'lookup_replacement_verified':rid in replacements,'active_geography_lookup_qid':r.get('active_geography_lookup_qid','')})
  rows.append(r)
 rows.sort(key=lambda r:r['record_id']);out.mkdir(parents=True,exist_ok=True)
 dump(out/'uk_birthplace_rows.jsonl.gz',rows);dump(out/'changes.jsonl.gz',changes)
 fields=['record_id','name','source_authorised_full_name','dob','raw_birthplace','hemisphere','birthplace_source_grade','birthplace_source_url','geography_decision','birthplace_discrepancy_retained','geography_lookup_qid_quarantined','active_geography_lookup_qid','northern_birthplace_candidate','final_analysis_eligibility_assigned']
 for fn,items in [('uk_birthplaces.csv',rows),('remaining_unknown.csv',[r for r in rows if r['hemisphere']=='unknown']),('changed_records.csv',changes)]:
  with (out/fn).open('w',encoding='utf-8',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['record_id','name','dob','before_hemisphere','after_hemisphere','before_raw_birthplace','after_raw_birthplace','birthplace_source_grade','lookup_replacement_verified','active_geography_lookup_qid'] if fn=='changed_records.csv' else fields,extrasaction='ignore');w.writeheader();w.writerows(items)
 counts=Counter(r['hemisphere'] for r in rows);prev=Counter(r['hemisphere'] for r in before);unknown=[r for r in rows if r['hemisphere']=='unknown']
 window=[r for r in rows if 1835<=int(r['dob'][:4])<=1985];assert len(window)==2644
 summary={'schema':'royal_society_birthplace_completion_v10','baseline':4983,'previous_counts':dict(prev),'hemisphere_counts':dict(counts),
  'hemisphere_net_change':{k:counts[k]-prev[k] for k in ['north','south','unknown']},
  'previous_unknown_newly_classified':sum(old[r['record_id']]['hemisphere']=='unknown' and r['hemisphere']!='unknown' for r in rows),
  'prior_known_reverted_to_unknown':sum(old[r['record_id']]['hemisphere']!='unknown' and r['hemisphere']=='unknown' for r in rows),
  'existing_geography_inventory':{'prior_explicit_unresolved':sum(r['hemisphere']=='unknown' and bool(r['birthplace_evidence_candidates']) for r in before),'new_dedicated_reviews':0,'resolved_from_dedicated_reviews':0},
  'new_fact_candidates':len(facts),'new_fact_origin_counts':dict(Counter(f['origin'] for f in facts)),'new_fact_unique_people':len(additions),'new_fact_people_first_explicit_birthplace':sum(not old[rid]['birthplace_evidence_candidates'] for rid in additions),'new_fact_source_grade_counts':dict(Counter(f['source_grade'] for f in facts)),
  'new_fact_hemisphere_candidate_counts':dict(Counter(f['hemisphere'] for f in facts)),
  'new_fact_people_classified':sum(r['record_id'] in additions and r['hemisphere']!='unknown' for r in rows),
  'verified_lookup_replacements':len(links),'current_lookup_state':{'active':sum(bool(r.get('active_geography_lookup_qid')) for r in rows if r['record_id'].startswith('RS_CURRENT_')),'legacy_lookup_quarantined':sum(bool(r.get('geography_lookup_qid_quarantined')) for r in rows if r['record_id'].startswith('RS_CURRENT_')),'held_identity_unverified':sum(bool(r.get('geography_lookup_identity_pending')) for r in rows if r['record_id'].startswith('RS_CURRENT_'))},'unknown_breakdown':{'no_active_explicit_birthplace_evidence':sum(not r['birthplace_evidence_candidates'] for r in unknown),
   'explicit_place_but_geography_unresolved':sum(bool(r['birthplace_evidence_candidates']) for r in unknown)},
  'descriptive_existing_native_DOB_window_1835_1985':{'rows':2644,'hemisphere_counts':dict(Counter(r['hemisphere'] for r in window)),'not_new_calendar_or_final_cohort_adjudication':True},
  'source_grade_counts_for_selected_geography':dict(Counter(r['birthplace_source_grade'] for r in rows)),
  'native_DOB_calendar_identity_eligibility_fields_preserved':True,'birth_window_changed':False,'source_quality_DOB_groups_unchanged':True,
  'cross_cohort_deduplicated':False,'final_cohort_frozen':False,
  'inputs_sha256':{str(p.relative_to(repo)):sha(p) for p in [bp]+sorted((s/'inputs').glob('*'))}}
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 with (prior/'outputs/all_country_birthplace_summary.csv').open() as f:globalrows=list(csv.DictReader(f))
 for g in globalrows:
  if g['cohort']=='UK_Royal_Society':
   for k in ['north','south','equator','unknown']:g[k]=counts[k]
   g['source_snapshot']='royal_society_birthplace_completion_v10'
 with (out/'all_country_birthplace_summary.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(globalrows[0]));w.writeheader();w.writerows(globalrows)
 return summary

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path)
 a=p.parse_args();print(json.dumps(assemble(a.study,a.output or a.study/'outputs'),ensure_ascii=False))
