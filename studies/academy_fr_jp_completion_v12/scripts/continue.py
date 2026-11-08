#!/usr/bin/env python3
"""Prepare, replay and verify reviewed v12 evidence against immutable v11 ledgers."""
import argparse
import collections
import copy
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
from urllib.parse import urlparse, parse_qs

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "academy_fr_jp_completion_v11"
BASE_COMMIT = "070239774f4fff72daea231e836796ef3ae8fc62"
spec = importlib.util.spec_from_file_location("academy_v11", BASE / "scripts/continue.py")
V11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V11)
V4, V3, J = V11.V4, V11.V3, V11.J
js, readcsv, require = V11.js, V11.readcsv, V11.require
HOLD_TYPES = {"calendar_hold": "source_calendar_hold", "formal_source_date_conflict": "source_date_conflict_hold", "source_quality_hold_unverified_competing_year": "source_quality_hold", "calendar_and_source_year_hold": "source_calendar_hold"}
HOLD_RANK = {"source_calendar_hold": 1, "source_caveat_hold": 2, "source_quality_hold": 3, "identity_assignment_hold": 4, "source_date_conflict_hold": 5}
ORDINARY_ROLES = {"ordinary_full_member", "ordinary_full_member_nonresident"}
ACADEMY_SOURCE_ROLES = {"firstparty", "first_party", "academy_firstparty", "firstparty_academy", "first_party_academy", "academy_authored", "academy_authored_original", "academy_authored_independent_host", "academy_authored_or_issued_original", "firstparty_academy_pdf", "firstparty_academy_notice", "academy_owned_firstparty", "parent_institution_firstparty"}
# Prior exact calendar decisions are applied by immutable V11.japan before v12
# replays its reviewed baseline directly. No new routing release is implicit.
EXACT_CALENDAR_ROUTING_RELEASES = {}
REVIEWED_ATTRIBUTED_SECONDARY_TIERS = set(V11.REVIEWED_ATTRIBUTED_SECONDARY_TIERS)


EXACT_SECTION_ACTIONS = {}
EXACT_FRANCE_DOB_QUARANTINE = {}
EXACT_COMPONENT_ACCEPTANCES = {'CTHS_100523': {'candidate_group_id': 'CTHS_100523', 'cths_parent_notice_sha256': 'c40e09d3da661e0f9e97c33194b5984238a4d58e851c00d8414ad12d1e914847', 'cths_expanded_biography_sha256': 'bfebe1f064a304ac822bb18353da9d1faa7bad6ca46f4dd0c134a2cacaede5a0', 'accepted_full_member_election_date': None, 'accepted_full_member_election_year': 1897, 'accepted_full_member_election_precision': 'year', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}, 'CTHS_104077': {'candidate_group_id': 'CTHS_104077', 'cths_parent_notice_sha256': 'e65d9df979d16a7d64ca9ef29f6c7bf9f5ae9fbb13c9b8415893dd1915a6fa92', 'cths_expanded_biography_sha256': 'e16f0d88353e49af3502b0ae451241a80227003815e4bb1152d5074294ac7d3d', 'accepted_full_member_election_date': None, 'accepted_full_member_election_year': 1923, 'accepted_full_member_election_precision': 'year', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}, 'CTHS_111937': {'candidate_group_id': 'CTHS_111937', 'cths_parent_notice_sha256': '94a64668e89ff16309c4c44e52ca49f15307b24ce121027c0e05da464835dd5a', 'cths_expanded_biography_sha256': '0525137f7df323361937e29bfb7fd591f601268c00ca9ac2a121b5e554b97f19', 'accepted_full_member_election_date': None, 'accepted_full_member_election_year': 1977, 'accepted_full_member_election_precision': 'year', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}, 'CTHS_112132': {'candidate_group_id': 'CTHS_112132', 'cths_parent_notice_sha256': '44b2f0b890c60cb9a652eac438fa49a6e651f17681bfa8e9efe3c91abe6cc3c4', 'cths_expanded_biography_sha256': 'bfff7bba9c51146d6e354a2ad1f9795a135710f8c48ec9f85a256ce65dda5e0d', 'accepted_full_member_election_date': None, 'accepted_full_member_election_year': 1955, 'accepted_full_member_election_precision': 'year', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}, 'CTHS_112272': {'candidate_group_id': 'CTHS_112272', 'cths_parent_notice_sha256': 'f1a0c9813cb1055996dc1b3c161c3e9347f02df6918e8c09650e092dee181137', 'cths_expanded_biography_sha256': 'ae34f4a91258e3d477c54b1db095896f05f49445d56f11e011ec6bda7e23d511', 'accepted_full_member_election_date': None, 'accepted_full_member_election_year': 1968, 'accepted_full_member_election_precision': 'year', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}, 'CTHS_112597': {'candidate_group_id': 'CTHS_112597', 'cths_parent_notice_sha256': '9fd0c11c8245d0e7743b3002b60aeb71e62ad5ce5c0bdfe6c85d0ad04b9156da', 'cths_expanded_biography_sha256': 'ffce5332e968bbf6dcb14667c0c0f77742db00748eca85c67534c5069fcec4f2', 'accepted_full_member_election_date': None, 'accepted_full_member_election_year': 1909, 'accepted_full_member_election_precision': 'year', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}, 'CTHS_112830': {'candidate_group_id': 'CTHS_112830', 'cths_parent_notice_sha256': 'c52ab9cc47e2bf10ee905adf69562a98aae025da645b2c68179ec16579c9be10', 'cths_expanded_biography_sha256': 'b686b4384f3ea65d38cce1870f5f80d0b4f62158409ca73a3a0b11d500f5b65b', 'accepted_full_member_election_date': None, 'accepted_full_member_election_year': 1924, 'accepted_full_member_election_precision': 'year', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}, 'CTHS_1958': {'candidate_group_id': 'CTHS_1958', 'cths_parent_notice_sha256': '0740a97cfdd631c3cb9c793226f24a778ab48c54a84f3e9866cee3252b8de005', 'cths_expanded_biography_sha256': '67e8a545da36d00a4097dda3df962f3f1f8ea2f42139ca1ad50d3cf960363cff', 'accepted_full_member_election_date': None, 'accepted_full_member_election_year': 1962, 'accepted_full_member_election_precision': 'year', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}, 'CTHS_2501': {'candidate_group_id': 'CTHS_2501', 'cths_parent_notice_sha256': '13070c0964562356d9290065ee2901bd82420471b0695eebfe22bcb5558e3ee0', 'cths_expanded_biography_sha256': 'd43b000f23ccdb07fc05e3d562b1f7cd3180904002ed5f63336adcd5eb9b8ab5', 'accepted_full_member_election_date': '1907-04-29', 'accepted_full_member_election_year': 1907, 'accepted_full_member_election_precision': 'day', 'decisions_sha256': '00b7a8347e8173cd5d69f7d59673c4443723491d03fbdf08686295658f8f9cab'}}
EXACT_INDIVIDUAL_CASE_ACCEPTANCES = {'PROFILE2_17029dcac8c2cc3d': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Sébastien Candel',
                                              'accepted_dob_iso': '1946-04-21'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_1b2dbc30512d1079': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Claude Debru',
                                              'accepted_dob_iso': '1944-12-03'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_2486d66ffc54fa60': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Eric Westhof',
                                              'accepted_dob_iso': '1948-07-25'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_3b4e1caf8ad114ce': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Sébastien Balibar',
                                              'accepted_dob_iso': '1947-10-14'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_42da8dfc3019dab0': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Jean Zinn-Justin',
                                              'accepted_dob_iso': '1943-07-10'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_4edc535226512431': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Antoine Triller',
                                              'accepted_dob_iso': '1952-05-23'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_641c979f606f9258': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Patrick Flandrin',
                                              'accepted_dob_iso': '1955-06-02'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_6744c2b4743540cb': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Jean-Claude Duplessy',
                                              'accepted_dob_iso': '1942-10-03'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_882455a0f94b93d5': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Édouard Bard',
                                              'accepted_dob_iso': '1962-09-01'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_8abc67336200a7a4': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Claire Voisin',
                                              'accepted_dob_iso': '1962-03-04'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_8b5e2b945f2490cc': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Jean-Claude Weill',
                                              'accepted_dob_iso': '1941-08-14'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_9c51a5b41eedae66': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Michel Haïssaguerre',
                                              'accepted_dob_iso': '1955-10-05'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_9ff6f4d54f4cc0cb': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Yves Bréchet',
                                              'accepted_dob_iso': '1961-10-12'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_afaef7ac7929999f': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Félix Rey',
                                              'accepted_dob_iso': '1957-11-22'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_c549e3f05efa1d6d': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Philippe Sautet',
                                              'accepted_dob_iso': '1961-05-08'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_ca0ee61296d82116': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Stephan Fauve',
                                              'accepted_dob_iso': '1955-12-20'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_e62494528ab515c3': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Joseph Sifakis',
                                              'accepted_dob_iso': '1946-12-26'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'PROFILE2_f741058fcd01768a': {'previous_values': {'identity_accepted': '0',
                                                   'dob_accepted': '0',
                                                   'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': ''},
                               'new_values': {'identity_accepted': '1',
                                              'dob_accepted': '1',
                                              'accepted_canonical_person_name': 'Clément Sanchez',
                                              'accepted_dob_iso': '1949-03-16'},
                               'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23'],
                               'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                               'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'CTHS_100245': {'previous_values': {'identity_accepted': '0',
                                     'dob_accepted': '0',
                                     'accepted_canonical_person_name': '',
                                     'accepted_dob_iso': ''},
                 'new_values': {'identity_accepted': '1',
                                'dob_accepted': '1',
                                'accepted_canonical_person_name': 'Philibert Guinier',
                                'accepted_dob_iso': '1876-06-21'},
                 'source_sha256s': ['94340445157c2df0f669fe451d302cc3a2e2aba865370b8cc8286d4efbb99e60'],
                 'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                 'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'CTHS_100326': {'previous_values': {'identity_accepted': '0',
                                     'dob_accepted': '0',
                                     'accepted_canonical_person_name': '',
                                     'accepted_dob_iso': ''},
                 'new_values': {'identity_accepted': '1',
                                'dob_accepted': '1',
                                'accepted_canonical_person_name': 'Maurice Caullery',
                                'accepted_dob_iso': '1868-09-05'},
                 'source_sha256s': ['bbdba513ebb2665d19744853bc44180fbf305fba0750d24336616250c49f4cd5'],
                 'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                 'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'CTHS_102817': {'previous_values': {'identity_accepted': '0',
                                     'dob_accepted': '0',
                                     'accepted_canonical_person_name': '',
                                     'accepted_dob_iso': ''},
                 'new_values': {'identity_accepted': '1',
                                'dob_accepted': '1',
                                'accepted_canonical_person_name': 'Gaston Eugène Marie Bonnier',
                                'accepted_dob_iso': '1853-04-09'},
                 'source_sha256s': ['3ec354826612b76824a6b9fef1034629e09e2af0ab599e8d30ec68188daadf7c'],
                 'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                 'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'CTHS_102822': {'previous_values': {'identity_accepted': '0',
                                     'dob_accepted': '0',
                                     'accepted_canonical_person_name': '',
                                     'accepted_dob_iso': ''},
                 'new_values': {'identity_accepted': '1',
                                'dob_accepted': '1',
                                'accepted_canonical_person_name': 'Charles René Zeiller',
                                'accepted_dob_iso': '1847-01-14'},
                 'source_sha256s': ['3a2f39ba8984a774b9da9d96254c38ca96d13ec53b7694bf76bd92951feae26e'],
                 'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                 'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'CTHS_102828': {'previous_values': {'identity_accepted': '0',
                                     'dob_accepted': '0',
                                     'accepted_canonical_person_name': '',
                                     'accepted_dob_iso': ''},
                 'new_values': {'identity_accepted': '1',
                                'dob_accepted': '1',
                                'accepted_canonical_person_name': 'Paul Henri Lecomte',
                                'accepted_dob_iso': '1856-01-08'},
                 'source_sha256s': ['8a432b1d17c971d982706c07c4e08bee9534ff4de270d57316c0a09135a0d79a'],
                 'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                 'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'CTHS_102843': {'previous_values': {'identity_accepted': '0',
                                     'dob_accepted': '0',
                                     'accepted_canonical_person_name': '',
                                     'accepted_dob_iso': ''},
                 'new_values': {'identity_accepted': '1',
                                'dob_accepted': '1',
                                'accepted_canonical_person_name': 'Jean Henri Humbert',
                                'accepted_dob_iso': '1887-01-24'},
                 'source_sha256s': ['382518ccd8778547cd0d16557cfc9dd14360e7b81ca9fbed83e961ceb6efacd2'],
                 'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                 'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'},
 'CTHS_102844': {'previous_values': {'identity_accepted': '0',
                                     'dob_accepted': '0',
                                     'accepted_canonical_person_name': '',
                                     'accepted_dob_iso': ''},
                 'new_values': {'identity_accepted': '1',
                                'dob_accepted': '1',
                                'accepted_canonical_person_name': 'Roger Jean Heim',
                                'accepted_dob_iso': '1900-02-12'},
                 'source_sha256s': ['34d9f0ff1073fc9ff4929979510c918d8f69061817d9a5c24432732ed181e430'],
                 'individual_case_proposals_sha256': 'ed1f8ccf1b01dd4b4f48dd39d1f129ca3c31c253c2a7926a4fb11c3bfabc77c3',
                 'membership_decisions_sha256': 'd4d2995a031bd1d474d32c54ea4fbbc709989c94c95fc173b700eab29e5153f3'}}
COMPONENT_METHOD_SHA256 = "d6ba179064775003e9a556b3579c1570f7c4a64333bd0092d0895b21c95eef13"
UNRESOLVED_BIRTHYEAR_STATUS = "unresolved_source_birthyear_conflict_no_date_selected"
EXACT_UNRESOLVED_BIRTHYEAR_CONTROLS = {
    "CTHS_102829": {
        "control_file": "source_batches/france_b/father_hold_control.json",
        "control_sha256": "09c391450a901e089d3d9dc4906ddf8484461db76af7652717a839e02e4fac3c",
        "source_sha256s": ["004926eb68023a040c44b00e85cb40e1c3c71bf46aa5316d38e6cb798b8c7b0a", "d27f70eba4e754dc4406fdcf02a8029fcc2431b3a91f4a1602c0e82be7c4ce66"],
    }
}


EXACT_UNRESOLVED_ROLE_CONTROLS = {
    "CTHS_117210": {
        "audit_file": "source_audits/casimir_role_negative_control.json",
        "audit_sha256": "1eb436995a5f1e738108fa5a6f6dbd40774bceaafd6fb1fa2d023184b55340bc",
        "source_sha256": "a30d6661fd74b49382e9b56c27d624f19e955494b8e9a6d4e07a8266c73f35e7",
        "reason": "This batch's generic member row cannot resolve an actual Academy foreign-associate role control; no lifetime exclusion or exact election date is inferred.",
    },
    "CTHS_117212": {
        "audit_file": "source_audits/chagas_foreign_role_control.json",
        "audit_sha256": "099bba51f2206db89a21bf32f49a794025da1997885d3c835b244ca0ade59ad9",
        "source_sha256": "2e943fda797be9e9d88e3cc5cdfa698127677fbdbeee00e8c6f3ab6850b7a3b1",
        "reason": "The same-publication Paris/Germain institutional bridge supports retaining the foreign-associate role hold; no membership year or lifetime exclusion is inferred.",
    }
}

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_baseline(root=ROOT):
    pinned = js(root / "inputs/baseline_provenance.json")
    require(pinned["parent_git_commit"] == BASE_COMMIT, "Wrong v11 baseline commit")
    for rel, expected in pinned["baseline_sha256"].items():
        require(sha(BASE / rel) == expected, "Changed v11 baseline: " + rel)
    for rel, expected in pinned["selection_sha256"].items():
        require(sha(root / rel) == expected, "Changed fixed v12 selection: " + rel)
    V11.check_baseline()


def selections(root=ROOT):
    config = js(root / "inputs/selection_config.json")
    require(config.get("selection_frozen") is True, "v12 selection is awaiting the root-reviewed queue freeze")
    result = {"japan": set(), "france": set()}
    for country in result:
        field = "member_key" if country == "japan" else "candidate_group_id"
        for entry in config.get(country, []):
            rel = Path(entry["path"])
            require(not rel.is_absolute() and ".." not in rel.parts and rel.parts[0] == "selection_queues", "Selection path must remain in selection_queues")
            rows = readcsv(root / rel)
            ids = {r[field] for r in rows}
            require(len(rows) == len(ids) == entry["count"], "Fixed selection cardinality mismatch: " + str(rel))
            require(not (ids & result[country]), "Overlapping fixed queues")
            result[country].update(ids)
        require(len(result[country]) == config["expected_totals"][country], "Fixed country selection total mismatch")
    return result


def baseline_summary():
    return js(BASE / "outputs/summary.json")


def processing_rows(path):
    raw = readcsv(path) if path.suffix == ".csv" else js(path)
    if isinstance(raw, dict):
        raw = raw.get("rows", raw.get("records", raw.get("queue_status", raw)))
    if isinstance(raw, dict):
        raw = [dict(v, **({"member_key": k} if k.startswith("jpa") else {"candidate_group_id": k})) for k, v in raw.items() if isinstance(v, dict)]
    require(isinstance(raw, list), "Processing records must be a list")
    return raw


def completed_status(status):
    return not status.startswith("not_") and status not in {"unprocessed", "pending"}


def processing_dispositions(path, field):
    result = {}
    for row in processing_rows(path):
        status = next((row[k] for k in ["status", "round_status", "outcome", "new_route_status", "processing_status"] if row.get(k)), "")
        require(isinstance(status, str) and status and field in row, "Missing processing identity/status: " + str(path))
        require(row[field] not in result, "Duplicate processing disposition: " + row[field])
        result[row[field]] = status
    return result


def reviewed_ids(path, field):
    return {key for key, status in processing_dispositions(path, field).items() if completed_status(status)}


def normalize_holds(raw):
    if isinstance(raw, dict):
        records = [dict(v, member_key=k) for k, v in raw.items() if k.startswith("jpa") and isinstance(v, dict)]
    else:
        require(isinstance(raw, list), "Hold list/mapping required")
        records = raw
    result = {}
    for record in records:
        # Search failures and alternate historical calendar expressions are not member-wide holds.
        if record.get("global_member_hold") is False or record.get("hold_scope") in {"claim", "search_outcome"}:
            continue
        status = record.get("status") or record.get("hold_status") or HOLD_TYPES.get(record.get("hold_type"))
        require(status is not None, "Unrecognized member-wide hold type: " + str(record.get("hold_type")))
        require(status in HOLD_RANK, "Unknown birth hold")
        key = record["member_key"]
        value = dict(status=status, reason=record.get("reason") or record.get("resolution") or record.get("note") or "")
        if record.get("existing_modern_claim_explicitly_challenged") is True:
            value["existing_modern_claim_explicitly_challenged"] = True
        require(value["reason"], "Hold needs an explicit reason")
        if key in result:
            result = merge_holds(result, {key: value})
        else:
            result[key] = value
    return result


def merge_holds(inherited, added):
    result = copy.deepcopy(inherited)
    for key, new in added.items():
        require(new.get("status") in HOLD_RANK, "Unknown birth hold")
        if key not in result:
            result[key] = copy.deepcopy(new)
        elif result[key] != new:
            old = result[key]
            # Never release/downgrade an inherited hold. Preserve both reasons even when strengthening it.
            status = max([old["status"], new["status"]], key=HOLD_RANK.get)
            result[key] = dict(status=status, reason=old["reason"] + " | v12 additional hold: " + new["reason"], inherited_hold=copy.deepcopy(old), v12_additional_hold=copy.deepcopy(new))
    return result


def reviewed_section_decisions(root=ROOT):
    proposals_path = root / "source_batches/japan_scope/section_proposals.json"
    proposals = js(proposals_path) if proposals_path.exists() else []
    require(isinstance(proposals, list), "Section proposals must be a list")
    approvals_path = root / "inputs/japan_section_approvals.json"
    approvals = js(approvals_path) if approvals_path.exists() else []
    require(isinstance(approvals, list), "Section approvals must be a list")
    require(len({x.get("member_key") for x in approvals}) == len(approvals), "Duplicate section approval")
    approved = {x.get("member_key"): x for x in approvals}
    base = {r["member_key"]: r for r in readcsv(BASE / "outputs/japan_master.csv")}
    require(set(approved) <= {p.get("member_key") for p in proposals}, "Approval has no source proposal")
    result = []
    for p in proposals:
        key = p.get("member_key")
        require(key in EXACT_SECTION_ACTIONS, "Section proposal is outside exact reviewed identities")
        expected = EXACT_SECTION_ACTIONS[key]
        require(key in base and not base[key]["broad_section_supported"], "Section action may resolve only an unresolved identity")
        require(p.get("new_broad_section") == expected["section"] and p.get("source_url") == expected["source_url"]
                and p.get("source_sha256") == expected["source_sha256"]
                and p.get("source_printed_member_name") == expected["printed_name"]
                and p.get("source_edition_year") == expected["edition_year"], "Exact section source/identity binding mismatch")
        require(p.get("name_jp") == base[key]["name_jp"] and p.get("previous_broad_section_supported") == "", "Section identity/previous-state mismatch")
        year = expected["edition_year"]
        require(not base[key]["first_election_date"] or base[key]["first_election_date"] <= f"{year}-12-31", "Section source predates the preserved membership interval")
        require(not base[key]["final_retirement_date"] or base[key]["final_retirement_date"] >= f"{year}-01-01", "Section source postdates the preserved membership interval")
        label = {"1": "第一部", "2": "第二部"}[expected["section"]]
        require(p.get("decision_type") == "set_broad_section" and p.get("source_printed_broad_section") == label
                and p.get("evidence_quote") == label, "Section must be explicitly printed, not inferred")
        require(p.get("body_verified") is True and p.get("identity_body_supported") is True
                and p.get("source_image_visually_verified") is True and p.get("source_identity_bridge")
                and p.get("source_location") and p.get("source_cover_sha256"), "Section needs actual image, edition and identity review")
        require(p.get("source_role") == "academy_issued_original_member_directory_hosted_national_library"
                and urlparse(p["source_url"]).hostname == "dl.ndl.go.jp", "Section needs the reviewed Academy directory original")
        require(p.get("degree_rule_extended") is False and p.get("exact_subsection_inferred") is False
                and p.get("new_exact_subsection") is None and p.get("dob_modified") is False
                and p.get("membership_election_date_modified") is False, "Section scope cannot infer degree/subsection or change DOB/election")
        approval = approved.get(key)
        require(approval is not None and approval.get("root_approved") is True
                and approval.get("independent_section_qa_passed") is True, "Section proposal awaits explicit root and independent QA approval")
        require(all(approval.get(k) == p.get(k) for k in ["member_key", "new_broad_section", "source_url", "source_sha256"]), "Section approval source binding mismatch")
        rel = approval.get("independent_section_qa_file")
        require(isinstance(rel, str) and not Path(rel).is_absolute() and Path(rel).parts[0] == "source_audits"
                and ".." not in Path(rel).parts, "Section QA path must stay in public audit scope")
        qa_path = root / rel
        require(qa_path.is_file() and sha(qa_path) == approval.get("independent_section_qa_sha256"), "Section QA hash binding mismatch")
        require(sha(proposals_path) == approval.get("section_proposals_sha256"), "Section proposal-file hash mismatch")
        qa = js(qa_path)
        require(qa.get("independent_qa_passed") is True
                and qa.get("section_proposals_sha256") == sha(proposals_path)
                and qa.get("worker_manifest_sha256") == sha(proposals_path.parent / "MANIFEST.json"), "Section independent QA reviewed a different final source handoff")
        checks = [c for c in qa.get("proposal_checks", []) if c.get("member_key") == key and c.get("source_sha256") == p["source_sha256"]]
        require(len(checks) == 1 and all(checks[0].get(k) is True for k in ["independent_actual_image_visual_passed", "unique_preserved_identity_match_passed", "snapshot_year_overlap_passed", "printed_exact_election_date_matches_preserved", "no_backprojection_to_original_election", "no_exact_subsection_inference"])
                and checks[0].get("new_broad_section") == expected["section"]
                and checks[0].get("source_edition_year") == expected["edition_year"]
                and checks[0].get("preserved_first_election_date") == base[key]["first_election_date"]
                and checks[0].get("literal_same_column_section") == label, "Independent QA did not approve this exact section source/identity")
        result.append(dict(p, root_approved=True, independent_qa_passed=True, root_approval_record=copy.deepcopy(approval), source_batch_version="v12"))
    return result


def apply_section_decisions(rows, decisions, summary):
    require(decisions == reviewed_section_decisions(), "Prepared section decisions differ from reviewed source approvals")
    before = {r["member_key"]: r for r in readcsv(BASE / "outputs/japan_master.csv")}
    seen = set()
    for d in decisions:
        key = d["member_key"]
        require(key not in seen, "Duplicate section decision")
        seen.add(key)
        row = next(r for r in rows if r["member_key"] == key)
        require(not before[key]["broad_section_supported"] and not row["broad_section_supported"], "Existing known section cannot be overwritten")
        row["broad_section_supported"] = d["new_broad_section"]
        row["section_evidence_status"] = "v12_direct_official_academy_directory_section_" + ("ii" if d["new_broad_section"] == "2" else "i")
        row["v12_previous_section_evidence_status"] = before[key]["section_evidence_status"]
        row["v12_section_source_url"] = d["source_url"]
        row["v12_section_source_sha256"] = d["source_sha256"]
        row["v12_section_source_locator"] = d["source_location"]
        row["v12_section_evidence_as_of_year"] = d["source_edition_year"]
        row["v12_section_temporal_scope_note"] = "Direct dated directory snapshot only; not back-projected to an earlier membership event."
    science = [r for r in rows if r["broad_section_supported"] != "1"]
    queue = [r for r in science if r["dob_status"] != "body_day_no_known_conflict" or not r["broad_section_supported"]]
    summary.update(section_status_counts=dict(collections.Counter(r["section_evidence_status"] for r in rows)),
                   broad_section_ii_supported=sum(r["broad_section_supported"] == "2" for r in rows),
                   section_i_excluded=sum(r["broad_section_supported"] == "1" for r in rows),
                   section_unresolved=sum(not r["broad_section_supported"] for r in rows),
                   nonexcluded_science_and_unresolved_candidates=len(science),
                   nonexcluded_body_day_no_known_conflict=sum(r["dob_status"] == "body_day_no_known_conflict" for r in science),
                   section_ii_and_body_day_no_known_conflict=sum(r["broad_section_supported"] == "2" and r["dob_status"] == "body_day_no_known_conflict" for r in rows),
                   nonexcluded_dob_not_day_count=sum(r["dob_status"] != "body_day_no_known_conflict" for r in science),
                   next_action_queue_count=len(queue), new_section_decisions=len(decisions),
                   scope_note="Restored predecessor working universe; exact approved official directory section attestations are added only for currently unresolved identities. All earlier scope evidence remains, no national cohort freeze or degree-rule extension.",
                   section_decision_source_scope="Exact root/independent-QA approved Academy directory snapshot only; no degree-rule extension, DOB/election change or subsection inference.")
    return queue


def reviewed_france_dob_quarantines(root=ROOT):
    approvals_path = root / "inputs/france_dob_conflict_approvals.json"
    approvals = js(approvals_path) if approvals_path.exists() else []
    require(isinstance(approvals, list), "France DOB approvals must be a list")
    require(len({x.get("candidate_group_id") for x in approvals}) == len(approvals), "Duplicate DOB quarantine approval")
    before = {r["candidate_group_id"]: r for r in readcsv(BASE / "outputs/france_master877.csv")}
    result = []
    for a in approvals:
        key = a.get("candidate_group_id")
        require(key in EXACT_FRANCE_DOB_QUARANTINE, "DOB quarantine is outside the exact reviewed identity")
        expected = EXACT_FRANCE_DOB_QUARANTINE[key]
        require(a.get("decision_type") == "quarantine_existing_dob_on_body_conflict"
                and a.get("root_approved") is True and a.get("independent_qa_passed") is True,
                "DOB quarantine needs root and independent QA approval")
        require(before[key]["identity_accepted"] == before[key]["dob_accepted"] == "1"
                and before[key]["accepted_dob_iso"] == expected["baseline_accepted_dob_iso"]
                and a.get("baseline_accepted_dob_iso") == expected["baseline_accepted_dob_iso"]
                and a.get("observed_competing_dates") == expected["observed_competing_dates"], "DOB quarantine previous value/date binding mismatch")
        def public_file(field):
            rel = a.get(field)
            require(isinstance(rel, str) and not Path(rel).is_absolute() and Path(rel).parts[0] == "source_audits"
                    and ".." not in Path(rel).parts, "DOB evidence path must stay in public audit scope")
            path = root / rel
            require(path.is_file(), "DOB evidence file is missing")
            return path
        claims_path = public_file("source_claims_file")
        qa_path = public_file("independent_qa_file")
        require(sha(claims_path) == a.get("source_claims_sha256") == expected["source_claims_sha256"], "DOB source-pair hash mismatch")
        require(sha(qa_path) == a.get("independent_qa_sha256"), "DOB independent QA hash mismatch")
        claims = js(claims_path)
        require(isinstance(claims, list) and len(claims) == 2 and {c.get("date_iso") for c in claims} == set(expected["observed_competing_dates"]), "DOB quarantine needs both observed competing body dates")
        for c in claims:
            require(c.get("candidate_group_id") == key and c.get("source_sha256") == expected["source_hashes"][c["date_iso"]]
                    and c.get("body_verified") is True and c.get("identity_body_supported") is True
                    and c.get("raw_birth_statement") and c.get("source_locator") and c.get("identity_note"), "DOB source identity/body/hash binding mismatch")
        qa = js(qa_path)
        require(qa.get("independent_qa_passed") is True and qa.get("candidate_group_id") == key
                and qa.get("source_claims_sha256") == sha(claims_path)
                and set(qa.get("source_dates_body_verified", [])) == set(expected["observed_competing_dates"]), "DOB independent QA reviewed a different source pair")
        require(a.get("body_sources_share_reference") is True and a.get("sources_not_assumed_independent") is True
                and qa.get("sources_not_assumed_independent") is True, "Related DOB sources cannot be counted as independent votes")
        result.append(dict(a, source_claims=claims, source_batch_version="v12", accepted_new_dob_iso=None))
    return result


def apply_france_dob_quarantines(rows, decisions):
    require(decisions == reviewed_france_dob_quarantines(), "Prepared DOB quarantines differ from reviewed source approvals")
    by = {r["candidate_group_id"]: r for r in rows}
    for d in decisions:
        row = by[d["candidate_group_id"]]
        require(row["dob_accepted"] == "1" and row["accepted_dob_iso"] == d["baseline_accepted_dob_iso"], "DOB quarantine may suspend only the exact old approval")
        row["v12_previous_accepted_dob_iso"] = row["accepted_dob_iso"]
        row["v12_previous_exact_dob_claims"] = row["exact_dob_claims"]
        row["exact_dob_claims"] = "|".join(sorted(set(row["exact_dob_claims"].split("|")) | set(d["observed_competing_dates"])))
        row["exact_dob_conflict"] = "1"
        row["dob_accepted"] = "0"
        row["accepted_dob_iso"] = ""
        row["v12_dob_review_status"] = "source_date_conflict_hold_no_day_selected"
        row["v12_dob_review_reason"] = d["reason"]
        row["v12_dob_conflict_source_urls"] = [c["source_url"] for c in d["source_claims"]]
        row["v12_dob_conflict_source_claims_file_sha256"] = d["source_claims_sha256"]
        row["completion_remaining_dimensions"] = "|".join(k for k in ["identity", "membership", "dob"] if row[k+"_accepted"] != "1")
        row["completion_status"] = "reviewed_with_holds"
        row["role_cutoff_and_dob_supported"] = False
    return rows


CASE_FIELDS = {"identity_accepted", "dob_accepted", "accepted_canonical_person_name", "accepted_dob_iso"}


def birthyear_control(key, root=ROOT):
    expected = EXACT_UNRESOLVED_BIRTHYEAR_CONTROLS.get(key)
    if expected is None:
        return None
    path = root / expected["control_file"]
    require(sha(path) == expected["control_sha256"], "Unresolved birthyear control metadata changed")
    control = js(path)
    require(control.get("candidate_group_id") == key
            and control["father_dedicated_subject_source"]["source_sha256"] == expected["source_sha256s"][0]
            and control["related_son_source"]["source_sha256"] == expected["source_sha256s"][1]
            and control["father_dedicated_subject_source"]["observed_full_date"] == "1862-11-23"
            and control["related_son_source"]["observed_birthyear_only"] == 1867,
            "Unresolved birthyear control source/subject binding mismatch")
    return control


def apply_unresolved_birthyear_controls(rows):
    for row in rows:
        for field in ["v12_dob_review_status", "v12_dob_review_reason", "v12_dob_review_control_sha256", "v12_dob_review_source_sha256s", "v12_dob_review_observed_birthyears"]:
            row.setdefault(field, "")
        key = row["candidate_group_id"]
        control = birthyear_control(key)
        if control is None:
            continue
        expected = EXACT_UNRESOLVED_BIRTHYEAR_CONTROLS[key]
        row["v12_dob_review_status"] = UNRESOLVED_BIRTHYEAR_STATUS
        row["v12_dob_review_reason"] = "Actual same-father source statements disagree on1862 versus1867; the later year has no observed month/day. Identity/DOB/membership remain held; no date is selected."
        row["v12_dob_review_control_sha256"] = expected["control_sha256"]
        row["v12_dob_review_source_sha256s"] = list(expected["source_sha256s"])
        row["v12_dob_review_observed_birthyears"] = [1862, 1867]
    return rows


def reviewed_individual_case_decisions(root=ROOT):
    path = root / "source_batches/france_b/individual_case_proposals.json"
    proposals = js(path) if path.exists() else []
    require(isinstance(proposals, list) and len({p.get("candidate_group_id") for p in proposals}) == len(proposals), "Duplicate or malformed individual-case proposals")
    by_proposal = {p.get("candidate_group_id"): p for p in proposals}
    approvals_path = root / "inputs/france_individual_case_approvals.json"
    approvals = js(approvals_path) if approvals_path.exists() else []
    require(isinstance(approvals, list) and len({a.get("candidate_group_id") for a in approvals}) == len(approvals), "Duplicate or malformed individual-case approvals")
    before = {r["candidate_group_id"]: r for r in readcsv(BASE / "outputs/france_master877.csv")}
    eligible_path = root / "selection_queues/france_b.csv"
    eligible = {r["candidate_group_id"] for r in readcsv(eligible_path)} if eligible_path.exists() else set()
    result = []
    for a in approvals:
        key = a.get("candidate_group_id")
        require(key in eligible and key in by_proposal and key in EXACT_INDIVIDUAL_CASE_ACCEPTANCES, "Individual-case approval is outside exact reviewed B identities")
        p, old, expected = by_proposal[key], before[key], EXACT_INDIVIDUAL_CASE_ACCEPTANCES[key]
        require(birthyear_control(key, root) is None and not any(k.endswith("_dob_review_status") and v == UNRESOLVED_BIRTHYEAR_STATUS for k, v in old.items()),
                "Unresolved actual-source birthyear conflict blocks individual-case promotion")
        require(a.get("root_approved") is True and a.get("independent_qa_passed") is True, "Individual case awaits root and independent actual-source approval")
        require(p.get("decision_type") == "accept_individual_identity_dob" and p.get("name") == old["display_name"], "Individual-case preserved identity mismatch")
        previous = {k: old[k] for k in CASE_FIELDS}
        changes = p.get("new_values")
        require(p.get("previous_values") == previous == expected.get("previous_values") == a.get("previous_values") and isinstance(changes, dict)
                and changes and set(changes) <= CASE_FIELDS and changes == expected.get("new_values") == a.get("new_values"), "Individual-case old/new value binding mismatch")
        require(p.get("prior_exact_dob_claims") == old["exact_dob_claims"] and old["exact_dob_conflict"] != "1", "Individual case cannot bypass an inherited birthday conflict")
        for flag in ["identity_accepted", "dob_accepted"]:
            if flag in changes:
                require(old[flag] == "0" and changes[flag] == "1", "Individual case may approve only an old zero flag")
        if "accepted_canonical_person_name" in changes:
            require(changes.get("identity_accepted") == "1" and changes["accepted_canonical_person_name"], "Canonical identity needs explicit new identity approval")
        require(changes.get("identity_accepted", old["identity_accepted"]) == "1" and p.get("identity_bridge"), "Individual case needs a supported unique identity")
        require(all(p.get("identity_checks", {}).get(k) is True for k in ["unique_preserved_group_match", "no_unresolved_alias_or_profile_collision", "same_subject_name_dob_career_verified"]), "Individual case has an unresolved identity/alias bridge")
        if "accepted_dob_iso" in changes or "dob_accepted" in changes:
            singleton = old["exact_dob_claims"]
            require(changes.get("dob_accepted") == "1" and changes.get("accepted_dob_iso") == singleton
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", singleton) is not None
                    and p.get("dob_matches_singleton_prior_raw_claim") is True, "DOB case must approve only its singleton unchanged prior raw claim")
            datetime.date.fromisoformat(singleton)
        sources = p.get("source_evidence")
        require(isinstance(sources, list) and sources, "Individual case needs actual source bodies")
        for e in sources:
            require(re.fullmatch(r"[0-9a-f]{64}", str(e.get("source_sha256", ""))) is not None
                    and e.get("source_url", "").startswith("https://") and type(e.get("source_capture_bytes")) is int
                    and e["source_capture_bytes"] > 0 and e.get("http_status") == 200 and e.get("source_id")
                    and e.get("body_verified") is True and e.get("identity_body_supported") is True
                    and e.get("source_locator") and e.get("observed_subject_name") and e.get("identity_support")
                    and e.get("source_role") and e.get("source_independence_group"), "Individual-case actual-source metadata is incomplete")
            require(bool(e.get("retrieved_utc")) or (e.get("retrieved_utc") is None
                    and e.get("capture_origin") == "existing_archived_original" and e.get("archived_capture_timestamp_unknown") is True
                    and e.get("local_reopened_utc") and e.get("archive_path") and e.get("archive_member")), "Individual-case retrieval provenance is incomplete")
        hashes = sorted(e["source_sha256"] for e in sources)
        if changes.get("dob_accepted") == "1":
            require(any(e.get("observed_dob_iso") == changes["accepted_dob_iso"] for e in sources), "Approved birthday is absent from actual case-source readings")
        require(sha(path) == a.get("individual_case_proposals_sha256") == expected.get("individual_case_proposals_sha256")
                and hashes == expected.get("source_sha256s") == a.get("source_sha256s"), "Individual-case proposal/source hashes differ from exact approval")
        membership_sha = sha(path.parent / "decisions.json")
        require(membership_sha == a.get("membership_decisions_sha256") == expected.get("membership_decisions_sha256"),
                "Individual-case approval reviewed different conditional membership decisions")
        qa_rel = a.get("independent_qa_file", "")
        require(not Path(qa_rel).is_absolute() and Path(qa_rel).parts and Path(qa_rel).parts[0] == "source_audits" and ".." not in Path(qa_rel).parts, "Individual-case QA must remain in source_audits")
        qa_path = root / qa_rel
        require(sha(qa_path) == a.get("independent_qa_sha256"), "Individual-case QA hash mismatch")
        qa = js(qa_path)
        require(qa.get("independent_qa_passed") is True and qa.get("individual_case_proposals_sha256") == sha(path)
                and qa.get("decisions_sha256") == membership_sha
                and qa.get("worker_manifest_sha256") == sha(path.parent / "MANIFEST.json"), "Individual-case QA reviewed a different final source handoff")
        checks = [c for c in qa.get("case_checks", []) if c.get("candidate_group_id") == key]
        required = ["previous_values_match_baseline", "identity_source_body_bridge_passed", "uniqueness_and_alias_collision_checks_passed", "all_actual_sources_rehashed_and_body_read", "no_old_source_flags_changed"]
        if changes.get("dob_accepted") == "1":
            required.append("singleton_prior_DOB_claim_passed")
        require(len(checks) == 1 and checks[0].get("source_sha256s") == hashes and all(checks[0].get(k) is True for k in required), "Independent QA did not approve this exact unique case")
        result.append(dict(p, root_approved=True, independent_qa_passed=True, root_approval_record=copy.deepcopy(a), source_batch_version="v12"))
    return result


def apply_individual_case_decisions(rows, decisions):
    require(decisions == reviewed_individual_case_decisions(), "Prepared individual cases differ from exact reviewed approvals")
    by = {r["candidate_group_id"]: r for r in rows}
    for d in decisions:
        row = by[d["candidate_group_id"]]
        require({k: row[k] for k in CASE_FIELDS} == d["previous_values"], "Individual case previous state changed")
        row["v12_previous_individual_case_values"] = copy.deepcopy(d["previous_values"])
        row.update(d["new_values"])
        row["v12_individual_case_status"] = "root_and_independent_source_review_approved"
        row["v12_individual_case_reason"] = d["reason"]
        row["v12_individual_case_source_sha256s"] = [e["source_sha256"] for e in d["source_evidence"]]
        row["completion_remaining_dimensions"] = "|".join(k for k in ["identity", "membership", "dob"] if row[k + "_accepted"] != "1")
        row["completion_status"] = "accepted_all_three" if not row["completion_remaining_dimensions"] else "reviewed_with_holds"
    return rows


def prepare(root=ROOT):
    check_baseline(root)
    chosen = selections(root)
    config = js(root / "inputs/batch_selection.json")
    source = root / "source_batches"
    jp_cross = set(config.get("japan_cross_source_member_keys", []))
    require(not (jp_cross & chosen["japan"]), "Japan cross-source addenda must be counted outside the fixed selection")
    base_jp = {r["member_key"]: r for r in readcsv(BASE / "outputs/japan_master.csv")}
    require(jp_cross <= base_jp.keys(), "Unknown Japan cross-source identity")
    delta = []
    for rel in config["japan_claim_files"]:
        for i, row in enumerate(js(source / rel)):
            require(row["member_key"] in chosen["japan"] | jp_cross, "Unselected v12 Japan claim")
            delta.append(dict(row, source_batch_record=rel + ":" + str(i), source_batch_version="v12"))
    processed = set()
    all_jp_outcomes = set()
    for rel in config["japan_processed_files"]:
        dispositions = processing_dispositions(source / rel, "member_key")
        require(not (all_jp_outcomes & dispositions.keys()), "Duplicate Japan disposition across source files")
        all_jp_outcomes.update(dispositions)
        processed.update(k for k, status in dispositions.items() if completed_status(status))
    require(all_jp_outcomes == chosen["japan"], "All fixed Japan candidates need explicit outcomes, including not_searched")
    require(processed <= chosen["japan"], "Unknown reviewed Japan ID")
    source_processed = set(processed)
    dob_processed = {c["member_key"] for c in delta} & source_processed
    for rel in config["japan_processed_files"]:
        for row in processing_rows(source / rel):
            if any(str(row.get(k, "")).lower() == "true" for k in ["dob_search_performed", "dob_body_review_performed"]):
                dob_processed.add(row["member_key"])
    require(dob_processed <= source_processed, "DOB review needs a completed source outcome")
    processed = dob_processed
    new_holds = {}
    for rel in config["japan_hold_files"]:
        new_holds = merge_holds(new_holds, normalize_holds(js(source / rel)))
    require(set(new_holds) <= chosen["japan"] | jp_cross, "Unselected v12 Japan hold")
    section_decisions = reviewed_section_decisions(root)
    decisions = []
    for rel in config["france_decision_files"]:
        decisions.extend(dict(d, source_batch_file=rel, source_batch_version="v12") for d in js(source / rel))
    cross = set(config.get("france_cross_source_candidate_ids", []))
    require(not (cross & chosen["france"]), "Cross-source addendum must be counted outside the fixed selection")
    base_fr = {r["candidate_group_id"]: r for r in readcsv(BASE / "outputs/france_master877.csv")}
    for key in cross:
        require(key in base_fr and base_fr[key]["identity_accepted"] == base_fr[key]["dob_accepted"] == "1"
                and base_fr[key]["membership_accepted"] == "0" and base_fr[key]["election_date_conflict"] != "1",
                "Cross-source ID must be an unchanged identity/DOB-approved strict gap without conflict")
    require({d["candidate_group_id"] for d in decisions} <= chosen["france"] | cross, "Unselected v12 France decision")
    for d in decisions:
        if d["candidate_group_id"] in cross:
            require(V3.flag(d["membership_accepted"]) == "1", "Cross-source addendum needs actual strict-positive evidence")
            validate_france_positive(d, base_fr[d["candidate_group_id"]])
    fr_processed, all_fr_outcomes = set(), set()
    for rel in config["france_processed_files"]:
        dispositions = processing_dispositions(source / rel, "candidate_group_id")
        require(not (all_fr_outcomes & dispositions.keys()), "Duplicate France disposition across source files")
        all_fr_outcomes.update(dispositions)
        fr_processed.update(k for k, status in dispositions.items() if completed_status(status))
    require(all_fr_outcomes == chosen["france"], "All fixed France candidates need explicit outcomes, including not_searched")
    require(fr_processed <= chosen["france"], "Unknown reviewed France ID")
    old_claims = js(BASE / "inputs/japan_claims.json")
    old_holds = inherited_holds()
    for release in calendar_routing_releases(delta, root=root):
        del old_holds[release["member_key"]]
    old_processed = js(BASE / "inputs/japan_processed_ids.json")
    return {"france_individual_case_decisions.json": reviewed_individual_case_decisions(root),
            "france_dob_conflict_decisions.json": reviewed_france_dob_quarantines(root),
            "japan_section_decisions.json": section_decisions,
            "japan_claims.json": old_claims + delta,
            "japan_delta_claims.json": delta,
            "japan_holds.json": merge_holds(old_holds, new_holds),
            "japan_delta_holds.json": new_holds,
            "japan_processed_ids.json": sorted(set(old_processed) | processed),
            "japan_delta_processed_ids.json": sorted(processed),
            "france_decisions.json": decisions,
            "france_processed_ids.json": sorted(fr_processed),
            "inherited_france_decisions.json": readcsv(BASE / "outputs/france_membership_decisions.csv")}


def previous_japan():
    # The final-state API includes all approved v11 direct section decisions and the
    # previously approved date/calendar/tier state; a three-argument birth-only
    # replay would silently omit that approved scope evidence.
    return V11.final_japan()


def inherited_holds(base_rows=None):
    """Seed effective status/reason from actual v11 state, retaining old overlay metadata."""
    overlays = copy.deepcopy(js(BASE / "inputs/japan_holds.json"))
    if base_rows is None:
        base_rows = previous_japan()[0]
    result = {}
    for row in base_rows:
        if row["dob_status"].endswith("_hold"):
            key = row["member_key"]
            old = overlays.get(key)
            value = copy.deepcopy(old) if old else {}
            if old and (old.get("status"), old.get("reason")) != (row["dob_status"], row.get("dob_hold_note", "")):
                value["inherited_predecessor_overlay_record"] = copy.deepcopy(old)
            value.update(status=row["dob_status"], reason=row.get("dob_hold_note", ""),
                         inherited_effective_baseline_study="studies/academy_fr_jp_completion_v11")
            result[key] = value
    return result


def calendar_routing_releases(delta, base_rows=None, base_ledger=None, root=ROOT):
    path = root / "inputs/calendar_routing_decisions.json"
    if not path.exists():
        return []
    decisions = js(path)
    require(isinstance(decisions, list), "Calendar routing decisions must be a list")
    require(not decisions, "No new v12 calendar routing source has root approval")
    return []


def secondary_reference(claim):
    return V3.secondary_reference(claim) or claim.get("source_tier") in REVIEWED_ATTRIBUTED_SECONDARY_TIERS


def classify_day_evidence(rows, ledger, summary):
    grouped = collections.defaultdict(list)
    for claim in ledger:
        if claim["precision"] == "day" and claim["calendar_comparable"]:
            grouped[claim["member_key"]].append(claim)
    for row in rows:
        days = grouped[row["member_key"]]
        row["has_institution_or_university_day_claim"] = any(not secondary_reference(c) for c in days)
        row["has_edited_reference_day_claim"] = any(V4.edited_reference(c) for c in days)
        row["has_other_attributed_secondary_day_claim"] = any(secondary_reference(c) and not V4.edited_reference(c) for c in days)
        row["day_evidence_tier"] = ("institution_or_university_supported" if row["has_institution_or_university_day_claim"] else "edited_reference_only" if row["has_edited_reference_day_claim"] else "other_attributed_secondary_only") if row["dob_status"] == "body_day_no_known_conflict" else "not_day_without_known_conflict"
    days = [r for r in rows if r["dob_status"] == "body_day_no_known_conflict"]
    summary.update(institutional_or_university_supported_day_no_known_conflict=sum(r["has_institution_or_university_day_claim"] for r in days),
                   edited_reference_only_day_no_known_conflict=sum(r["day_evidence_tier"] == "edited_reference_only" for r in days),
                   other_attributed_secondary_only_day_no_known_conflict=sum(r["day_evidence_tier"] == "other_attributed_secondary_only" for r in days),
                   secondary_only_day_no_known_conflict=sum(not r["has_institution_or_university_day_claim"] for r in days),
                   reviewed_v12_attributed_reproduction_tiers=sorted(REVIEWED_ATTRIBUTED_SECONDARY_TIERS),
                   source_tier_classification_note="Legacy classification plus the exact root-reviewed third-party university-publication reproduction tier; an attributed reproduction is not promoted to institution-hosted or edited-reference evidence.")


def japan(delta, new_holds, new_processed, section_decisions=None):
    base_rows, base_ledger, _, baseline = previous_japan()
    by = {r["member_key"]: r for r in base_rows}
    require(set(new_processed) <= by.keys(), "Unknown processed Japan identity")
    require(set(new_holds) <= by.keys(), "Unknown Japan hold identity")
    for c in delta:
        J.validate_claim(c, by)
        require(not any(h in c["source_url"] for h in ["wikipedia.org", "wikidata.org"]), "Crowd-source evidence not allowed")
        original_hash = c.get("source_sha256")
        if original_hash is None:
            exceptions = js(ROOT / "inputs/batch_selection.json").get("web_body_capture_exceptions", [])
            approved = [e for e in exceptions if all(c.get(k) == e.get(k) for k in ["member_key", "source_url", "extracted_body_sha256", "source_original_capture_http_status", "web_body_ref"])
                        and re.fullmatch(r"turn\d+(?:view|fetch|search)\d+", e.get("root_verification_ref", "")) is not None]
            require(len(approved) == 1, "Null original hash is not an explicitly approved source exception")
            require(c.get("source_capture_status") == "original_capture_failed_body_verified_via_web"
                    and type(c.get("source_original_capture_http_status")) is int
                    and 400 <= c["source_original_capture_http_status"] <= 599
                    and re.fullmatch(r"turn\d+(?:view|fetch)\d+", c.get("web_body_ref", "")) is not None
                    and re.fullmatch(r"[0-9a-f]{64}", c.get("extracted_body_sha256", "")) is not None,
                    "Null original hash needs exact approved failure/web-body evidence; derived text is not original bytes")
        else:
            require(re.fullmatch(r"[0-9a-f]{64}", original_hash) is not None, "New source needs original captured-body SHA256")
        require(c.get("retrieved_utc") or c.get("retrieved_date"), "New source needs retrieval time")
        reviewed_tiers = js(ROOT / "inputs/batch_selection.json").get("reviewed_source_tiers", [])
        require(c.get("source_tier") in set(baseline["source_tier_claim_counts"]) | set(reviewed_tiers), "Unreviewed source tier")
    for key, h in new_holds.items():
        if h["status"] == "source_calendar_hold" and by[key]["dob_status"] == "body_day_no_known_conflict":
            require(h.get("existing_modern_claim_explicitly_challenged") is True, "Historical alternate cannot erase supported modern date")
    routing_releases = calendar_routing_releases(delta, base_rows, base_ledger)
    cumulative_holds = merge_holds(inherited_holds(base_rows), new_holds)
    # Recompute from the approved structured v11 ledger, not V4's older input
    # overlays. This naturally retains all four exact prior routing outcomes
    # while still detecting any new comparable date disagreement.
    authority = {r["member_key"]: copy.deepcopy(r["ndl_authority_name_only_candidates"]) for r in base_rows}
    birth_processed = {r["member_key"] for r in base_rows if r["body_source_reviewed"]} | set(new_processed)
    rows, ledger, queue, recomputed = J.assemble(base_rows, base_ledger + delta, cumulative_holds, birth_processed, authority)
    for row in rows:
        row["body_source_reviewed"] = row.pop("institutionally_processed")
        if row["dob_status"] == "not_institutionally_processed":
            row["dob_status"] = "not_body_source_processed"
    recomputed["dob_status_counts"]["not_body_source_processed"] = recomputed["dob_status_counts"].pop("not_institutionally_processed", 0)
    recomputed["body_birth_people"] = recomputed.pop("institutional_body_birth_people")
    summary = copy.deepcopy(baseline)
    summary.update(recomputed)
    summary["scope_note"] = baseline["scope_note"]
    summary["source_tier_claim_counts"] = dict(collections.Counter(c["source_tier"] for c in ledger))
    summary["source_tier_note"] = "Institution/university/organization, edited-reference-only and other attributed-secondary day evidence remain separate."
    classify_day_evidence(rows, ledger, summary)
    for r in rows:
        for version in range(4, 12):
            field = f"v{version}_source_claim_added"
            r[field] = by[r["member_key"]][field]
        r["v12_source_claim_added"] = any(c["member_key"] == r["member_key"] for c in delta)
        require(r["broad_section_supported"] == by[r["member_key"]]["broad_section_supported"], "v12 cannot alter Japan scope")
        released = next((d for d in routing_releases if d["member_key"] == r["member_key"]), None)
        if released:
            require(r["dob_status"] == "body_day_no_known_conflict" and r["source_date_components_iso"] == released["source_date_components_iso"], "Exact routing release did not produce the source-supplied day")
        elif by[r["member_key"]]["dob_status"].endswith("_hold"):
            require(r["dob_status"].endswith("_hold"), "Inherited Japan hold released")
            require(HOLD_RANK[r["dob_status"]] >= HOLD_RANK[by[r["member_key"]]["dob_status"]], "Inherited Japan hold downgraded")
        old = by[r["member_key"]]
        if old["dob_status"] == r["dob_status"] == "body_day_no_known_conflict":
            require(r["source_date_components_iso"] == old["source_date_components_iso"], "Inherited selected Japan day changed")
    new_by_claim = {c["claim_id"]: c for c in ledger}
    require(all(new_by_claim.get(c["claim_id"]) == c for c in base_ledger), "Inherited claim or claim field changed")
    summary.update(baseline_day_no_known_conflict=baseline["body_day_no_known_conflict"],
                   day_status_net_change=summary["body_day_no_known_conflict"] - baseline["body_day_no_known_conflict"],
                   new_raw_source_claim_rows=len(delta), inherited_v11_raw_source_claim_rows=len(js(BASE / "inputs/japan_claims.json")),
                   newly_processed_v12_candidates=len(set(new_processed)), new_section_decisions=0,
                   approved_calendar_routing_releases=len(routing_releases), calendar_routing_release_sources=routing_releases,
                   calendar_routing_release_note="Exact root-approved source-supplied pairs only, including the separately approved original V2 calendar-routing overlay; no collector conversion, majority adjudication or generic hold release.")
    if section_decisions:
        queue = apply_section_decisions(rows, section_decisions, summary)
    return rows, ledger, queue, summary


def normalized_credit(value):
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def cths_contribution_origin(e):
    """An exact credited institutional contribution, never CTHS-domain trust."""
    credit = normalized_credit(e.get("source_author_credit", ""))
    authors = e.get("credited_authors", e.get("source_credited_authors"))
    if not isinstance(authors, list) or credit not in {normalized_credit(a) for a in authors}:
        return False
    common = (e.get("source_author_credit_verified") is True
              and e.get("source_author_credit_scope") == "explicit_credited_writer_or_cowriter"
              and str(e.get("cths_society_id")) == "506"
              and all(e.get(k) is True for k in ["cths_typed_ordinary_role_verified", "cths_literal_full_member_start_verified",
                                                "cths_same_body_authorship_role_start_verified", "cths_identity_body_verified"])
              and e.get("body_verified") is True and bool(e.get("identity_note"))
              and re.fullmatch(r"[0-9a-f]{64}", str(e.get("source_sha256", ""))) is not None)
    if not common:
        return False
    if credit == "academie des sciences":
        return (e.get("source_role") == "academy_authored_independent_host"
                and e.get("academy_authored_or_issued_original") is True)
    if credit == "institut de france":
        academy_claim = e.get("academy_authored_or_issued_original") is True
        actual_academy_cocredit = isinstance(authors, list) and "academie des sciences" in {normalized_credit(a) for a in authors}
        return (e.get("source_role") == "parent_institution_firstparty"
                and e.get("parent_institution_authored_or_issued_original") is True
                and (not academy_claim or actual_academy_cocredit))
    return False


def academy_original(e):
    host = (urlparse(e.get("source_url", "")).hostname or "").lower()
    if host in {"cths.fr", "www.cths.fr"}:
        if e.get("cths_notice_component_bundle_verified") is True:
            return cths_notice_component_origin(e)
        return cths_contribution_origin(e)
    return V11.academy_original(e)


def cths_notice_component_origin(e):
    """One linked subject notice, with two explicitly separate HTTP originals."""
    if not (e.get("cths_evidence_spans_multiple_http_responses") is True
            and e.get("cths_same_body_authorship_role_start_verified") is False
            and e.get("cths_component_method_contract_sha256") == COMPONENT_METHOD_SHA256
            and sha(ROOT / "source_audits/cths_expanded_notice_method_contract.json") == COMPONENT_METHOD_SHA256):
        return False
    # Reuse the unchanged credit/ordinary/start requirements without claiming
    # that the parent byline and expanded event share one HTTP response.
    credit_view = dict(e, cths_same_body_authorship_role_start_verified=True)
    if not cths_contribution_origin(credit_view):
        return False
    required_true = ["cths_parent_notice_identity_DOB_verified", "cths_expanded_biography_body_verified",
                     "cths_expansion_handler_ID_continuity_verified", "cths_expansion_preview_career_continuity_verified",
                     "cths_subject_identity_career_verified", "cths_known_role_controls_preserved", "identity_and_DOB_unchanged"]
    if not all(e.get(k) is True for k in required_true):
        return False
    parent = urlparse(e.get("cths_parent_notice_url", ""))
    expanded = urlparse(e.get("cths_expanded_biography_url", ""))
    parent_ids = parse_qs(parent.query).get("id", [])
    if not (parent.scheme == expanded.scheme == "https" and parent.hostname in {"cths.fr", "www.cths.fr"}
            and expanded.hostname == parent.hostname and parent.path == "/an/savant.php"
            and expanded.path == "/library/getdata.php" and len(parent_ids) == 1):
        return False
    key = parent_ids[0]
    h = e.get("cths_observed_expansion_handler")
    if not isinstance(h, dict):
        return False
    query = dict(q=["proso_bio_detail"], id=[key], dep=["y"])
    if not (h.get("target_element_id") == h.get("query_name") == "proso_bio_detail"
            and str(h.get("person_id")) == key and h.get("dep") == "y"
            and h.get("resolved_url") == e.get("cths_expanded_biography_url")
            and h.get("literal_onclick_or_query") and h.get("parent_source_locator")
            and parse_qs(expanded.query) == query):
        return False
    literal = h["literal_onclick_or_query"]
    if not isinstance(literal, str):
        return False
    pairs = re.findall(r"(?<![A-Za-z0-9_])(q|id|dep)=([^&'\"\s)]+)", literal)
    if len(pairs) != 3 or dict(pairs) != dict(q="proso_bio_detail", id=key, dep="y"):
        return False
    components = e.get("source_capture_components")
    if not isinstance(components, list) or len(components) != 2:
        return False
    by = {c.get("component"): c for c in components if isinstance(c, dict)}
    if set(by) != {"parent_notice", "expanded_biography"}:
        return False
    for component, prefix in [("parent_notice", "cths_parent_notice"), ("expanded_biography", "cths_expanded_biography")]:
        c = by[component]
        if not (re.fullmatch(r"[0-9a-f]{64}", str(e.get(prefix + "_sha256", "")))
                and e.get(prefix + "_http_status") == 200 and e.get(prefix + "_retrieved_utc")
                and c.get("source_url") == e.get(prefix + "_url")
                and c.get("source_sha256") == e.get(prefix + "_sha256")
                and c.get("http_status") == 200 and c.get("retrieved_utc") == e[prefix + "_retrieved_utc"]
                and type(c.get("bytes")) is int and c["bytes"] > 0):
            return False
    return (e.get("source_url") == e["cths_parent_notice_url"]
            and e.get("source_sha256") == e["cths_parent_notice_sha256"]
            and e.get("cths_notice_authorship_credit_component") == "parent_notice"
            and all(e.get("cths_" + kind + "_evidence_component") in by and e.get("cths_" + kind + "_evidence_locator") for kind in ["role", "start"])
            and bool(e.get("source_independence_group")))


def reviewed_component_acceptance(d, e, root=ROOT):
    key = d["candidate_group_id"]
    expected = EXACT_COMPONENT_ACCEPTANCES.get(key)
    require(expected is not None, "Expanded-notice membership awaits an exact root-reviewed source approval")
    approvals = js(root / "inputs/cths_component_approvals.json")
    matches = [a for a in approvals if a.get("candidate_group_id") == key]
    require(len(matches) == 1, "Component acceptance needs one exact approval")
    a = matches[0]
    require(a.get("root_approved") is True and a.get("independent_qa_passed") is True,
            "Component acceptance needs root and independent source QA")
    fields = ["cths_parent_notice_sha256", "cths_expanded_biography_sha256"]
    require(all(e.get(k) == a.get(k) == expected.get(k) for k in fields), "Component source-pair approval mismatch")
    require(all(d.get(k) == a.get(k) == expected.get(k) for k in ["accepted_full_member_election_date", "accepted_full_member_election_year", "accepted_full_member_election_precision"]),
            "Component event differs from exact root approval")
    decision_path = root / "source_batches/france_a/decisions.json"
    require(sha(decision_path) == a.get("decisions_sha256") == expected.get("decisions_sha256"), "Component decision-file binding mismatch")
    qa_rel = a.get("independent_qa_file", "")
    require(not Path(qa_rel).is_absolute() and Path(qa_rel).parts and Path(qa_rel).parts[0] == "source_audits" and ".." not in Path(qa_rel).parts,
            "Component QA must remain in source_audits")
    qa_path = root / qa_rel
    require(sha(qa_path) == a.get("independent_qa_sha256"), "Component QA hash mismatch")
    qa = js(qa_path)
    require(qa.get("independent_qa_passed") is True and qa.get("decisions_sha256") == sha(decision_path)
            and qa.get("worker_manifest_sha256") == sha(decision_path.parent / "MANIFEST.json"), "Component QA reviewed a different handoff")
    checks = [c for c in qa.get("decision_checks", []) if c.get("candidate_group_id") == key]
    require(len(checks) == 1 and all(checks[0].get(k) == e.get(k) for k in fields)
            and all(checks[0].get(k) is True for k in ["independent_component_bundle_passed", "ordinary_role_direct_start_passed", "identity_DOB_unchanged"]),
            "Component QA did not approve this exact source/subject event")


def ordinary_subject_event(e):
    """Metadata cannot re-label an as-of bound or the notice author's title as an election."""
    non_events = {"as_of", "asof", "status_as_of", "dated_role_bound", "author_title", "author_membership",
                  "membership_attested_by_year", "presidency_attesting_membership",
                  "perpetual_secretary_appointment_attesting_membership_by_year"}
    kind = str(e.get("event_type", e.get("event_kind", ""))).lower().replace("-", "_").replace(" ", "_")
    subject = str(e.get("event_subject_role", e.get("subject_role", ""))).lower()
    return (kind not in non_events and "as_of" not in kind and "asof" not in kind
            and "relative" not in kind and "derived" not in kind and "arithmetic" not in kind
            and subject not in {"author", "notice_author", "speaker"}
            and e.get("event_is_as_of") is not True and e.get("event_belongs_to_author") is not True
            and e.get("event_year_is_derived") is not True and e.get("event_year_is_relative") is not True
            and e.get("event_year_is_calculated") is not True)


def inherited_france_role_evidence():
    grouped = collections.defaultdict(list)
    for record in readcsv(BASE / "outputs/france_membership_decisions.csv"):
        evidence = record.get("evidence", [])
        if isinstance(evidence, str):
            evidence = json.loads(evidence) if evidence else []
        if isinstance(evidence, list):
            grouped[record["candidate_group_id"]].extend(e for e in evidence if isinstance(e, dict))
    return grouped


def reject_same_event_nonordinary_role_conflict(d, year, accepted_date, prior_evidence):
    if d.get("known_nonordinary_role_conflict_for_same_event") is True:
        raise ValueError("Ordinary membership cannot override explicit same-event nonordinary role evidence")
    nonordinary = {"correspondent", "correspondant", "membre correspondant", "foreign associate", "foreign member", "foreign full member", "associe etranger", "membre associe etranger"}
    for e in list(d.get("evidence", [])) + list(prior_evidence):
        if e.get("same_event_foreign_or_correspondent_conflict") is True:
            raise ValueError("Ordinary membership cannot override explicit same-event nonordinary role evidence")
        if e.get("body_verified") is not True or normalized_credit(e.get("role", "")) not in nonordinary:
            continue
        if e.get("event_subject_role", e.get("subject_role")) in {"author", "notice_author", "speaker"}:
            continue
        other_date = e.get("event_date")
        other_year = e.get("event_year")
        if other_date and accepted_date and other_date != accepted_date:
            continue
        same = (bool(other_date and accepted_date and other_date == accepted_date)
                or str(other_year) == str(year))
        if same and e.get("event_explicitly_separate_from_accepted_full_event") is not True:
            raise ValueError("Ordinary membership cannot override explicit same-event nonordinary role evidence")


def validate_france_positive(d, before, prior_evidence=None):
    require(d.get("previous_conflict_explicitly_resolved") is not True, "v12 cannot release inherited France election conflicts")
    if V3.flag(d["membership_accepted"]) != "1":
        return
    require(before.get("election_date_conflict") != "1", "Inherited France conflict must stay held")
    control = EXACT_UNRESOLVED_ROLE_CONTROLS.get(d["candidate_group_id"])
    if control:
        require(sha(ROOT / control["audit_file"]) == control["audit_sha256"], "Role negative-control evidence changed")
        raise ValueError("Exact unresolved source-role control cannot be promoted by a generic member row")
    precision = d.get("accepted_full_member_election_precision")
    accepted_date = d.get("accepted_full_member_election_date")
    accepted_year = d.get("accepted_full_member_election_year")
    if precision == "day":
        require(isinstance(accepted_date, str), "Accepted day required")
        day = datetime.date.fromisoformat(accepted_date)
        require(accepted_year in (None, "", day.year, str(day.year)), "Accepted day/year disagree")
        year = day.year
    else:
        require(precision == "year" and type(accepted_year) is int and not accepted_date, "Exact year precision required")
        year = accepted_year
    if prior_evidence is None:
        prior_evidence = inherited_france_role_evidence().get(d["candidate_group_id"], [])
    reject_same_event_nonordinary_role_conflict(d, year, accepted_date, prior_evidence)
    matching = []
    for e in d.get("evidence", []):
        parsed_source = urlparse(e.get("source_url", ""))
        if (parsed_source.hostname or "").lower() in {"cths.fr", "www.cths.fr"}:
            source_ids = parse_qs(parsed_source.query).get("id", [])
            if source_ids != [d["candidate_group_id"].removeprefix("CTHS_")]:
                continue
        if not (e.get("body_verified") is True and ordinary_subject_event(e) and e.get("role") in ORDINARY_ROLES and e.get("quote") and e.get("identity_note") and academy_original(e)):
            continue
        event_date, event_year = e.get("event_date"), e.get("event_year")
        if precision == "day":
            same = e.get("event_precision") == "day" and event_date == accepted_date and event_year in (None, "", year, str(year))
        else:
            same = e.get("event_precision") in {"day", "year"} and event_year in (year, str(year))
            if event_date:
                same = same and datetime.date.fromisoformat(event_date).year == year
        if same:
            if e.get("cths_notice_component_bundle_verified") is True:
                reviewed_component_acceptance(d, e)
            matching.append(e)
    require(matching, "Strict France acceptance needs a matching Academy-original ordinary-full-member event; correspondent/foreign events cannot substitute")


def france(decisions, dob_quarantines=None, individual_cases=None):
    base_rows = readcsv(BASE / "outputs/france_master877.csv")
    if individual_cases:
        apply_individual_case_decisions(base_rows, individual_cases)
    before = {r["candidate_group_id"]: r for r in base_rows}
    prior_roles = inherited_france_role_evidence()
    for d in decisions:
        require(d["candidate_group_id"] in before, "Unknown France identity")
        validate_france_positive(d, before[d["candidate_group_id"]], prior_roles.get(d["candidate_group_id"], []))
    rows, accepted, gaps, delta_ledger, summary = V3.france(base_rows, decisions)
    changed = {d["candidate_group_id"] for d in decisions}
    fields = ["membership_decision_status", "membership_review_reason", "evidence_urls", "election_source_conflict_retained"]
    for r in rows:
        old = before[r["candidate_group_id"]]
        for field in fields:
            r["v12_" + field] = r["v3_" + field] if r["candidate_group_id"] in changed else ""
            for version in ["v3_", "v4_", "v5_", "v6_", "v7_", "v8_", "v9_", "v10_", "v11_"]:
                r[version + field] = old.get(version + field, "")
        if r["candidate_group_id"] in changed:
            r["source_evidence_review_version"] = "France_v12_membership_continuation_20261030"
        else:
            r["membership_as_of_year"] = old.get("membership_as_of_year", "")
        require(old.get("election_date_conflict") != "1" or r["election_date_conflict"] == "1", "Inherited France conflict lost")
    # Retain the full predecessor decision ledger, including held source events, as immutable history.
    ledger = readcsv(BASE / "outputs/france_membership_decisions.csv") + delta_ledger
    summary.update(baseline_all_three_accepted=js(BASE / "outputs/summary.json")["france"]["all_three_accepted"],
                   all_three_net_change=len(accepted) - js(BASE / "outputs/summary.json")["france"]["all_three_accepted"],
                   inherited_v11_membership_decision_rows=len(ledger) - len(delta_ledger),
                   source_backed_decisions=len(decisions))
    if dob_quarantines:
        apply_france_dob_quarantines(rows, dob_quarantines)
        accepted = [r for r in rows if all(r[k+"_accepted"] == "1" for k in ["identity", "membership", "dob"])]
        gaps = [r for r in rows if r not in accepted]
        summary["current"]["dob_accepted"] = sum(r["dob_accepted"] == "1" for r in rows)
        summary["all_three_accepted"] = len(accepted)
        summary["all_three_remaining_gaps"] = len(gaps)
        summary["all_three_net_change"] = len(accepted) - js(BASE / "outputs/summary.json")["france"]["all_three_accepted"]
        summary["role_cutoff_and_dob_supported"] = sum(bool(r["role_cutoff_and_dob_supported"]) for r in rows)
    summary["known_exact_DOB_conflict_rows"] = sum(r["exact_dob_conflict"] == "1" for r in rows)
    summary["new_exact_DOB_conflict_quarantines"] = len(dob_quarantines or [])
    summary["DOB_quarantined_candidate_ids"] = [d["candidate_group_id"] for d in (dob_quarantines or [])]
    apply_unresolved_birthyear_controls(rows)
    summary["unresolved_birthyear_control_rows"] = sum(r.get("v12_dob_review_status") == UNRESOLVED_BIRTHYEAR_STATUS for r in rows)
    summary["baseline"] = baseline_summary()["france"]["current"]
    summary["new_individual_case_adjudications"] = len(individual_cases or [])
    summary["identity_approval_net_change"] = summary["current"]["identity_accepted"] - summary["baseline"]["identity_accepted"]
    summary["dob_approval_net_change"] = summary["current"]["dob_accepted"] - summary["baseline"]["dob_accepted"]
    return rows, accepted, gaps, ledger, summary



def processing_summary(root=ROOT):
    config = js(root / "inputs/batch_selection.json")
    result = {}
    for country, field in [("japan", "member_key"), ("france", "candidate_group_id")]:
        by_file, activity, outcomes = {}, {}, {}
        total = collections.Counter()
        for rel in config[country + "_processed_files"]:
            dispositions = processing_dispositions(root / "source_batches" / rel, field)
            counts = collections.Counter(dispositions.values())
            by_file[rel] = dict(counts)
            total.update(counts)
            outcomes.update(dispositions)
            summary_path = root / "source_batches" / Path(rel).parent / "summary.json"
            if summary_path.exists():
                activity[str(summary_path.relative_to(root))] = {k:v for k,v in js(summary_path).items() if type(v) in (int, float)}
        result[country] = dict(status_counts=dict(total), by_file=by_file,
                               explicit_outcome_rows=len(outcomes),
                               actually_processed_dispositions=sum(completed_status(s) for s in outcomes.values()),
                               not_processed_ids=sorted(k for k,s in outcomes.items() if not completed_status(s)),
                               batch_cache_scan_only_dispositions=sum(n for s, n in total.items() if "cache_scan_only_no_targeted_search" in s),
                               explicit_targeted_status_dispositions=sum(n for s, n in total.items() if s.startswith("targeted_")),
                               collector_reported_numeric_activity=activity,
                               note="Selection/outcome coverage is not completed processing or individual new-query coverage. Not-searched rows remain unprocessed. Exact status labels and collector-reported search metrics are separate; source-backed approval alone does not imply a targeted new search.")
    return result


def final_japan():
    """Reconstruct this study's complete approved final state for a successor."""
    return japan(js(ROOT / "inputs/japan_delta_claims.json"), js(ROOT / "inputs/japan_delta_holds.json"),
                 js(ROOT / "inputs/japan_delta_processed_ids.json"), js(ROOT / "inputs/japan_section_decisions.json"))


def verify_baseline_inheritance():
    """Verify inherited state independently of all new source approvals."""
    check_baseline()
    old_japan, old_claims, _, old_summary = previous_japan()
    rows, claims, queue, summary = japan([], {}, [])
    require(claims == old_claims, "Empty delta changed an inherited Japan claim")
    for before, after in zip(old_japan, rows):
        require({k: after[k] for k in before} == before, "Empty delta changed an inherited Japan field")
    old_france = readcsv(BASE / "outputs/france_master877.csv")
    france_rows, _, _, ledger, france_summary = france([])
    for before, after in zip(old_france, france_rows):
        require({k: str(after[k]) for k in before} == {k: str(v) for k, v in before.items()},
                "Empty delta changed an inherited France field")
    require(ledger == readcsv(BASE / "outputs/france_membership_decisions.csv"),
            "Empty delta changed inherited France decision history")
    return dict(baseline_commit=BASE_COMMIT, verification_scope="empty_delta_baseline",
                inherited_japan_rows=len(rows), inherited_japan_claims=len(claims),
                inherited_japan_day_statuses=summary["body_day_no_known_conflict"],
                inherited_japan_effective_holds=len(inherited_holds(old_japan)),
                inherited_japan_section_ii=summary["broad_section_ii_supported"],
                inherited_japan_section_i=summary["section_i_excluded"],
                inherited_japan_unresolved=summary["section_unresolved"],
                inherited_japan_queue=len(queue), inherited_france_rows=len(france_rows),
                inherited_france_current=france_summary["current"],
                inherited_france_all_three=france_summary["all_three_accepted"],
                every_old_field_and_claim_preserved=True, new_decisions=0,
                new_identity_DOB_approvals_applied_in_this_baseline_check=0)


def assemble(output):
    require(not output.exists(), "Fresh output directory required")
    check_baseline()
    expected = prepare()
    for name, value in expected.items():
        require(js(ROOT / "inputs" / name) == value, "Prepared input changed: " + name)
    jm, jl, jq, j = final_japan()
    jp_cross = set(js(ROOT / "inputs/batch_selection.json").get("japan_cross_source_member_keys", []))
    j["cross_source_additional_member_keys"] = sorted({c["member_key"] for c in js(ROOT / "inputs/japan_delta_claims.json") if c["member_key"] in jp_cross})
    j["cross_source_additional_candidates"] = len(j["cross_source_additional_member_keys"])
    individual_cases = js(ROOT / "inputs/france_individual_case_decisions.json")
    fm, fa, fg, fd, f = france(js(ROOT / "inputs/france_decisions.json"), js(ROOT / "inputs/france_dob_conflict_decisions.json"), individual_cases)
    f["newly_processed_v12_candidates"] = len(js(ROOT / "inputs/france_processed_ids.json"))
    cross = set(js(ROOT / "inputs/batch_selection.json").get("france_cross_source_candidate_ids", []))
    f["cross_source_additional_candidate_ids"] = sorted(d["candidate_group_id"] for d in js(ROOT / "inputs/france_decisions.json") if d["candidate_group_id"] in cross)
    f["cross_source_additional_candidates"] = len(f["cross_source_additional_candidate_ids"])
    output.mkdir(parents=True)
    for name, rows in [("japan_master.csv", jm), ("japan_birth_claims.csv", jl), ("japan_next_action_queue.csv", jq), ("france_master877.csv", fm), ("france_accepted_all_three.csv", fa), ("france_remaining_gaps.csv", fg), ("france_membership_decisions.csv", fd)]:
        J.write_csv(output / name, rows)
    if individual_cases:
        J.write_csv(output / "france_case_adjudications.csv", individual_cases)
    else:
        (output / "france_case_adjudications.csv").write_text("candidate_group_id,decision_type,previous_values,new_values,source_evidence,root_approval_record\n", encoding="utf-8")
    scope_processing = processing_summary()
    j["newly_source_processed_v12_candidates"] = scope_processing["japan"]["actually_processed_dispositions"]
    j["newly_DOB_processed_v12_candidates"] = len(js(ROOT / "inputs/japan_delta_processed_ids.json"))
    j["processing_boundary_note"] = "Section-source queries/body reviews are not birthday searches. DOB processing IDs change only for explicit birth-source review, not scope-only activity."
    summary = dict(date="2026-10-30", baseline_commit=BASE_COMMIT, japan=j, france=f,
                   fixed_selection_counts={k: len(v) for k, v in selections().items()}, actual_processed_counts={"japan": scope_processing["japan"]["actually_processed_dispositions"], "france": len(js(ROOT / "inputs/france_processed_ids.json"))}, japan_dob_processed_count=len(js(ROOT / "inputs/japan_delta_processed_ids.json")), processing_status_breakdown=scope_processing, professor_collection="paused", fields_collection="preserved_parked", collection_complete=False,
                   analysis_cohort_frozen=False, bazi_variables_computed=0)
    dump(output / "summary.json", summary)
    return summary


def verify():
    actual = {str(p.relative_to(ROOT)): sha(p) for p in ROOT.rglob("*") if p.is_file() and p != ROOT / "MANIFEST.json" and "__pycache__" not in p.parts}
    require(actual == js(ROOT / "MANIFEST.json")["files"], "Inventory/hash mismatch")
    require(not any("private" in Path(p).parts or p.endswith((".pdf", ".html", ".png", ".jpg", ".pyc")) for p in actual), "Raw/private source in deliverable")
    for rel in actual:
        parts = Path(rel).parts
        if parts[0] == "source_batches":
            require(len(parts) == 3 and (Path(rel).suffix in {".json", ".csv"} or parts[-1] in {"README.md", "README.txt"}), "Only top-level public source metadata is deliverable: " + rel)
    check_baseline()
    for name, value in prepare().items():
        require(js(ROOT / "inputs" / name) == value, "Prepared input mismatch: " + name)
    summary = js(ROOT / "outputs/summary.json")
    j, f = summary["japan"], summary["france"]
    require(summary["fixed_selection_counts"] == {k: len(v) for k, v in selections().items()}, "Fixed selection coverage changed")
    require(summary["actual_processed_counts"] == {"japan": summary["processing_status_breakdown"]["japan"]["actually_processed_dispositions"], "france": len(js(ROOT / "inputs/france_processed_ids.json"))}, "Actual processing accounting mismatch")
    require(summary["japan_dob_processed_count"] == len(js(ROOT / "inputs/japan_delta_processed_ids.json")), "DOB processing accounting mismatch")
    require(summary["processing_status_breakdown"]["france"]["explicit_outcome_rows"] == len(selections()["france"]), "France outcomes incomplete")
    require(summary["processing_status_breakdown"]["japan"]["explicit_outcome_rows"] == len(selections()["japan"]), "Japan outcomes incomplete")
    require(summary["processing_status_breakdown"]["japan"]["actually_processed_dispositions"] == summary["actual_processed_counts"]["japan"], "Unsearched Japan rows counted as processed")
    require(summary["processing_status_breakdown"]["france"]["actually_processed_dispositions"] == summary["actual_processed_counts"]["france"], "Unsearched France rows counted as processed")
    require(j["restored_candidate_universe"] == baseline_summary()["japan"]["restored_candidate_universe"] and j["broad_section_ii_supported"] + j["section_i_excluded"] + j["section_unresolved"] == baseline_summary()["japan"]["restored_candidate_universe"], "Japan scope accounting changed")
    require(j["new_section_decisions"] == len(js(ROOT / "inputs/japan_section_decisions.json")), "Section decision accounting mismatch")
    require(j["baseline_day_no_known_conflict"] == baseline_summary()["japan"]["body_day_no_known_conflict"], "Wrong Japan baseline")
    require(j["body_day_no_known_conflict"] == j["institutional_or_university_supported_day_no_known_conflict"] + j["edited_reference_only_day_no_known_conflict"] + j["other_attributed_secondary_only_day_no_known_conflict"], "Source tier totals mismatch")
    require(j["nonexcluded_body_day_no_known_conflict"] + j["nonexcluded_dob_not_day_count"] == j["nonexcluded_science_and_unresolved_candidates"], "Japan DOB accounting mismatch")
    cases = js(ROOT / "inputs/france_individual_case_decisions.json")
    identity_gain = sum(d["new_values"].get("identity_accepted") == "1" for d in cases)
    dob_gain = sum(d["new_values"].get("dob_accepted") == "1" for d in cases)
    require((f["candidate_groups"], f["current"]["identity_accepted"], f["current"]["dob_accepted"]) == (baseline_summary()["france"]["candidate_groups"], baseline_summary()["france"]["current"]["identity_accepted"] + identity_gain, baseline_summary()["france"]["current"]["dob_accepted"] + dob_gain - len(js(ROOT / "inputs/france_dob_conflict_decisions.json"))), "France nonmembership dimensions changed outside exact reviewed cases/quarantines")
    require(f["new_individual_case_adjudications"] == len(cases)
            and len(readcsv(ROOT / "outputs/france_case_adjudications.csv")) == len(cases), "Individual-case ledger accounting mismatch")
    require(f["current"]["membership_accepted"] >= baseline_summary()["france"]["current"]["membership_accepted"] and f["all_three_accepted"] >= baseline_summary()["france"]["all_three_accepted"], "France approvals lost")
    require(f["known_election_conflict_rows"] >= baseline_summary()["france"]["known_election_conflict_rows"], "Inherited France chronology holds lost")
    require(f["all_three_accepted"] + f["all_three_remaining_gaps"] == baseline_summary()["france"]["candidate_groups"], "France gap accounting mismatch")
    require(not summary["analysis_cohort_frozen"] and summary["bazi_variables_computed"] == 0, "Analysis gate changed")
    require(j["calendar_conversions_performed"] == j["default_date_components_filled"] == j["analysis_record_count"] == 0, "Japan collection gates changed")
    require(all(r["final_cohort_accepted"] == "False" and r["bazi_variables_computed"] == "0" for r in readcsv(ROOT / "outputs/japan_master.csv")), "Japan final cohort gate changed")
    with tempfile.TemporaryDirectory(prefix=".verify-replay-", dir=ROOT) as folder:
        replay = Path(folder) / "outputs"
        assemble(replay)
        require({p.name for p in replay.iterdir()} == {p.name for p in (ROOT / "outputs").iterdir()}, "Output inventory differs from deterministic replay")
        for path in replay.iterdir():
            require(path.read_bytes() == (ROOT / "outputs" / path.name).read_bytes(), "Output byte replay mismatch: " + path.name)
    print(f"{len(actual)} pinned v12 files verified; v11 evidence and fixed processing scope preserved")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["baseline", "prepare", "assemble", "verify"])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.mode == "baseline":
        print(json.dumps(verify_baseline_inheritance(), ensure_ascii=False))
    elif args.mode == "verify":
        verify()
    elif args.mode == "prepare":
        require(args.output_dir is not None and not args.output_dir.exists(), "Fresh output directory required")
        values = prepare()
        args.output_dir.mkdir(parents=True)
        for name, value in values.items():
            dump(args.output_dir / name, value)
    else:
        require(args.output_dir is not None, "Output directory required")
        summary = assemble(args.output_dir)
        print(json.dumps({"japan_day": summary["japan"]["body_day_no_known_conflict"], "france_membership": summary["france"]["current"]["membership_accepted"]}))


if __name__ == "__main__":
    main()
