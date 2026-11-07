import unittest
from unittest.mock import patch
import wikidata_place_extent_adapter as adapter

def coordinate(lat,lon=1,precision=0.001):return {'lat':lat,'lon':lon,'precision':precision,'globe':'http://www.wikidata.org/entity/Q2','claim_id':'fixture','rank':'normal'}

def place(qid='Q999999999',label='fixture locality',coords=None,types=None,country=None):
 return {'qid':qid,'label':label,'coordinates':coords or [],'instance_of_claims':[{'qid':q} for q in types or []],'country_claims_descriptive_only':[{'qid':q} for q in country or []]}

class PlaceEntityTests(unittest.TestCase):
 def test_specific_London_entity_is_in_England_without_country_imputation(self):
  r=adapter.classify_wikidata_place_evidence(place('Q84','London',[coordinate(51.5)],['Q4835091'],['Q145']))
  self.assertEqual(r['hemisphere'],'north');self.assertEqual(r['extent_source']['anchor_qids'],['Q21']);self.assertIsNone(r['lat'])
 def test_new_opposite_coordinate_cannot_inherit_old_extent(self):
  r=adapter.classify_wikidata_place_evidence(place('Q84','London',[coordinate(-51.5)]))
  self.assertEqual(r['hemisphere'],'unknown');self.assertIn('contradicts',r['reason'])
 def test_P17_is_not_a_birth_country(self):
  r=adapter.classify_wikidata_place_evidence(place(country=['Q145']))
  self.assertEqual(r['hemisphere'],'unknown')
 def test_country_centroids_of_France_and_Brazil_are_not_used(self):
  for qid,label,lat in [('Q142','France',47),('Q155','Brazil',-10)]:
   with self.subTest(label=label):self.assertEqual(adapter.classify_wikidata_place_evidence(place(qid,label,[coordinate(lat)],['Q6256'],[qid]))['hemisphere'],'unknown')
 def test_wholly_one_hemisphere_label_extent_does_not_need_point(self):
  r=adapter.classify_wikidata_place_evidence(place('Q408','Australia',[],['Q6256'],['Q408']))
  self.assertEqual(r['hemisphere'],'south');self.assertIsNone(r['lat']);self.assertEqual(r['geographic_resolution_source_grade'],'S3')
 def test_multicoordinate_same_and_opposite_hemispheres(self):
  for coords,sign in [([coordinate(10),coordinate(11)],'north'),([coordinate(10),coordinate(-11)],'unknown')]:
   r=adapter.classify_wikidata_place_evidence(place(coords=coords));self.assertEqual(r['hemisphere'],sign)
   self.assertIsNone(r['lat'])
 def test_missing_precision_cannot_supply_direct_point(self):
  c=coordinate(10);c['precision']=None
  self.assertEqual(adapter.classify_wikidata_place_evidence(place(coords=[c]))['hemisphere'],'unknown')
 def test_missing_precision_can_be_resolved_by_independent_containing_extent(self):
  c=coordinate(51.5);c['precision']=None
  self.assertEqual(adapter.classify_wikidata_place_evidence(place('Q84','London',[c]))['hemisphere'],'north')
 def test_failed_entity_is_not_classified_from_label(self):
  p=place('Q408','Australia');p['error']='HTTP403'
  self.assertEqual(adapter.classify_wikidata_place_evidence(p)['hemisphere'],'unknown')

if __name__=='__main__':unittest.main()
