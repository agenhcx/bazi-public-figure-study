#!/usr/bin/env python3
"""Evaluate one explicit P19 place entity, independently of people or DOBs."""
from __future__ import annotations
from functools import lru_cache
import hashlib,importlib.util,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FROZEN_CLASSIFIER_SHA='8b8b894ee85deef97047691d9612f1b2cf21f1687d29e12fcc205468ce421a54'
EARTH={'http://www.wikidata.org/entity/Q2','https://www.wikidata.org/entity/Q2','Q2'}

@lru_cache(maxsize=1)
def _classifier():
 for path in (ROOT/'v3/classify_birthplace.py',ROOT/'classify_birthplace.py'):
  if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==FROZEN_CLASSIFIER_SHA:
   spec=importlib.util.spec_from_file_location('frozen_royal_society_geography_v3',path)
   mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
 raise RuntimeError('Frozen v3 classify_birthplace.py must be beside adapter (or v3/ in scratch).')

@lru_cache(maxsize=1)
def _approvals():
 return json.loads((ROOT/'wikidata_place_extent_approvals.json').read_text())

def _qid_values(values):
 out=set()
 for value in values or []:
  if isinstance(value,str):out.add(value)
  elif isinstance(value,dict) and value.get('qid'):out.add(value['qid'])
 return out

def classify_wikidata_place_evidence(place):
 """place uses v1/v2 qid,label,coordinates,instance_of_claims,P17 schema."""
 qid=place.get('qid','');label=place.get('label','')
 result={'qid':qid,'label':label,'hemisphere':'unknown','reason':'no_approved_geographic_resolution','authority':[],'coordinates_used':[],'coordinates_observed':place.get('coordinates') or [],'extent_source':None,'geographic_resolution_source_grade':'S3','P17_not_promoted_to_birth_country':True,'DOB_or_acceptance_modified':False,'lat':None,'lon':None}
 if place.get('error'):
  result['reason']='place_entity_fetch_error';return result
 mod=_classifier();label_geo=mod.classify_place(label);result['label_geography']=label_geo
 extent=_approvals()['approvals'].get(qid);result['extent_source']=extent
 if extent:
  source_by_file={s['response_file']:s for s in _approvals()['query_sources']}
  result['extent_query_sources']=[source_by_file[n] for n in extent['source_response_files']]
 label_sign=label_geo['hemisphere'];extent_sign=extent['hemisphere'] if extent else 'unknown'
 if extent and extent_sign=='unknown':
  result['reason']='geographical_extent_anchors_cross_hemispheres';return result
 spatial_signs={s for s in (label_sign,extent_sign) if s!='unknown'}
 if len(spatial_signs)>1:
  result['reason']='label_extent_and_P131_containment_disagree';return result
 # Inspect the supplied Earth coordinates even when precision is missing, so a
 # new southern point cannot silently inherit an old northern extent approval.
 observed_signs=set();valid=[];coordinate_skips=[]
 for c in place.get('coordinates') or []:
  if c.get('rank')=='deprecated':continue
  if c.get('globe') not in EARTH:
   coordinate_skips.append('non_earth_or_unstated_globe');continue
  lat=c.get('lat',c.get('latitude'));lon=c.get('lon',c.get('longitude'));prec=c.get('precision')
  if isinstance(lat,bool) or isinstance(lon,bool) or not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)) or not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:
   coordinate_skips.append('invalid_coordinate');continue
  if lat!=0:observed_signs.add('north' if lat>0 else 'south')
  if isinstance(prec,bool) or not isinstance(prec,(int,float)) or not math.isfinite(prec) or prec<0 or abs(lat)<=prec:
   coordinate_skips.append('precision_missing_or_touches_equator');continue
  valid.append(c)
 result['coordinate_skipped_reasons']=coordinate_skips
 if spatial_signs:
  spatial=next(iter(spatial_signs))
  if any(sign!=spatial for sign in observed_signs):
   result['reason']='observed_Earth_coordinate_contradicts_approved_extent';return result
  result['hemisphere']=spatial
  result['reason']='explicit_place_label_extent_or_spatial_P131_extent'
  if label_sign!='unknown':result['authority'].append({'kind':'explicit_place_label_geography','rule_ids':label_geo['rule_ids'],'resolution_kind':label_geo['geography_evidence_kind']})
  if extent_sign!='unknown':result['authority'].append({'kind':'geographic_P131_containment','anchor_qids':extent['anchor_qids']})
  # The accepted basis is the containing extent; no point is invented or used
  # to stand in for a country's area.
  return result
 types=_qid_values(place.get('instance_of_claims') or place.get('P31'))
 countries=_qid_values(place.get('country_claims_descriptive_only') or place.get('P17'))
 if types&mod.BROAD_TYPES or qid in countries:
  result['reason']='broad_place_without_approved_extent';return result
 if not valid:
  result['reason']='no_valid_direct_earth_coordinate_or_approved_extent';return result
 valid_signs={'north' if c.get('lat',c.get('latitude'))>0 else 'south' for c in valid}
 if len(valid_signs)!=1 or len(observed_signs)>1:
  result['reason']='direct_coordinate_alternatives_cross_hemispheres';return result
 result['hemisphere']=next(iter(valid_signs));result['reason']='all_valid_direct_Earth_coordinates_same_hemisphere';result['coordinates_used']=valid
 points={(c.get('lat',c.get('latitude')),c.get('lon',c.get('longitude'))) for c in valid}
 if len(points)==1:result['lat'],result['lon']=next(iter(points))
 result['authority'].append({'kind':'direct_Earth_P625_only','claim_ids':[c.get('claim_id') for c in valid]})
 return result
