#!/usr/bin/env python3
"""Hold the sole new bare place name where physical geographic aliases cross hemispheres."""
from build_geography import ROOT,read
import json
prior=read(ROOT/'prior_exact_term_reviews.jsonl')
rows=read(ROOT/'exact_term_candidates.jsonl')
assert [r['term'] for r in rows]==['Falkirk']
for r in rows:
 signs={e['point_hemisphere'] for e in r['candidate_entities'] if e['point_hemisphere'] in {'north','south'}}
 assert signs=={'north','south'}
 assert any(e['qid']=='Q6797333' and e['point_hemisphere']=='south' for e in r['candidate_entities'])
 r.update(disposition='held',hemisphere='unknown',geographic_source_grade='S3',basis='exact_label_or_alias_physical_geographic_candidates_cross_hemispheres; northern_Falkirk_town_council_area_and_parish_plus_southern_Maylands_railway_station_Falkirk_alias; bare_birthplace_has_no_qualifier_to_select',
  no_unique_geographic_entity_selected=True,country_assigned=False,birthpoint_coordinates_assigned=False,
  candidate_completeness='One bounded exact English label/alias query without LIMIT; all returned alternatives retained, not an exhaustive global gazetteer. Physical railway/address candidates are retained, and no naming-period assumption is used to infer the source birthplace.')
assert not {r['term'] for r in rows}&{r['term'] for r in prior}
(ROOT/'new_exact_term_reviews.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
(ROOT/'exact_term_reviews.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in prior+rows))
print('Falkirk held: real physical name/alias candidates in both hemispheres')
