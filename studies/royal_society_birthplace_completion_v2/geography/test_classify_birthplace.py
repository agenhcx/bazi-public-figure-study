import unittest
from classify_birthplace import classify_place

class GeographicBoundaryTests(unittest.TestCase):
 def check(self,raw,expected):
  r=classify_place(raw);self.assertEqual(r['hemisphere'],expected,(raw,r));self.assertEqual(r['raw_birthplace'],raw);self.assertFalse(r['DOB_or_acceptance_modified'])
 def test_long_compounds_mask_inner_names(self):
  for raw,sign in [('New South Wales, Australia','south'),('North Island, New Zealand','south'),('South Georgia','south'),('New Britain','south'),('Netherlands East Indies','unknown'),('Dutch East Indies','unknown'),('Java, Dutch East Indies','south'),('Wales, United Kingdom','north')]:
   with self.subTest(raw=raw):self.check(raw,sign)
 def test_historical_extents(self):
  for raw,sign in [('British Guiana','north'),('Guyana','north'),('Ceylon','north'),('Cape Colony','south'),('Northern Rhodesia','south'),('Southern Rhodesia','south'),('South Korea','north'),('South India','north')]:
   with self.subTest(raw=raw):self.check(raw,sign)
 def test_ambiguous_naked_city_names_remain_unknown(self):
  for raw in ['Perth','Melbourne','Cambridge','Hamilton','Wellington','Camden','Richmond','London','Victoria','New England']:
   with self.subTest(raw=raw):self.check(raw,'unknown')
 def test_explicit_qualifiers_disambiguate(self):
  for raw,sign in [('Perth, Scotland','north'),('Perth, Western Australia','south'),('Cambridge, England','north'),('Cambridge, New Zealand','south'),('Victoria, British Columbia','north'),('Victoria, Australia','south')]:
   with self.subTest(raw=raw):self.check(raw,sign)
 def test_cross_equator_country_is_not_a_centroid(self):
  for raw in ['Indonesia','Brazil','Kenya','Uganda','Congo','Maldives','France','USA']:
   with self.subTest(raw=raw):self.check(raw,'unknown')
 def test_us_state_or_explicit_continent(self):
  self.check('Fulford, New York, United States, North and Central America','north')
  self.check('United States, North and Central America','north')
  self.check('United States, Oceania','unknown')
  self.check('United Kingdom','north')
  self.check('France, Europe','north')
  self.check('German Empire','unknown')
  self.check('German Empire, Europe','north')
 def test_place_of_birth_only_does_not_use_route_destination(self):
  self.check('At sea, on voyage to Australia','unknown');self.check('At sea, North Sea','north')
 def test_alternative_hemiagreement_and_conflict(self):
  self.check('England or Scotland','north');self.check('England or Australia','unknown');self.check('Indonesia or Japan','unknown')
 def test_country_qualified_point_lookup(self):
  self.check('Nairobi, Kenya','south');self.check('Paris, France','north')
 def test_homonym_country_context_uses_city_country(self):
  # No rule may turn a person/academy's implicit British context into geography.
  self.check('Camden, New South Wales, Australia','south')
  self.check('Camden, London, England','north')

 def test_exact_geographical_aliases_and_administrative_pairs(self):
  for raw in ['Bavaria','Surrey','Woking','Montréal','Saint-Lin','Bicester','Norwich','Carrickfergus','Wolverhampton','Austin, Texas','Shaftesbury, Dorset','Folkestone, Kent','Guernsey, Channel Islands','Douglas, Isle of Man']:
   with self.subTest(raw=raw):self.check(raw,'north')
  self.check('Copenhagen','unknown')

if __name__=='__main__':unittest.main()
