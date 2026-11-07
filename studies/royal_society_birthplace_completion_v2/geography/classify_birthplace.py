#!/usr/bin/env python3
"""Classify an explicit birthplace field; never infer birthplace from a person."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from functools import lru_cache
import gzip,hashlib,json,math,re,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BROAD_TYPES={'Q6256','Q3624078','Q7275','Q3024240','Q3336843','Q15634554','Q161243','Q1048835','Q5107','Q35657','Q10864048','Q13220204','Q82794','Q4835091','Q28575','Q34876','Q149621','Q33837','Q23442','Q485258','Q20617590'}
US_STATES='Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia'.split('|')
SEAS_NORTH=('north sea','english channel','baltic sea','mediterranean sea','caribbean sea','gulf of mexico','red sea','persian gulf')

def norm(text):
 text=unicodedata.normalize('NFKC',str(text or '')).replace('\u2013','-').replace('\u2014','-').replace('\u2019',"'")
 return re.sub(r'\s+',' ',text).strip().casefold()

def pattern(text):
 return re.compile(r'(?<!\w)'+re.escape(norm(text)).replace(r'\ ',r'\s+')+r'(?!\w)')

@lru_cache(maxsize=1)
def rules():
 data=json.loads((ROOT/'geography_rules.json').read_text())
 aliases=[]
 for rule in data['rules']:
  for alias in rule['aliases']:aliases.append((norm(alias),pattern(alias),rule))
 aliases.sort(key=lambda item:len(item[0]),reverse=True)
 return data,aliases

@lru_cache(maxsize=1)
def point_lookup():
 lookup_path=ROOT/'existing_place_lookup.json.gz'
 if lookup_path.exists():data=json.loads(gzip.decompress(lookup_path.read_bytes()))
 else:data=json.loads((ROOT/'existing_place_lookup.json').read_text())
 aliases=defaultdict(set)
 for qid,place in data['places'].items():
  for label in [place.get('label','')]+place.get('aliases_en',[]):
   label=norm(label)
   if len(label)>1:aliases[label].add(qid)
 return data['places'],aliases

def _hits(text):
 hits=[];occupied=[]
 for alias,compiled,rule in rules()[1]:
  for m in compiled.finditer(text):
   if any(m.start()<end and start<m.end() for start,end in occupied):continue
   occupied.append(m.span());hits.append({'matched_text':text[m.start():m.end()],'span':list(m.span()),'rule_id':rule['id'],'hemisphere':rule['hemisphere'],'kind':rule['kind'],'country':rule['country'],'country_qid':rule['country_qid'],'geographic_basis':rule['geographic_basis']})
 return sorted(hits,key=lambda hit:hit['span'][0])

def _point_sign(place):
 types={c['qid'] for c in place.get('instance_of_claims') or []}
 if types&BROAD_TYPES or any(c['qid']==place['qid'] for c in place.get('country_claims_descriptive_only') or []):return 'unknown','broad_extent_not_point'
 coords=place.get('coordinates') or []
 if not coords:return 'unknown','no_direct_coordinate'
 signs=set()
 for c in coords:
  lat=c.get('lat');precision=c.get('precision')
  if isinstance(lat,bool) or not isinstance(lat,(int,float)) or not math.isfinite(lat) or not -90<=lat<=90:return 'unknown','invalid_latitude'
  if isinstance(precision,bool) or not isinstance(precision,(int,float)) or not math.isfinite(precision) or precision<0 or abs(lat)<=precision:return 'unknown','coordinate_precision_touches_equator_or_unknown'
  signs.add('north' if lat>0 else 'south')
 return (next(iter(signs)),'all_direct_coordinates_same_hemisphere') if len(signs)==1 else ('unknown','coordinate_alternatives_cross_hemispheres')

def _country_context(text,hits):
 contexts={h['country_qid'] for h in hits if h.get('country_qid') and h['kind']=='country_extent'}
 hints=rules()[0]['country_context_hints']
 # Full compound phrases mask inner country names here too.
 for h in hits:
  for alias,qid in hints.items():
   if norm(alias)==h['matched_text']:contexts.add(qid)
 return contexts

def _point_matches(text,contexts):
 if not contexts:return []
 places,aliases=point_lookup();matches=[];occupied=[]
 # Only exact stored labels/aliases, with explicitly supplied country context.
 for alias in sorted(aliases,key=len,reverse=True):
  for m in pattern(alias).finditer(text):
   if any(m.start()<end and start<m.end() for start,end in occupied):continue
   candidates=[]
   for qid in aliases[alias]:
    p=places[qid]
    if qid in contexts:continue
    countries={v['qid'] for v in p.get('country_claims_descriptive_only') or []}
    if not countries&contexts:continue
    sign,basis=_point_sign(p)
    candidates.append({'qid':qid,'label':p.get('label',''),'countries':sorted(countries),'hemisphere':sign,'reason':basis,'coordinates':p.get('coordinates') or [],'source_response':p.get('source_response',{})})
   if candidates:
    occupied.append(m.span());matches.append({'matched_alias':alias,'span':list(m.span()),'candidates':candidates})
 return matches

def classify_place(raw):
 """Return a reproducible annotation for a source's explicit birthplace string."""
 text=norm(raw)
 result={'raw_birthplace':str(raw or ''),'normalized_birthplace':text,'hemisphere':'unknown','reason':'unresolved_explicit_birthplace','rule_ids':[],'rule_matches':[],'point_matches':[],'country_context_qids':[],'lat':None,'lon':None,'geography_evidence_kind':'none','place_alternatives_retained':False,'input_must_be_explicit_birthplace':True,'DOB_or_acceptance_modified':False}
 if text in {'','-','--','n/a','na','unknown','not known','not recorded','?','unspecified','not stated'}:result['reason']='birthplace_field_empty_or_unknown';return result
 if re.search(r'\bat\s+sea\b|\baboard\b|\bon\s+board\b|\bvoyage\b|\ben\s+route\b',text):
  marine=[sea for sea in SEAS_NORTH if pattern(sea).search(text)]
  if marine:result.update(hemisphere='north',reason='explicit_named_sea_wholly_northern',rule_ids=['named_sea_north'],geography_evidence_kind='static_named_extent_rule')
  else:result['reason']='at_sea_or_route_is_not_a_birth_country'
  return result
 # Explicit alternatives must each be supported; a known Japan branch cannot
 # turn an unresolved Indonesia branch into a northern birth.
 alternatives=re.split(r'\s+(?:or|alternatively)\s+|\s*\|\s*',text)
 if len(alternatives)>1:
  parts=[classify_place(part) for part in alternatives]
  signs={p['hemisphere'] for p in parts}
  result['alternative_results']=parts;result['place_alternatives_retained']=True
  if len(signs)==1 and 'unknown' not in signs:result.update(hemisphere=signs.pop(),reason='all_explicit_birthplace_alternatives_same_hemisphere',geography_evidence_kind='alternative_place_extent_agreement')
  else:result['reason']='explicit_alternatives_unresolved_or_cross_hemispheres'
  return result
 hits=_hits(text);result['rule_matches']=hits;result['rule_ids']=[h['rule_id'] for h in hits]
 contexts=_country_context(text,hits);result['country_context_qids']=sorted(contexts)
 # Bare UK county rules cannot override an explicit Australian or other country
 # context. Subnational words may be reused globally as town names.
 strong=[h for h in hits if h['hemisphere']!='unknown' and (h['kind']!='contextless_county' or not contexts or contexts=={'Q145'})]
 if 'Q30' in contexts and any(pattern(state).search(text) for state in US_STATES):
  strong.append({'hemisphere':'north','rule_id':'US_country_plus_explicit_state','kind':'country_qualified_subregion'})
 signs={h['hemisphere'] for h in strong}
 if len(signs)>1:result['reason']='explicit_geographical_rules_cross_hemispheres';return result
 if signs:
  result.update(hemisphere=next(iter(signs)),reason='explicit_named_extent_wholly_one_hemisphere',geography_evidence_kind='S3_exact_geographical_alias_gazetteer' if any(h['kind']=='S3_exact_geographical_alias_gazetteer' for h in strong) else 'static_named_extent_rule')
  result['rule_ids']=list(dict.fromkeys(result['rule_ids']+[h['rule_id'] for h in strong]))
  return result
 matches=_point_matches(text,contexts);result['point_matches']=matches
 if matches:
  signs={c['hemisphere'] for m in matches for c in m['candidates']}
  if len(signs)==1 and 'unknown' not in signs:
   result.update(hemisphere=next(iter(signs)),reason='country_qualified_exact_place_alias_all_coordinates_same_hemisphere',geography_evidence_kind='S3_country_qualified_place_point_lookup')
   points={(c['lat'],c['lon']) for m in matches for p in m['candidates'] for c in p['coordinates']}
   result['place_alternatives_retained']=len(points)>1 or sum(len(m['candidates']) for m in matches)>1
   if len(points)==1:result['lat'],result['lon']=next(iter(points))
  else:result['reason']='matched_place_candidates_unresolved_or_cross_hemispheres'
 elif any(h['rule_id']=='unresolved_special_ambiguous' for h in hits):result['reason']='unqualified_ambiguous_locality'
 elif hits:result['reason']='country_or_region_does_not_determine_hemisphere'
 return result

def _read(path):
 opener=gzip.open if str(path).endswith('.gz') else open
 with opener(path,'rt',encoding='utf-8-sig') as f:return [json.loads(l) for l in f if l.strip()]

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--field',default='raw_placeofbirth');args=ap.parse_args()
 args.output.mkdir(parents=True,exist_ok=True);rows=[]
 for source in _read(args.input):
  raw=source.get(args.field) or source.get('raw_birthplace') or source.get('raw_place_of_birth') or ''
  geo=classify_place(raw);rows.append({**source,'geography':geo,'hemisphere':geo['hemisphere']})
 (args.output/'classified.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n' for row in rows))
 unresolved=Counter(r['geography']['raw_birthplace'] for r in rows if r['hemisphere']=='unknown')
 (args.output/'unresolved_unique_places.json').write_text(json.dumps([{'place':p,'people':n,'reason':classify_place(p)['reason']} for p,n in unresolved.most_common()],ensure_ascii=False,indent=2)+'\n')
 summary={'rows':len(rows),'hemisphere_counts':dict(Counter(r['hemisphere'] for r in rows)),'unique_unresolved_places':len(unresolved),'input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),'rules_sha256':hashlib.sha256((ROOT/'geography_rules.json').read_bytes()).hexdigest(),'lookup_sha256':hashlib.sha256((ROOT/'existing_place_lookup.json.gz' if (ROOT/'existing_place_lookup.json.gz').exists() else ROOT/'existing_place_lookup.json').read_bytes()).hexdigest()}
 (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
