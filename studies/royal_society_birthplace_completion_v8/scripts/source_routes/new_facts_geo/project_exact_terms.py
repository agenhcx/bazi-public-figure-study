#!/usr/bin/env python3
"""Project one bounded exact-label geographic query for explicit manual review."""
from pathlib import Path
import json,collections,math,hashlib
from build_geography import ROOT,_point_sign
meta=json.loads((ROOT/'exact_terms_request.json').read_text())
if not meta['success']:raise RuntimeError(meta)
g=collections.defaultdict(dict)
for r in json.loads((ROOT/'exact_terms_response.json').read_text())['results']['bindings']:
 term=r['needle']['value'];qid=r['place']['value'].split('/')[-1]
 x=g[term].setdefault(qid,{'qid':qid,'label':r.get('label',{}).get('value'),'description':r.get('description',{}).get('value'),'types':{},'country_claims_descriptive_only':{},'coordinates':{},'source_url':'https://www.wikidata.org/wiki/'+qid})
 if 'type' in r:x['types'][r['type']['value'].split('/')[-1]]=r.get('typeLabel',{}).get('value','')
 if 'country' in r:x['country_claims_descriptive_only'][r['country']['value'].split('/')[-1]]={'qid':r['country']['value'].split('/')[-1]}
 if 'latitude' in r:
  rank=r['rank']['value'].split('#')[-1];globe=r['globe']['value'];lat=float(r['latitude']['value']);precision=float(r['precision']['value'])
  c={'claim_id':r['coordStatement']['value'].split('/')[-1].replace('-','$',1),'statement_uri':r['coordStatement']['value'],'lat':lat,'lon':float(r['longitude']['value']),'precision':precision,'rank':rank,'globe':globe,'valid_direct_Earth_coordinate':rank!='DeprecatedRank' and globe=='http://www.wikidata.org/entity/Q2' and math.isfinite(lat) and math.isfinite(precision) and precision>=0 and abs(lat)>precision}
  x['coordinates'][c['claim_id']]=c
out=[]
for term in meta['terms']:
 candidates=[]
 for qid,x in sorted(g[term].items(),key=lambda y:int(y[0][1:])):
  x['instance_of_claims']=[{'qid':q,'label':label} for q,label in x.pop('types').items()];x['coordinates']=list(x['coordinates'].values());x['country_claims_descriptive_only']=list(x['country_claims_descriptive_only'].values())
  # Geographic proof uses only active valid Earth coordinates.
  active=dict(x,coordinates=[c for c in x['coordinates'] if c['valid_direct_Earth_coordinate']])
  sign,why=_point_sign(active);x['point_hemisphere']=sign;x['point_reason']=why;candidates.append(x)
 result={'term':term,'candidate_entities':candidates,'source_url':meta['source_url'],'source_sha256':meta['sha256'],'query_sha256':meta['query_sha256'],'no_limit':True,'no_unique_geographic_entity_selected':True}
 out.append(result)
(ROOT/'exact_term_candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in out))
for r in out:
 print('\nTERM',repr(r['term']))
 for x in r['candidate_entities']:
  print(x['qid'],repr(x['label']),repr(x['description']),';'.join(v.get('label','') or v['qid'] for v in x['instance_of_claims']),[(c['lat'],c['rank']) for c in x['coordinates']],x['point_hemisphere'],x['point_reason'])
