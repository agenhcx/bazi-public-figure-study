from pathlib import Path
import gzip,json,hashlib,datetime
from identity_matcher import parts,full_name_matches,route_name_aliases
B=Path(__file__).parent;P=Path('uk_birthplace_checkout/studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz');BS='8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356';assert hashlib.sha256(P.read_bytes()).hexdigest()==BS
rows=[json.loads(l)for l in gzip.open(P,'rt')];nas=[r for r in rows if r['cohort']=='NAS'];unknown=[r for r in nas if r['hemisphere']=='unknown'];assert len(nas)==2242 and len(unknown)==543
captures=json.loads((B/'captures.json').read_text());api=[]
for cap in captures:
 if cap.get('status')!=200:continue
 f=Path(cap['local_raw_path']);assert hashlib.sha256(f.read_bytes()).hexdigest()==cap['sha256'];j=json.loads(f.read_bytes())
 for i,obj in enumerate(j['laureates']):api.append({'category':cap['category'],'API_array_index':i,'object':obj,'capture':cap})
assert len(api)==len({x['object']['id']for x in api}) # this evidence union contains no repeated API person ID

def preferred_alias_exception(r,s):
 # Named root-adjudicated exception, not a generalized alias expansion rule.
 if r['name']!='Bruce Merrifield' or s.get('id')!='261' or s.get('knownName',{}).get('en')!=r['name']:return False
 full=s.get('fullName',{}).get('en','');fam=s.get('familyName',{}).get('en','');a=parts(r['name']);b=parts(full);f=parts(fam)
 if full!='Robert Bruce Merrifield' or not f or a[-len(f):]!=f or b[-len(f):]!=f:return False
 pos=0
 for t in a:
  while pos<len(b) and b[pos]!=t:pos+=1
  if pos==len(b):return False
  pos+=1
 return True

def matches(r,s):return full_name_matches(r['name'],s) or ([{'field':'knownName.en explicit root-adjudicated preferred-name alias','value':s['knownName']['en'],'fullName_proof':s['fullName']['en']}] if preferred_alias_exception(r,s) else [])
def forward(r):return[x for x in api if x['object'].get('birth',{}).get('date')==r['dob']and matches(r,x['object'])]
coverage=[];candidates=[];holds=[]
for r in unknown:
 route=[(a,route_name_aliases(r['name'],a['object']))for a in api if route_name_aliases(r['name'],a['object'])];entries=[]
 for a,aliases in route:
  s=a['object'];exact=s.get('birth',{}).get('date')==r['dob'];strict=matches(r,s);reverse=[z for z in nas if z['dob']==s.get('birth',{}).get('date')and matches(z,s)];fwd=forward(r)
  e={'API_category':a['category'],'API_array_index':a['API_array_index'],'API_id':s['id'],'API_fullName':s.get('fullName',{}).get('en'),'API_knownName':s.get('knownName',{}).get('en'),'API_familyName':s.get('familyName',{}).get('en'),'API_birth_date':s.get('birth',{}).get('date'),'matching_name_aliases':aliases,'all_known_native_name_parts_compatible':bool(strict),'strict_fullName_matches':full_name_matches(r['name'],s),'acceptance_name_proof':strict,'explicit_preferred_name_alias_exception':preferred_alias_exception(r,s),'knownName_only_not_sufficient':True,'exact_native_DOB_match':exact,'unique_API_objects_for_native_name_plus_DOB':len(fwd),'unique_NAS_rows_for_API_name_plus_DOB':len(reverse),'NAS_reverse_matches':[{'record_id':z['record_id'],'name':z['name'],'dob':z['dob']}for z in reverse],'birthplace_locationString_en':s.get('birth',{}).get('place',{}).get('locationString',{}).get('en',''),'birthplace_city_en':s.get('birth',{}).get('place',{}).get('city',{}).get('en',''),'birthplace_country_en':s.get('birth',{}).get('place',{}).get('country',{}).get('en',''),'source_sha256':a['capture']['sha256'],'source_url':a['capture']['requested_url'],'nobel_prize_context':[{'awardYear':p.get('awardYear'),'category':p.get('category',{}).get('en')}for p in s.get('nobelPrizes',[])]}
  if not strict:e['status']='hold_identity_exclusion_fullName_contradicts_or_does_not_establish_known_native_parts'
  elif not exact:e['status']='hold_exact_native_DOB_mismatch_no_DOB_adoption'
  elif len(fwd)!=1 or len(reverse)!=1 or reverse[0]['record_id']!=r['record_id']:e['status']='hold_bidirectional_identity_ambiguity'
  elif not e['birthplace_locationString_en']:e['status']='hold_no_literal_structured_birthplace_locationString'
  else:e['status']='candidate_two_anchor_unique'
  entries.append(e);item={'cohort':'NAS','record_id':r['record_id'],'name':r['name'],'native_dob':r['dob'],**e};(candidates if e['status']=='candidate_two_anchor_unique'else holds).append(item)
 coverage.append({'cohort':'NAS','record_id':r['record_id'],'name':r['name'],'native_dob':r['dob'],'baseline_sha256':BS,'API_objects_compared':len(api),'source_SHA256_by_category':{c['category']:c['sha256']for c in captures if c.get('status')==200},'routing_method':'NamedBruceMerrifieldexception:exactofficialknownName+allnativefullpartsorderedinfullNamewithsamefamily+exactDOB+bidirectionaluniqueness;otherwisefull/known/given-family may route only; allnativefulltokens must be compatible withAPI fullName.en; sourceinitialscannotestablishnativefulltoken; exactnativeDOB; bidirectionalunique; no QID','routes':entries,'status':'no_compatible_name_route'if not entries else'candidate_two_anchor_unique'if any(e['status']=='candidate_two_anchor_unique'for e in entries)else'hold_routed_conflict_or_ambiguity'})
for filename,data in [('coverage.jsonl',coverage),('candidate_analysis.jsonl',candidates),('candidate_holds_analysis.jsonl',holds)]:
 (B/filename).write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n'for x in data))
(B/'input_locks.json').write_text(json.dumps({'baseline':str(P),'baseline_sha256':BS,'baseline_count':len(rows),'NAS_count':len(nas),'unknown_NAS_count':len(unknown),'API_objects_total':len(api),'API_objects_unique_ids':len({x['object']['id']for x in api}),'current_lane_HTTP_requests':len(captures),'QIDs_used':False,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2))
print('COUNTS',{'API_objects':len(api),'candidates':len(candidates),'routed_holds':len(holds),'unknown_no_name_route':sum(not c['routes']for c in coverage)});print('CANDIDATES',json.dumps([{k:c[k]for k in['name','native_dob','API_fullName','birthplace_locationString_en','API_id','API_category']}for c in candidates],ensure_ascii=False));print('HOLDS',json.dumps([{k:c[k]for k in['name','native_dob','API_fullName','API_birth_date','status','API_id']}for c in holds],ensure_ascii=False))
