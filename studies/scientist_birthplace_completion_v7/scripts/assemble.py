#!/usr/bin/env python3
"""Apply frozen birthplace observations to the unchanged v6 person records."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import argparse, csv, gzip, hashlib, json, re

BASE_SHA = '8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356'
GEO_FIELDS = {'hemisphere', 'raw_birthplace', 'country', 'lat', 'lon',
 'birthplace_source_grade', 'birthplace_source_url', 'birthplace_source_urls',
 'birthplace_evidence_kind', 'birthplace_evidence_excerpt', 'birthplace_claim_excerpt',
 'birthplace_locator', 'birthplace_source_sha256', 'source_sha256', 'reason',
 'northern_birthplace_candidate', 'southern_birthplace_separate',
 'geographic_conflict_pending_review', 'place_alternatives_retained', 'locality_resolution'}
CSV_FIELDS = ['cohort','record_id','name','dob','raw_birthplace','hemisphere',
 'birthplace_source_grade','birthplace_source_url','country','lat','lon',
 'final_analysis_eligibility_assigned']
CHANGE_FIELDS = ['cohort','record_id','name','dob','before_hemisphere','after_hemisphere',
 'before_raw_birthplace','after_raw_birthplace','birthplace_source_grade']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 with (gzip.open(p, 'rt', encoding='utf-8') if str(p).endswith('.gz') else p.open(encoding='utf-8')) as f:
  return [json.loads(line) for line in f if line.strip()]
def dump(p, rows):
 data = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True)+'\n' for r in rows).encode()
 p.write_bytes(gzip.compress(data, mtime=0) if str(p).endswith('.gz') else data)
def key(r): return (r['cohort'], r['record_id'])
def baseline(s):
 repo=s.parents[1]
 p=repo/'studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz'
 assert sha(p)==BASE_SHA
 rows=read(p)
 assert len(rows)==len({key(r) for r in rows})==11094
 assert sum(r['cohort']=='UK_Royal_Society' for r in rows)==4983
 rows.sort(key=key)
 return rows,[p]
def write_csv(p, rows, fields):
 with p.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def assemble(s, out):
 before,basefiles=baseline(s);old={key(r):r for r in before}
 facts=read(s/'inputs/new_birthplace_facts.jsonl.gz')
 additions={key(f):f for f in facts};assert len(additions)==len(facts)
 rows=[];changes=[]
 for b in before:
  r=deepcopy(b);f=additions.get(key(b))
  if f:
   assert b['hemisphere']=='unknown' and f['native_dob']==b['dob']
   assert f['source_grade'] in {'S1','S2','S3'}
   assert f['hemisphere'] in {'north','south','unknown'}
   assert len(f['evidence_quote'].split())<=25
   assert f['geography']['country_assigned'] is False
   assert f['geography']['birthpoint_coordinates_assigned'] is False
   assert f['identity_independent_QA_passed'] is True
   r['v7_geography_before_overlay']={k:deepcopy(b[k]) for k in GEO_FIELDS if k in b}
   r['v7_birthplace_fact_evidence']=deepcopy(f)
   r['v7_geographic_review']=deepcopy(f['geography'])
   sign=f['hemisphere']
   r.update(hemisphere=sign,raw_birthplace=f['raw_birthplace'],country='',lat=None,lon=None,
    birthplace_source_grade=f['source_grade'],birthplace_source_url=' | '.join(f['source_urls']),
    birthplace_source_urls=f['source_urls'],birthplace_evidence_kind='v7_explicit_birthplace_source',
    birthplace_evidence_excerpt=f['evidence_quote'],birthplace_locator=f['evidence_locator'],
    birthplace_source_sha256=f['source_sha256'],reason=f['geographic_basis'],
    northern_birthplace_candidate=sign=='north',southern_birthplace_separate=sign=='south',
    geographic_conflict_pending_review=False)
   if 'locality_resolution' in b: r['locality_resolution']='hemisphere_only_from_explicit_source_qualifier' if sign!='unknown' else 'new_source_place_geography_held'
   changes.append({'cohort':r['cohort'],'record_id':r['record_id'],'name':r['name'],'dob':r['dob'],
    'before_hemisphere':b['hemisphere'],'after_hemisphere':sign,
    'before_raw_birthplace':b['raw_birthplace'],'after_raw_birthplace':r['raw_birthplace'],
    'birthplace_source_grade':f['source_grade']})
  assert all(r.get(k)==v for k,v in b.items() if k not in GEO_FIELDS),(key(r),'non-geographic mutation')
  if b['cohort']=='UK_Royal_Society': assert r==b
  rows.append(r)
 assert len(changes)==len(facts)
 out.mkdir(parents=True,exist_ok=True)
 dump(out/'birthplace_rows.jsonl.gz',rows);dump(out/'changes.jsonl.gz',changes)
 write_csv(out/'birthplaces.csv',rows,CSV_FIELDS)
 write_csv(out/'remaining_unknown.csv',[r for r in rows if r['hemisphere']=='unknown'],CSV_FIELDS)
 write_csv(out/'changed_records.csv',changes,CHANGE_FIELDS)
 countries=[]
 for cohort in sorted({r['cohort'] for r in rows}):
  subset=[r for r in rows if r['cohort']==cohort];prior=[r for r in before if r['cohort']==cohort]
  counts=Counter(r['hemisphere'] for r in subset);prev=Counter(r['hemisphere'] for r in prior)
  countries.append({'cohort':cohort,'baseline_rows':len(subset),
   **{x:counts[x] for x in ['north','south','equator','unknown']},
   'previous_unknown':prev['unknown'],'newly_classified':prev['unknown']-counts['unknown']})
 write_csv(out/'all_country_birthplace_summary.csv',countries,list(countries[0]))
 windows={}
 for c in countries:
  cohort=c['cohort'];subset=[r for r in rows if r['cohort']==cohort]
  observed=[r for r in subset if re.fullmatch(r'\d{4}-\d{2}-\d{2}',r.get('dob','') or '')]
  window=[r for r in observed if 1835<=int(r['dob'][:4])<=1985]
  windows[cohort]={'native_nonblank_day_rows':len(observed),'native_window_1835_1985_rows':len(window),
   'hemisphere_counts':dict(Counter(r['hemisphere'] for r in window)),
   'descriptive_only_not_calendar_eligibility_adjudication':True,
   'source_birth_years_not_used_to_fill_native_DOB_or_window':True}
 summary={'schema':'scientist_birthplace_completion_v7','cohort_records':11094,
  'unique_within_cohort_keys':11094,'unit':'cohort records; not cross-cohort independent persons',
  'direct_baseline':'scientist_birthplace_completion_v6','baseline_lineage':{'other_seven_cohorts':'v6 complete objects retaining v1 baseline and all v2/v3/v4/v5/v6 overlays',
   'UK_Royal_Society':'royal_society_birthplace_completion_v10','UK_baseline_rows':4983},
  'new_fact_candidates':len(facts),
  'retained_source_observation_count':sum(f.get('source_observation_count',1) for f in facts),
  'retained_source_observation_grade_counts':dict(Counter(o['source_grade'] for f in facts for o in f.get('source_observations',[{'source_grade':f['source_grade']}]))),
  'new_explicit_official_birthplace_facts':sum(f.get('fact_role')=='new_explicit_official_birthplace' for f in facts),
  'new_explicit_memoir_birthplace_facts':sum(f.get('fact_role')=='new_explicit_memoir_birthplace' for f in facts),
  'prior_birthplace_qualification_facts':sum(f.get('fact_role')=='prior_birthplace_qualification' for f in facts),
  'new_fact_source_grade_counts':dict(Counter(f['source_grade'] for f in facts)),
  'new_fact_cohort_counts':dict(Counter(f['cohort'] for f in facts)),
  'newly_classified':sum(c['newly_classified'] for c in countries),'country_summary':countries,
  'UK_all_4983_rows_preserved':True,'other_unchanged_rows':sum(r==old[key(r)] for r in rows),
  'all_existing_non_geographic_fields_preserved':True,'original_DOB_groups_unchanged':True,
  'CAS_Gregorian_acceptance_still_unadjudicated':True,
  'Nobel_655_reconstructed_ID_scope_not_original_final_DOB_restoration':True,
  'Nobel_native_DOBs_still_blank':all(r['dob']=='' for r in rows if r['cohort']=='Nobel_science'),
  'observed_native_DOB_windows':windows,'new_country_or_birthpoint_assignments':0,
  'cross_cohort_deduplicated':False,'final_cohort_frozen':False,'BaZi_or_outcomes_added':False,
  'inputs_sha256':{str(p.relative_to(s.parents[1])):sha(p) for p in basefiles+sorted((s/'inputs').glob('*'))}}
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 return summary

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path)
 a=p.parse_args();print(json.dumps(assemble(a.study,a.output or a.study/'outputs'),ensure_ascii=False))
