from pathlib import Path
import gzip,json,hashlib,re,unicodedata,datetime
B=Path('academy_v7_workers/nobel_physics');P=Path('uk_birthplace_checkout/studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz');S=Path('academy_v5_workers/geography/nobel_physics_corroboration_response.bin');BS='8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356';SS='633002ff83120f9408d630209b24ebab7d1f3f1e999cf5bb51638ebb8976075e'
assert hashlib.sha256(P.read_bytes()).hexdigest()==BS;assert hashlib.sha256(S.read_bytes()).hexdigest()==SS
rows=list(map(json.loads,gzip.open(P,'rt')));nas=[r for r in rows if r['cohort']=='NAS'];unknown=[r for r in nas if r['hemisphere']=='unknown'];api=json.loads(S.read_bytes())['laureates'];assert len(nas)==2242 and len(unknown)==543 and len(api)==230
from identity_matcher import parts,full_name_matches,route_name_aliases
def matches(r,s):return full_name_matches(r['name'],s)
def name_dob_matches(r):return [(i,s,matches(r,s)) for i,s in enumerate(api) if s.get('birth',{}).get('date')==r['dob'] and matches(r,s)]
coverage=[];candidates=[];conflicts=[]
for r in unknown:
 route=[(i,s,route_name_aliases(r['name'],s)) for i,s in enumerate(api) if route_name_aliases(r['name'],s)]
 entries=[]
 for i,s,aliases in route:
  exact=s.get('birth',{}).get('date')==r['dob'];reverse=[z for z in nas if z['dob']==s.get('birth',{}).get('date') and matches(z,s)];forward=name_dob_matches(r)
  e={'API_array_index':i,'API_id':s['id'],'API_fullName':s.get('fullName',{}).get('en'),'API_knownName':s.get('knownName',{}).get('en'),'API_birth_date':s.get('birth',{}).get('date'),'matching_name_aliases':aliases,'all_known_native_name_parts_compatible':bool(matches(r,s)),'strict_fullName_matches':matches(r,s),'knownName_only_not_sufficient':True,'exact_native_DOB_match':exact,'unique_API_objects_for_native_name_plus_DOB':len(forward),'unique_NAS_rows_for_API_name_plus_DOB':len(reverse),'NAS_reverse_matches':[{'record_id':z['record_id'],'name':z['name'],'dob':z['dob']} for z in reverse],'birthplace_locationString_en':s.get('birth',{}).get('place',{}).get('locationString',{}).get('en',''),'birthplace_city_en':s.get('birth',{}).get('place',{}).get('city',{}).get('en',''),'birthplace_country_en':s.get('birth',{}).get('place',{}).get('country',{}).get('en',''),'nobel_prize_context':[{'awardYear':p.get('awardYear'),'category':p.get('category',{}).get('en'),'motivation':p.get('motivation',{}).get('en')} for p in s.get('nobelPrizes',[])]}
  e['status']='candidate_two_anchor_unique' if exact and matches(r,s) and len(forward)==len(reverse)==1 and reverse[0]['record_id']==r['record_id'] else 'hold_identity_exclusion_date_mismatch' if not exact else 'hold_fullName_incompatible_or_ambiguous_identity'
  entries.append(e)
  item={'cohort':'NAS','record_id':r['record_id'],'name':r['name'],'native_dob':r['dob'],**e}
  (candidates if e['status']=='candidate_two_anchor_unique' else conflicts).append(item)
 coverage.append({'cohort':'NAS','record_id':r['record_id'],'name':r['name'],'native_dob':r['dob'],'baseline_sha256':BS,'source_sha256':SS,'API_objects_compared':len(api),'routing_method':'routing may use canonical full/known/given-family names; acceptance requires all known native full tokens compatible with API fullName.en (source initials cannot prove native full tokens); native initials may expand; explicit familyName; no QID','routes':entries,'status':'no_compatible_name_route' if not entries else 'candidate_two_anchor_unique' if any(e['status']=='candidate_two_anchor_unique' for e in entries) else 'hold_routed_conflict_or_ambiguity'})
for filename,data in [('all543_coverage.jsonl',coverage),('candidate_analysis.jsonl',candidates),('candidate_holds_analysis.jsonl',conflicts)]:
 with (B/filename).open('w') as f:
  for x in data:f.write(json.dumps(x,ensure_ascii=False)+'\n')
(B/'input_locks.json').write_text(json.dumps({'baseline':str(P),'baseline_sha256':BS,'baseline_count':len(rows),'NAS_count':len(nas),'unknown_NAS_count':len(unknown),'cached_API_source':str(S),'cached_API_source_sha256':SS,'cached_API_bytes':S.stat().st_size,'API_object_count':len(api),'current_lane_HTTP_requests':0,'QIDs_used':False,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2))
print('HIGH_CONFIDENCE_CANDIDATES',len(candidates));print(json.dumps([{'name':c['name'],'native_dob':c['native_dob'],'API_name':c['API_fullName'],'place':c['birthplace_locationString_en'],'id':c['API_id']} for c in candidates],ensure_ascii=False,indent=2));print('ROUTED_HOLDS',len(conflicts));print(json.dumps(conflicts,ensure_ascii=False,indent=2))
