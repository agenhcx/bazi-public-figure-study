#!/usr/bin/env python3
"""Bounded, birthplace-only geography overlay; does not execute prior workers."""
import argparse, collections, copy, datetime, gzip, hashlib, json, pathlib, re, sys, time, urllib.parse, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
WORKERS=ROOT.parent
PROJECT=WORKERS.parent
REPO=PROJECT/'uk_birthplace_checkout'
V2=REPO/'studies/royal_society_birthplace_completion_v2'
OLD=PROJECT/'uk_birthplace_v3_workers'
V4=PROJECT/'uk_birthplace_v4_workers'
V5=PROJECT/'uk_birthplace_v5_workers'
V6=PROJECT/'uk_birthplace_v6_workers'
V7=PROJECT/'uk_birthplace_v7_workers'
sys.path.insert(0,str(V2/'geography'))
from classify_birthplace import classify_place,norm,_point_sign

def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else p.open()) as f:return [json.loads(l) for l in f if l.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jdump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def subset_label(label,raw):return bool(norm(label)) and re.search(r'(?<!\w)'+re.escape(norm(label))+r'(?!\w)',norm(raw)) is not None

def literal_terms(raw):
 terms={raw.strip()}|{p.strip() for p in re.split(r',\s*',raw)}
 # Only remove literal locative prefixes, preserving the source's near/off
 # relation in the fact and in the geographic result. No unique birthpoint.
 terms |= {part.strip() for t in list(terms) for part in re.split(r'\s+in\s+|\s+on(?: the)?\s+',t)}
 terms |= {re.sub(r'^(?:near|in|at|then|the village of)\s+','',t,flags=re.I) for t in list(terms)}
 terms |= {re.sub(r'^\d+[A-Za-z]?\s+','',t) for t in list(terms)}
 return {t for t in terms if t and not re.search(r'\d',t) and not re.match(r'^(?:a|the) (?:small )?village$',t)}

def entity_place(qid,e,meta):
 claims=e.get('claims',{});cs=[]
 for c in claims.get('P625',[]):
  if c.get('rank')=='deprecated':continue
  v=c.get('mainsnak',{}).get('datavalue',{}).get('value',{})
  if isinstance(v,dict) and v.get('globe')=='http://www.wikidata.org/entity/Q2':cs.append({'claim_id':c.get('id'),'lat':v.get('latitude'),'lon':v.get('longitude'),'precision':v.get('precision'),'rank':c.get('rank'),'reference_count':len(c.get('references',[])),'globe':v.get('globe')})
 def values(prop):
  out=[]
  for c in claims.get(prop,[]):
   if c.get('rank')=='deprecated':continue
   v=c.get('mainsnak',{}).get('datavalue',{}).get('value',{})
   if isinstance(v,dict) and v.get('id'):out.append({'qid':v['id'],'claim_id':c.get('id'),'rank':c.get('rank'),'reference_count':len(c.get('references',[]))})
  return out
 return {'qid':qid,'label':e.get('labels',{}).get('en',{}).get('value'),'coordinates':cs,'country_claims_descriptive_only':values('P17'),'instance_of_claims':values('P31'),'source_response':meta}

def load_caches():
 places=json.loads(gzip.decompress((V2/'geography/existing_place_lookup.json.gz').read_bytes()))['places'];titles={}
 p=OLD/'new_facts_geography/anchor_place_entities.json';m=json.loads((p.parent/'anchor_place_entities_request.json').read_text())
 for qid,e in json.loads(p.read_text()).get('entities',{}).items():places[qid]=entity_place(qid,e,{'response_sha256':m['sha256'],'url':m['source_url'],'raw_response_file':'v3/audit/new_places_anchor_place_entities.json.gz'})
 for log in json.loads((OLD/'new_facts_geography/place_anchor_requests.json').read_text()):
  if not log.get('success'):continue
  parse_title_response(json.loads((OLD/'new_facts_geography'/log['file']).read_text()),log,titles,'v3/audit/new_fact_geography_sources.json.gz::')
 # Load v4 entity/title projections; source responses remain immutable.
 p=V4/'new_facts_geo/resolved_place_lookup.json'
 if p.exists():places.update(json.loads(p.read_text())['places'])
 p=V4/'new_facts_geo/resolved_anchor_titles.json'
 if p.exists():
  t4=json.loads(p.read_text())
  for row in t4.values():
   if row.get('response_file','').startswith('place_anchor_batch_'):row['response_file']='v4/new_facts_geo/'+row['response_file']
  titles.update(t4)
 # Same-round peer cache: geographic entities and explicit place articles only.
 p=V5/'geo48/geography_entities.json';mp=V5/'geo48/geography_entities_request.json'
 if p.exists() and mp.exists():
  m=json.loads(mp.read_text())
  if m.get('success'):
   for qid,e in json.loads(p.read_text()).get('entities',{}).items():places[qid]=entity_place(qid,e,{'response_sha256':m['response_sha256'],'url':m['source_url'],'raw_response_file':'v5/geo48/geography_entities.json'})
 p=V5/'geo48/geography_titles.json';mp=V5/'geo48/geography_titles_request.json'
 if p.exists() and mp.exists():
  m=json.loads(mp.read_text())
  if m.get('success'):
   log={'titles':m['requested_titles'],'source_url':m['source_url'],'sha256':m['response_sha256'],'file':'geography_titles.json'}
   parse_title_response(json.loads(p.read_text()),log,titles,'v5/geo48/')
 p=V6/'new_facts_geo/place_entities.json';mp=V6/'new_facts_geo/place_entities_request.json'
 if p.exists() and mp.exists():
  m=json.loads(mp.read_text())
  if m.get('success'):
   for qid,e in json.loads(p.read_text()).get('entities',{}).items():places[qid]=entity_place(qid,e,{'response_sha256':m['sha256'],'url':m['source_url'],'raw_response_file':'v6/new_facts_geo/place_entities.json'})
 return places,titles

def parse_title_response(blob,log,titles,prefix=''):
 q=blob.get('query',{});pages={p['title']:p for p in q.get('pages',[])}
 aliases={p:p for p in pages}
 for n in q.get('normalized',[])+q.get('redirects',[]):aliases[n['from']]=n['to']
 for title in log['titles']:
  t=title.replace('_',' ')
  for _ in range(8):
   if aliases.get(t,t)==t:break
   t=aliases[t]
  p=pages.get(t)
  if p and p.get('pageprops',{}).get('wikibase_item'):
   titles[title.replace('_',' ')]={'title':p['title'],'qid':p['pageprops']['wikibase_item'],'source_url':log['source_url'],'response_sha256':log['sha256'],'response_file':prefix+log['file']}

def request(url,path):
 meta={'source_url':url,'retrieved_utc':now(),'file':path.name,'success':False,'requests_retried':0}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BirthplaceEvidenceResearch/1.0'}),timeout=40) as r:raw=r.read();meta['http_status']=r.status
  path.write_bytes(raw);meta['sha256']=sha(path);meta['success']=True
 except Exception as e:meta['error']=type(e).__name__+': '+str(e)
 return meta

def all_links(f):
 result=list(f.get('birthplace_anchor_links',[]))
 for alt in f.get('alternate_birthplace_evidence',[]):result+=alt.get('birthplace_anchor_links',[])
 return result

def collect(facts,places,titles):
 targets=sorted({urllib.parse.unquote(a['url'].split('/wiki/',1)[1]).replace('_',' ') for f in facts if classify_place(f['raw_birthplace'])['hemisphere']=='unknown' for a in all_links(f) if '/wiki/' in a.get('url','')})
 missing=[t for t in targets if t not in titles]
 if len(missing)>50:missing=missing[:50]
 logs=[]
 for batch,start in enumerate(range(0,len(missing),50)):
  terms=missing[start:start+50];url='https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','prop':'pageprops','titles':'|'.join(terms),'format':'json','formatversion':2,'redirects':1})
  path=ROOT/f'place_anchor_batch_{batch}.json';log=request(url,path);log['titles']=terms;logs.append(log)
  if log['success']:parse_title_response(json.loads(path.read_text()),log,titles)
  if '429' in log.get('error',''):break
  time.sleep(1.1)
 jdump(ROOT/'place_anchor_requests.json',logs)
 qids=sorted({titles[t]['qid'] for t in targets if t in titles and (titles[t]['qid'] not in places or not places[titles[t]['qid']].get('coordinates'))})[:50]
 jdump(ROOT/'missing_place_qids.json',qids)
 if qids:
  url='https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode({'action':'wbgetentities','ids':'|'.join(qids),'props':'claims|labels|descriptions','languages':'en','format':'json','maxlag':5})
  p=ROOT/'place_entities.json';m=request(url,p)
  if m['success']:
   blob=json.loads(p.read_text())
   if 'error' in blob:m['api_error']=blob['error'];m['success']=False
   else:
    for qid,e in blob.get('entities',{}).items():places[qid]=entity_place(qid,e,{'response_sha256':m['sha256'],'url':url,'retrieved_utc':m['retrieved_utc'],'raw_response_file':p.name})
  jdump(ROOT/'place_entities_request.json',m)
 jdump(ROOT/'resolved_anchor_titles.json',titles)
 # Lookup is a projection of already-bound geographic entities, not a person search.
 jdump(ROOT/'resolved_place_lookup.json',{'places':places})
 return logs,qids

COUNTIES={'Q23204','Q23111','Q23240','Q23183','Q23082','Q23298','Q23159','Q23346','Q19186','Q23156','Q23148','Q23064','Q23098','Q23092','Q163','Q206934','Q23276','Q23140','Q650682'}

def classify_fact(fact,places,titles,wiki_by_id,allow_companion=True):
 if fact.get('route')=='crosswalk' and fact.get('geography',{}).get('frozen_place_evidence'):
  original=fact['geography'];place=original['frozen_place_evidence'];qid=place['qid']
  path=REPO/original['frozen_place_file']
  assert sha(path)==original['frozen_place_file_sha256']
  frozen=json.loads(gzip.decompress(path.read_bytes()))['places']
  assert frozen[qid]==place
  binding=fact.get('official_birth_fields',{}).get('place',{}).get('cityNow',{}).get('sameAs',[])
  assert 'https://www.wikidata.org/wiki/'+qid in binding
  sign,why=_point_sign(place)
  assert sign==original['hemisphere'] and sign!='unknown'
  assert original['country_assigned'] is False and original['birthpoint_coordinates_assigned'] is False
  assert original['lat'] is None and original['lon'] is None
  result=copy.deepcopy(original)
  result.update(reused_verified_frozen_geography=True,geographic_resolution_source_grade='S3',DOB_or_acceptance_modified=False,point_sign_replayed=why)
  return result
 if fact['record_id']=='RS_PAST_NA3559' and (ROOT/'hamilton_typed_town_context_review.json').exists():
  typed=json.loads((ROOT/'hamilton_typed_town_context_review.json').read_text())
  assert fact['raw_birthplace']==typed['raw_birthplace_unchanged'] and fact['source_sha256']==typed['source_sha256']
  assert all(c['point_hemisphere']=='north' for c in typed['compatible_settlement_candidates'])
  return {'hemisphere':'north','basis':typed['basis'],'geographic_resolution_source_grade':'S3','geography_evidence_kind':'S3_same_source_explicit_town_type_then_existing_exact_name_inventory','typed_source_context_review':typed,'no_unique_geographic_entity_selected':True,'country_assigned':False,'birthpoint_coordinates_assigned':False,'lat':None,'lon':None,'DOB_or_acceptance_modified':False}
 raw=fact['raw_birthplace'];base=classify_place(raw)
 # Report hemisphere only; no birth country or exact birthpoint is assigned.
 result={'hemisphere':base['hemisphere'],'basis':base['reason'],'geographic_resolution_source_grade':'S3','geography_evidence_kind':base['geography_evidence_kind'],'original_classifier_result':base,'geography_sources':[],'country_assigned':False,'birthpoint_coordinates_assigned':False,'lat':None,'lon':None,'DOB_or_acceptance_modified':False}
 if base.get('reason') in {'explicit_geographical_rules_cross_hemispheres','explicit_alternatives_unresolved_or_cross_hemispheres','at_sea_or_route_is_not_a_birth_country'}:
  return result
 if base['hemisphere']!='unknown':
  result['geography_sources']=[{'source_file':'v2/geography/geography_rules.json','source_sha256':sha(V2/'geography/geography_rules.json')},{'source_file':'v2/geography/existing_place_lookup.json.gz','source_sha256':sha(V2/'geography/existing_place_lookup.json.gz')}]
  return result
 links=[dict(a,companion=False) for a in fact.get('birthplace_anchor_links',[])]
 if allow_companion and fact['record_id'] in wiki_by_id:
  companion=wiki_by_id[fact['record_id']]
  links += [dict(a,companion=True,companion_source_url=companion['source_url'],companion_source_sha256=companion['source_sha256']) for a in companion.get('birthplace_anchor_links',[]) if subset_label(a['label'],raw)]
 witnesses=[]
 extents=json.loads((OLD/'extent/geography_sources.json').read_text())
 for a in links:
  if not subset_label(a.get('label',''),raw) or '/wiki/' not in a.get('url',''):continue
  title=urllib.parse.unquote(a['url'].split('/wiki/',1)[1]).replace('_',' ');t=titles.get(title)
  if not t or t['qid'] not in places:continue
  p=places[t['qid']];qid=t['qid'];w={'explicit_birthplace_link':a,'resolved_place_article':t,'place_entity':p,'place_entity_url':'https://www.wikidata.org/wiki/'+qid}
  if qid=='Q84':
   cpath=OLD/'localities/geographic_context_entities.json';london=json.loads(cpath.read_text())['entities']['Q84'];desc=london.get('descriptions',{}).get('en',{}).get('value','')
   if 'England' in desc:w.update(hemisphere='north',basis='explicit_link_identifies_London_England_inside_GB_extent',extent_sources=[extents['gb_extent']],location_description=desc,location_description_source_sha256=sha(cpath));witnesses.append(w)
  elif qid in COUNTIES:
   if 'Q145' in {c['qid'] for c in p.get('country_claims_descriptive_only',[])}:w.update(hemisphere='north',basis='explicit_linked_GB_historic_county_extent_not_centroid',extent_sources=[extents['gb_counties'],extents['gb_extent']]);witnesses.append(w)
  else:
   sign,why=_point_sign(p)
   if sign!='unknown':w.update(hemisphere=sign,basis='explicit_birthplace_link_exact_locality_QID_'+why);witnesses.append(w)
 # Review results are restricted to an exact full raw string or literal comma
 # component; raw parentheticals and regional qualifiers are not guessed.
 exact_path=ROOT/'exact_term_reviews.jsonl'
 if not witnesses and exact_path.exists():
  terms=literal_terms(raw)
  matched=[r for r in read(exact_path) if r['term'] in terms]
  reviewed=[r for r in matched if r['disposition']=='accepted']
  if matched:
   result['exact_name_geographic_reviews']=matched
   result.update(basis='bounded_exact_geographic_inventory_unresolved_or_cross_hemispheres',geography_evidence_kind='S3_exact_name_geographic_inventory_review_hold')
  if reviewed:
   signs={r['hemisphere'] for r in reviewed}
   if len(signs)==1:
    result.update(hemisphere=signs.pop(),basis='bounded_exact_birthplace_name_or_explicit_component_all_compatible_geographic_candidates_same_hemisphere',geography_evidence_kind='S3_exact_name_geographic_inventory_review')
    if any(r.get('unique_city_entity_resolved_from_qualified_historical_name_pair') for r in reviewed):
     result.update(no_unique_geographic_entity_selected=False,unique_city_entity_resolved_from_qualified_historical_name_pair=True,resolved_geographic_entity_qid='Q656')
    return result
 result['linked_place_witnesses']=witnesses;signs={w['hemisphere'] for w in witnesses}
 if len(signs)==1:result.update(hemisphere=next(iter(signs)),basis='all_supported_explicit_birthplace_linked_geographies_same_hemisphere',geography_evidence_kind='S3_explicit_birthplace_link_disambiguation_then_place_geography')
 elif len(signs)>1:result['basis']='explicit_birthplace_linked_geographies_conflict'
 return result

def build(facts,places,titles):
 wiki={f['record_id']:f for f in facts if f.get('birthplace_anchor_links')};out=[]
 for f in facts:
  g=classify_fact(f,places,titles,wiki);alts=f.get('alternate_birthplace_evidence',[])
  if alts:
   main=dict(g);ags=[classify_fact(dict(a,route=f['route'],record_id=f['record_id']),places,titles,wiki,False) for a in alts]
   g['alternative_results']=[{'raw_birthplace':f['raw_birthplace'],'geography':main}]+[{'raw_birthplace':a['raw_birthplace'],'geography':a_g} for a,a_g in zip(alts,ags)]
   signs={a['hemisphere'] for a in [main]+ags};g['place_alternatives_retained']=True
   if len(signs)==1 and 'unknown' not in signs:g.update(hemisphere=signs.pop(),basis='all_explicit_same_article_birthplace_alternatives_same_hemisphere')
   else:g.update(hemisphere='unknown',basis='explicit_same_article_birthplace_alternative_unresolved_or_conflicting')
  annotation={}
  if f['record_id']=='RS_PAST_NA5011' and g.get('unique_city_entity_resolved_from_qualified_historical_name_pair'):
   assert (f.get('native_dob') or f.get('dob'))=='1908-12-04'
   annotation={'no_unique_geographic_entity_selected':False,'unique_city_entity_resolved_from_qualified_historical_name_pair':True,
    'source_place_name_timing_discrepancy':{
     'flag':True,'native_dob_unchanged':'1908-12-04','source_place_wording_unchanged':f['raw_birthplace'],
     'recorded_Petrograd_official_name_period_years':[1914,1924],
     'geographic_name_period_source_entity':'Q27906714','geographic_name_period_source_properties':['P580','P582'],
     'note':'The native DOB precedes the recorded 1914–1924 Petrograd naming period, so the source phrase then Petrograd has a place-name timing discrepancy relative to the native date. The same physical city is resolved as Q656 and remains northern. This annotation does not adjudicate or change the source wording, native DOB or calendar.',
     'raw_source_quote_modified':False,'birthplace_source_grade_modified':False,'native_DOB_or_calendar_modified':False,
     'birthpoint_coordinates_assigned':False}}
  out.append({**annotation,'record_id':f['record_id'],'source_url':f['source_url'],'source_sha256':f['source_sha256'],'raw_birthplace':f['raw_birthplace'],'route':f['route'],'source_grade':f['source_grade'],'birthplace_source_grade':f['source_grade'],'geographic_resolution_source_grade':'S3','hemisphere':g['hemisphere'],'basis':g['basis'],'disposition':'accepted' if g['hemisphere']!='unknown' else 'held','geography':g,'native_dob':f.get('native_dob') or f.get('dob'),'DOB_or_native_acceptance_modified':False,'original_birthplace_fact':f})
 return out

def exact_collect(facts):
 # Literal component terms come only from explicit birthplace text, never from
 # a person's nationality, education, work or an inferred country.
 terms=sorted({part for f in facts if classify_place(f['raw_birthplace'])['hemisphere']=='unknown' for part in literal_terms(f['raw_birthplace'])})
 prior_terms=set()
 for p in [V7/'new_facts_geo/exact_term_reviews.jsonl']:
  if p.exists():
   prior_terms.update(r.get('term',r.get('raw_birthplace')) for r in read(p))
 terms=[t for t in terms if t not in prior_terms]
 jdump(ROOT/'exact_terms_selection.json',{'new_terms':terms,'reused_prior_terms':sorted(prior_terms),'no_prior_term_requeried':True})
 if not terms:return {'executed':False,'reason':'no_new_geographic_terms'}
 literals=' '.join(json.dumps(t,ensure_ascii=False)+'@en' for t in terms)
 query='SELECT DISTINCT ?needle ?place ?label ?description ?type ?typeLabel ?country ?coordStatement ?latitude ?longitude ?precision ?rank ?globe WHERE {\n VALUES ?needle { %s }\n ?place (rdfs:label|skos:altLabel) ?needle .\n OPTIONAL { ?place rdfs:label ?label FILTER(LANG(?label)="en") }\n OPTIONAL { ?place schema:description ?description FILTER(LANG(?description)="en") }\n OPTIONAL { ?place wdt:P31 ?type . OPTIONAL { ?type rdfs:label ?typeLabel FILTER(LANG(?typeLabel)="en") } }\n OPTIONAL { ?place wdt:P17 ?country }\n OPTIONAL { ?place p:P625 ?coordStatement . ?coordStatement psv:P625 ?cv; wikibase:rank ?rank . ?cv wikibase:geoLatitude ?latitude; wikibase:geoLongitude ?longitude; wikibase:geoPrecision ?precision; wikibase:geoGlobe ?globe . }\n}'%literals
 (ROOT/'exact_terms_query.rq').write_text(query)
 url='https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':query,'format':'json'})
 meta=request(url,ROOT/'exact_terms_response.json');meta.update(terms=terms,query_sha256=sha(ROOT/'exact_terms_query.rq'),no_limit=True,no_person_properties_requested=True)
 jdump(ROOT/'exact_terms_request.json',meta)
 return meta


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--collect',action='store_true');ap.add_argument('--exact-collect',action='store_true');a=ap.parse_args()
 paths={'australian_directory':WORKERS/'australian_directory/accepted.jsonl','historical_dnb':WORKERS/'historical_dnb/accepted.jsonl'}
 facts=[dict(f,route=route) for route,p in paths.items() if p.exists() for f in read(p)]
 places,titles=load_caches()
 if a.exact_collect:exact_collect(facts)
 if a.collect:collect(facts,places,titles)
 else:
  p=ROOT/'resolved_place_lookup.json'
  if p.exists():places=json.loads(p.read_text())['places']
  p=ROOT/'resolved_anchor_titles.json'
  if p.exists():titles=json.loads(p.read_text())
 out=build(facts,places,titles)
 for filename,rs in [('new_fact_geography.jsonl',out),('held_new_fact_geography.jsonl',[r for r in out if r['hemisphere']=='unknown'])]:
  data=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rs).encode();(ROOT/filename).write_bytes(data);(ROOT/(filename+'.gz')).write_bytes(gzip.compress(data,mtime=0))
 summary={'created_utc':now(),'input_sha256':{r:sha(p) for r,p in paths.items() if p.exists()},'script_sha256':sha(pathlib.Path(__file__)),'candidate_count':len(out),'qualified_historical_city_entity_resolutions':sum(bool(r.get('unique_city_entity_resolved_from_qualified_historical_name_pair')) for r in out),'source_place_name_timing_discrepancy_count':sum(bool(r.get('source_place_name_timing_discrepancy',{}).get('flag')) for r in out),'distinct_people':len({r['record_id'] for r in out}),'hemisphere_counts':dict(collections.Counter(r['hemisphere'] for r in out)),'people_with_supported_hemisphere':len({r['record_id'] for r in out if r['hemisphere']!='unknown'}),'by_route':{rt:dict(collections.Counter(r['hemisphere'] for r in out if r['route']==rt)) for rt in paths},'held':[{'record_id':r['record_id'],'raw_birthplace':r['raw_birthplace'],'source_url':r['source_url'],'basis':r['basis']} for r in out if r['hemisphere']=='unknown'],'output_sha256':sha(ROOT/'new_fact_geography.jsonl'),'DOB_or_native_acceptance_modified':False,'country_or_birthpoint_assigned':False,'no_person_queries':True,'network_bound':'at most one new exact-label query, one new place-pageprops query, and one at-most-50-QID entity request; no retries; no prior exact term requeried','network_requests_executed':{'place_pageprops':len(json.loads((ROOT/'place_anchor_requests.json').read_text())) if (ROOT/'place_anchor_requests.json').exists() else 0,'exact_name_geographic':int((ROOT/'exact_terms_request.json').exists()),'place_entity_api':int((ROOT/'place_entities_request.json').exists())}}
 jdump(ROOT/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
