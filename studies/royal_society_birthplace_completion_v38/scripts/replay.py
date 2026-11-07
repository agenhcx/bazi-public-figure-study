#!/usr/bin/env python3
"""Reconstruct exact UK v37, then apply v38 geography-only observations.

The v10 carrier and frozen v11/v12/v13/v14/v15/v16/v17/v18/v19/v20/v21/v22/v23/v24/v25/v26/v27/v28/v29/v30/v31/v32/v33/v34/v35/v36 inputs are self-contained.
First-birthplace source grades remain separate from frozen native DOB grades.
Canonical JSONL hashes avoid relying on Python-specific gzip headers.
"""
import copy
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_V33_CANONICAL = '773cd149b4ee77d77233d81ac37fefa1e861a98c375b3d1c285ae36a32aa9847'
V33_SOURCE_COMMIT = '433064a032cf85a26c81959621df4240c9d02190'
EXPECTED_V34_CANONICAL = '271a32070f8dae8c54933f1ebaacc5ae141427a3448f8f1562000f8842a0c632'
V34_SOURCE_COMMIT = 'ea8f974cb7029714906c2f5ceb9cc1e1bc2594e1'
EXPECTED_V35_CANONICAL = '271a32070f8dae8c54933f1ebaacc5ae141427a3448f8f1562000f8842a0c632'
V35_SOURCE_COMMIT = '462860b8b9a7937c7fbe436790a64db863ee0a39'
EXPECTED_V10 = 'e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
EXPECTED_V11_CANONICAL = '577515b90cff05d61288222a4daf595aaaed76a1baa16ab96391720b02c32da6'
EXPECTED_V12_CANONICAL = '1b6318ed3e7056886949b47ff08f65eaa518a355cede9de67be934088eadf108'
EXPECTED_V13_CANONICAL = '1b6318ed3e7056886949b47ff08f65eaa518a355cede9de67be934088eadf108'
EXPECTED_V14_CANONICAL = '1b6318ed3e7056886949b47ff08f65eaa518a355cede9de67be934088eadf108'
EXPECTED_V15_CANONICAL = 'c05181f1d910507405ed5ae728aeecb2430b36ba01ea7ced1f84694f1d026255'
EXPECTED_V16_CANONICAL = '4811ffec9a75ac2d9488bc2a1bd97922369bf40b27362a59fb9d4ddfdcfd3d9f'
EXPECTED_V17_CANONICAL = '4354dfa3272b960448ba2614d76c4cda6539ae9aa8cb0898eb8f9b1de7a3bde4'
EXPECTED_V18_CANONICAL = 'f515cb1b649f3408d960b8dacd9ccdfddb82dab312adb2c95c0f4480b43feaf8'
EXPECTED_V19_CANONICAL = '5c8d93078101a69b32c9652c6bcbc99ce926c2dd4bd50547e235071ae377c043'
EXPECTED_V20_CANONICAL = 'bbe9e22d00c4bfb3fb7a390df6a18a349e0abe64ba2986cd5075650f62ae9f2b'
EXPECTED_V21_CANONICAL = '91b14b75fa13811abed8122644ed4b10f739fef5695ee72ed62ad5fd296bcac2'
EXPECTED_V22_CANONICAL = '728502a5f0a71570a262a894dc800a9073ff19bbba68e2c7a7dd7027a5f8f2b9'
EXPECTED_V23_CANONICAL = '9547b9e958d6526acf578a20f3b42e63e5a95de3aeca91a3c244d9620ee7ab01'
EXPECTED_V24_CANONICAL = '77d03a85ab2c959d1fc34732907535c2fa465b36fa6b1ab176bb4e66de6c5d0d'
EXPECTED_V25_CANONICAL = 'b36383e9ac72642059c2f9b5ff6c57187c8b04477bb5830ebf85b61a12cda730'
EXPECTED_V26_CANONICAL = '41aebb4d4c05b6c45889315892b5edcfa1f10c2a7d16fe75e6608e0e3dc07378'
EXPECTED_V27_CANONICAL = 'ac6d3db5594801b9c55e271b392eb245fc8ae66216c0031eb5686ba82a545118'
EXPECTED_V28_CANONICAL = '697389a67f48c88f214b8efc832a1f8744fcab34a4882f581215d75c8755403e'
EXPECTED_V29_CANONICAL = 'e528b4afce6ded29ff6af749b4d46a8d7b9d0bce7d57d34ac8f1366421bbce73'
EXPECTED_V30_CANONICAL = '4313e08b77eee084ed6ba828b1490a57deba8fab502a6fe09a4780db8ac14e8a'
EXPECTED_V31_CANONICAL = 'c9c6b0d913c4ec0a8ff9a5d458ad8707da398ded149b86cd3c2794ee8f1d1932'
EXPECTED_V32_CANONICAL = '73ee2d8621c03ecdb1a4fa15c558215f40c0868aab0344a790cfccb6e264bbaa'
V32_SOURCE_COMMIT = 'a9c824bfb374035912eb6c36a8e631ccbb4177e1'
V31_SOURCE_COMMIT = '6445f1752e71713e6c97b245e027d3912f1d1abf'
V30_SOURCE_COMMIT = 'd8a19a4ea5f8e84480f313c54c8e9cedb3e5ff17'
V29_SOURCE_COMMIT = '8c801f03dd42fb497d437ede34d6caf0d3a41e4a'
V28_SOURCE_COMMIT = 'f2770a948ce55ba7ffe9e2fbf9116956d4e4a1c2'
V27_SOURCE_COMMIT = '688209fe6319dc3f4c70a74918d72cf7ebbdb016'
V26_SOURCE_COMMIT = '3d51d6739c7319a1a39b2c4d7f730b4a8b02fb05'
V25_SOURCE_COMMIT = '65494e28c0b3ad9bd28538bd45daca5df8232b07'
V24_SOURCE_COMMIT = '4c0a23054048645b632bcaccc96f2fe7ae60dfef'
V23_SOURCE_COMMIT = 'd0933cbe05a4a6549ac66a6c9078fbbb822666bf'
V22_SOURCE_COMMIT = 'b3c22b66be309470b5e17ad1d0f681bf71ed581f'
V21_SOURCE_COMMIT = '065a8a5e438b6fadb85756df6ad513fb9aba27ae'
V20_SOURCE_COMMIT = '4f15eecc06904eee10005d1c2a09eaea9771e834'
V19_SOURCE_COMMIT = '25b6b8f40d148d2e6c61235675446bbbfbdb4928'
V18_SOURCE_COMMIT = 'd7fa790be25c26e8fc07d92976a7dc4052e1f527'
V17_SOURCE_COMMIT = '1804b275112484268a1fd0f41318ea9cb85b2125'
V16_SOURCE_COMMIT = '72edac7cceca5cc4aa077dddc8c5fde401059b36'
V15_FOLLOWUP_SCOPE = {'RS_PAST_NA3607', 'RS_PAST_NA3629', 'RS_PAST_NA3957', 'RS_PAST_NA3652',
                  'RS_PAST_NA4682', 'RS_PAST_NA4250', 'RS_PAST_NA4117', 'RS_PAST_NA4780'}
V16_FOLLOWUP_SCOPE = {
    'RS_PAST_NA3088', 'RS_PAST_NA3964', 'RS_PAST_NA4211', 'RS_PAST_NA4680',
    'RS_PAST_NA5416', 'RS_PAST_NA3971', 'RS_PAST_NA4568', 'RS_PAST_NA4774',
    'RS_PAST_NA4050', 'RS_PAST_NA6870', 'RS_PAST_NA6897', 'RS_PAST_NA4863'
}
V17_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4155', 'RS_PAST_NA5003', 'RS_PAST_NA629', 'RS_PAST_NA5508',
    'RS_PAST_NA6313', 'RS_PAST_NA645', 'RS_PAST_NA637', 'RS_PAST_NA4592'
}
V17_REVIEWED_SCOPE = {
    'RS_PAST_NA1266', 'RS_PAST_NA1376', 'RS_PAST_NA1614', 'RS_PAST_NA2688',
    'RS_PAST_NA3483', 'RS_PAST_NA4155', 'RS_PAST_NA4592', 'RS_PAST_NA5003',
    'RS_PAST_NA5508', 'RS_PAST_NA5620', 'RS_PAST_NA629', 'RS_PAST_NA6313',
    'RS_PAST_NA637', 'RS_PAST_NA645', 'RS_PAST_NA7080'
}
V18_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA1744', 'RS_PAST_NA3830', 'RS_PAST_NA4918', 'RS_PAST_NA8089',
    'RS_PAST_NA3358', 'RS_PAST_NA5962', 'RS_PAST_NA6938', 'RS_PAST_NA4005'
}
V18_REVIEWED_SCOPE = {
    'RS_PAST_NA1376', 'RS_PAST_NA1744', 'RS_PAST_NA3358',
    'RS_PAST_NA3830', 'RS_PAST_NA4005', 'RS_PAST_NA4918',
    'RS_PAST_NA5962', 'RS_PAST_NA6938', 'RS_PAST_NA8089'
}
V19_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA3979',
    'RS_PAST_NA4485',
    'RS_PAST_NA4601',
    'RS_PAST_NA4667',
    'RS_PAST_NA3912',
    'RS_PAST_NA4627',
    'RS_PAST_NA4614',
    'RS_PAST_NA2099',
    'RS_PAST_NA4636',
    'RS_PAST_NA4124',
    'RS_CURRENT_11792',
    'RS_CURRENT_37377',
}
V20_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4036', 'RS_PAST_NA4166', 'RS_PAST_NA4179', 'RS_PAST_NA4490',
    'RS_PAST_NA2044', 'RS_PAST_NA2090', 'RS_PAST_NA4170', 'RS_PAST_NA1998'
}
V21_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4651', 'RS_PAST_NA4585', 'RS_PAST_NA4834', 'RS_PAST_NA4076',
    'RS_PAST_NA8672', 'RS_PAST_NA8700', 'RS_PAST_NA5885', 'RS_PAST_NA9858'
}
V22_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4252', 'RS_PAST_NA4747', 'RS_PAST_NA4220', 'RS_PAST_NA3931',
    'RS_PAST_NA4193', 'RS_PAST_NA6876', 'RS_PAST_NA3621', 'RS_PAST_NA3635'
}
V23_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4139', 'RS_PAST_NA4064', 'RS_PAST_NA4074', 'RS_PAST_NA4591',
    'RS_PAST_NA3474', 'RS_PAST_NA4233', 'RS_PAST_NA4301', 'RS_PAST_NA4642',
    'RS_PAST_NA4616', 'RS_PAST_NA4630', 'RS_PAST_NA7048', 'RS_PAST_NA5422'
}
V24_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA6228',
    'RS_PAST_NA6648',
    'RS_PAST_NA5494',
    'RS_PAST_NA5506',
    'RS_PAST_NA6968',
    'RS_PAST_NA2977',
    'RS_PAST_NA2863',
    'RS_PAST_NA178',
    'RS_PAST_NA6655',
    'RS_PAST_NA6775',
    'RS_PAST_NA6941',
    'RS_PAST_NA8294',
}
V25_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA1176',
    'RS_PAST_NA1177',
    'RS_PAST_NA1090',
    'RS_PAST_NA1476',
    'RS_PAST_NA2684',
    'RS_PAST_NA7012',
    'RS_PAST_NA7070',
    'RS_PAST_NA8048',
    'RS_PAST_NA8257',
    'RS_PAST_NA785',
    'RS_PAST_NA1823',
    'RS_PAST_NA1611',
}
V26_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA1134',
    'RS_PAST_NA1196',
    'RS_PAST_NA1323',
    'RS_PAST_NA1361',
    'RS_PAST_NA1593',
    'RS_PAST_NA173',
    'RS_PAST_NA1855',
    'RS_PAST_NA187',
    'RS_PAST_NA6572',
    'RS_PAST_NA732',
    'RS_PAST_NA780',
    'RS_PAST_NA788',
}
V27_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA1585',
    'RS_PAST_NA1937',
    'RS_PAST_NA1951',
    'RS_PAST_NA1967',
    'RS_PAST_NA1973',
    'RS_PAST_NA1994',
    'RS_PAST_NA2005',
    'RS_PAST_NA2016',
    'RS_PAST_NA2025',
    'RS_PAST_NA2030',
    'RS_PAST_NA2033',
    'RS_PAST_NA2049',
}
V28_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA2092',
    'RS_PAST_NA2121',
    'RS_PAST_NA2133',
    'RS_PAST_NA2245',
    'RS_PAST_NA3113',
    'RS_PAST_NA3622',
    'RS_PAST_NA3626',
    'RS_PAST_NA386',
    'RS_PAST_NA3918',
    'RS_PAST_NA3961',
    'RS_PAST_NA4091',
    'RS_PAST_NA4189',
}
V29_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4208',
    'RS_PAST_NA4384',
    'RS_PAST_NA448',
    'RS_PAST_NA4535',
    'RS_PAST_NA4681',
    'RS_PAST_NA504',
    'RS_PAST_NA5088',
    'RS_PAST_NA5089',
    'RS_PAST_NA530',
    'RS_PAST_NA5362',
    'RS_PAST_NA604',
    'RS_PAST_NA611',
    'RS_PAST_NA6300',
    'RS_PAST_NA661',
    'RS_PAST_NA753',
    'RS_PAST_NA831',
    'RS_PAST_NA8663',
    'RS_PAST_NA8828',
}
V36_METHOD_ID = 'uk-geography-canonical-community-reference-pilot-v1'
V36_PROOF_MODES = ('direct_born_region_in_actual_canonical_person_body', 'explicit_person_born_place_hyperlink_then_actual_target_place_region', 'actual_person_P19_entity_then_actual_P131_admin_chain_to_whole_region')
V36_GEOGRAPHY_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4155',
    'RS_PAST_NA6868',
    'RS_PAST_NA3578',
    'RS_PAST_NA3609',
    'RS_PAST_NA813',
    'RS_PAST_NA872',
}
V36_GEOGRAPHY_FIELD = 'geography_followup_v36'
V35_GEOGRAPHY_FOLLOWUP_SCOPE = {
    'RS_PAST_NA6941',
    'RS_PAST_NA780',
    'RS_PAST_NA813',
    'RS_PAST_NA872',
    'RS_PAST_NA8828',
    'RS_PAST_NA907',
}
V35_GEOGRAPHY_FIELD = 'geography_followup_v35'
V34_GEOGRAPHY_FOLLOWUP_SCOPE = {
    'RS_PAST_NA3474',
    'RS_PAST_NA4568',
    'RS_PAST_NA5494',
    'RS_PAST_NA6231',
    'RS_PAST_NA6313',
    'RS_PAST_NA6434',
    'RS_PAST_NA645',
    'RS_PAST_NA661',
    'RS_PAST_NA663',
    'RS_PAST_NA6655',
    'RS_PAST_NA669',
    'RS_PAST_NA6847',
}
V34_GEOGRAPHY_FIELD = 'geography_followup_v34'
V33_GEOGRAPHY_FOLLOWUP_SCOPE = {
    'RS_PAST_NA1994',
    'RS_PAST_NA2016',
    'RS_PAST_NA2146',
    'RS_PAST_NA2153',
    'RS_PAST_NA2154',
    'RS_PAST_NA2460',
    'RS_PAST_NA2863',
    'RS_PAST_NA331',
    'RS_PAST_NA3578',
    'RS_PAST_NA3609',
    'RS_PAST_NA3620',
    'RS_PAST_NA5124',
}
V33_GEOGRAPHY_FIELD = 'geography_followup_v33'
V32_GEOGRAPHY_FOLLOWUP_SCOPE = {
    'RS_PAST_NA1324',
    'RS_PAST_NA1475',
    'RS_PAST_NA1476',
    'RS_PAST_NA1611',
    'RS_PAST_NA1513',
    'RS_PAST_NA1592',
    'RS_PAST_NA1727',
    'RS_PAST_NA1752',
    'RS_PAST_NA2044',
    'RS_PAST_NA2080',
    'RS_PAST_NA2099',
    'RS_PAST_NA2111',
}
V32_GEOGRAPHY_FIELD = 'geography_followup_v32'
V31_GEOGRAPHY_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4680',
    'RS_PAST_NA4155',
    'RS_PAST_NA6868',
    'RS_PAST_NA4113',
    'RS_PAST_NA8736',
    'RS_PAST_NA8744',
    'RS_PAST_NA4166',
    'RS_PAST_NA1580',
    'RS_PAST_NA5065',
    'RS_PAST_NA4747',
    'RS_PAST_NA5962',
    'RS_PAST_NA7080',
}
V31_GEOGRAPHY_FIELD = 'geography_followup_v31'
V30_GEOGRAPHY_FOLLOWUP_SCOPE = {
    'RS_CURRENT_10965',
    'RS_PAST_NA2007',
    'RS_PAST_NA1998',
    'RS_PAST_NA2892',
    'RS_PAST_NA187',
    'RS_PAST_NA173',
    'RS_PAST_NA4571',
    'RS_PAST_NA4636',
    'RS_PAST_NA5003',
    'RS_PAST_NA4774',
    'RS_PAST_NA6938',
    'RS_PAST_NA8835',
}
V30_GEOGRAPHY_FIELD = 'geography_followup_v30'
GEOGRAPHY_PILOT_SCOPE = {'RS_PAST_NA4918'}
V20_GEOGRAPHY_FIELD = 'geography_followup_v20'
BIRTHPLACE_FIELD = 'birthplace_followup_v29'
GEOGRAPHY_FIELD = 'geography_followup_v14'
WINDOW_START, WINDOW_END = date(1835, 1, 1), date(1985, 12, 31)
GEO_FIELDS = {'hemisphere', 'geo_resolution_status', 'geography_decision',
              'reason', 'northern_birthplace_candidate', 'southern_birthplace_separate'}


def canonical_bytes(rows):
    return ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
                   for r in rows).encode('utf-8')


def encode_gzip(rows):
    # GzipFile uses a fixed OS header; filename and mtime are explicitly blank/zero.
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buf, compresslevel=9, mtime=0) as stream:
        stream.write(canonical_bytes(rows))
    return buf.getvalue()


def in_window(row):
    return WINDOW_START <= date.fromisoformat(row['dob']) <= WINDOW_END


def json_file(path):
    return json.loads(path.read_text(encoding='utf-8'))


def apply_context(rows, facts, version):
    """Apply one accepted context object per unknown cohort key; retain old evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate accepted keys'
    row_ids = {row['record_id'] for row in rows}
    assert set(by_id) <= row_ids, 'Accepted key outside fixed cohort'
    context_field = 'birthplace_followup_' + version
    allowed = GEO_FIELDS | {context_field}
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown', before['record_id']
            assert before['dob'] == fact['native_dob'], before['record_id']
            assert before['source_authorised_full_name'] == fact['authority_name'], before['record_id']
            assert before['raw_birthplace'], 'This batch refines existing explicit birthplaces only'
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}
            assert context_field not in before, 'Already supplemented at this version'
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_' + version + '_explicit_region_context',
                         geography_decision=version + '_explicit_birthplace_region_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_region',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[context_field] = fact
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'prior_raw_birthplace': before['raw_birthplace'],
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'qualified_context': fact['qualified_context'],
                            'new_context_source_grade': fact['source_grade'],
                            'source_url': fact['source_url']})
        assert set(before) <= set(after)
        assert (set(after) - set(before)) <= {context_field}
        for key in before:
            if key not in allowed:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert before == after
        updated.append(after)
    assert [r['record_id'] for r in updated] == [r['record_id'] for r in rows]
    assert len(changes) == len(facts)
    return updated, changes


def load_v11():
    raw = (ROOT / 'inputs' / 'uk_birthplace_rows_v10.jsonl.gz').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_V10
    v10 = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    assert len(v10) == 4983
    assert len({row['record_id'] for row in v10}) == 4983
    assert Counter(row['hemisphere'] for row in v10) == {'north': 4155, 'south': 183, 'unknown': 645}
    v11_facts = json_file(ROOT / 'inputs' / 'v11_accepted_context.json')
    assert len(v11_facts) == 3
    v11, _ = apply_context(v10, v11_facts, 'v11')
    assert hashlib.sha256(canonical_bytes(v11)).hexdigest() == EXPECTED_V11_CANONICAL
    assert Counter(row['hemisphere'] for row in v11) == {'north': 4158, 'south': 183, 'unknown': 642}
    window = [row for row in v11 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2258, 'south': 178, 'unknown': 208}
    return v11


def load_v12():
    v11 = load_v11()
    v12_facts = json_file(ROOT / 'inputs' / 'v12_accepted_context.json')
    assert len(v12_facts) == 1
    v12, _ = apply_context(v11, v12_facts, 'v12')
    assert hashlib.sha256(canonical_bytes(v12)).hexdigest() == EXPECTED_V12_CANONICAL
    assert Counter(row['hemisphere'] for row in v12) == {'north': 4159, 'south': 183, 'unknown': 641}
    window = [row for row in v12 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2259, 'south': 178, 'unknown': 207}
    return v12


def load_v13():
    v12 = load_v12()
    v13_facts = json_file(ROOT / 'inputs' / 'v13_accepted_context.json')
    assert v13_facts == [], 'Frozen v13 accepted context must remain empty'
    v13, _ = apply_context(v12, v13_facts, 'v13')
    assert hashlib.sha256(canonical_bytes(v13)).hexdigest() == EXPECTED_V13_CANONICAL
    assert Counter(row['hemisphere'] for row in v13) == {'north': 4159, 'south': 183, 'unknown': 641}
    window = [row for row in v13 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2259, 'south': 178, 'unknown': 207}
    return v13



def load_v14():
    v13 = load_v13()
    v14_facts = json_file(ROOT / 'inputs' / 'v14_accepted_geography.json')
    assert v14_facts == [], 'Frozen v14 principal geography acceptance must remain empty'
    assert hashlib.sha256(canonical_bytes(v13)).hexdigest() == EXPECTED_V14_CANONICAL
    return v13


BIRTHPLACE_FIELDS = {'raw_birthplace', 'birthplace_source_grade', 'birthplace_source_url',
                    'birthplace_source_urls', 'birthplace_claim_excerpt',
                    'birthplace_claim_status', 'birthplace_evidence_kind'}
MUTABLE_OLD_FIELDS = BIRTHPLACE_FIELDS | GEO_FIELDS


def target_ids_from_rows(rows):
    return [row['record_id'] for row in rows
            if row['hemisphere'] == 'unknown' and not row.get('raw_birthplace') and in_window(row)]


def apply_first_birthplaces(rows, facts, target_ids, version, followup_scope):
    """Adopt explicit person-birthplace observations without changing native fields."""
    context_field = 'birthplace_followup_' + version
    assert version in {'v15', 'v16', 'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29'}
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate accepted birthplace keys'
    assert set(by_id) <= set(followup_scope), 'Accepted key outside fixed original-source followups'
    assert set(by_id) <= set(target_ids), 'Accepted key outside frozen blank-place window'
    row_ids = [row['record_id'] for row in rows]
    assert len(set(row_ids)) == len(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown', before['record_id']
            assert not before.get('raw_birthplace'), 'This stage only adopts first stored birthplaces'
            assert before['dob'] == fact['native_dob'], before['record_id']
            assert before['source_authorised_full_name'] == fact['authority_name'], before['record_id']
            if version in {'v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29'} and not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip(), 'Current record needs nonempty stored name'
                assert fact.get('native_full_name') == before['name'], 'Blank authority requires exact stored native full name'
            assert context_field not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact['raw_birthplace'], str) and fact['raw_birthplace'].strip()
            assert isinstance(fact['source_url'], str) and fact['source_url'].strip()
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str)
            if version in {'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29'}:
                # A labeled structured birthplace field need not become a prose quote.
                if not source_quote.strip():
                    assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured-field evidence'
                    assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip(), 'Structured field needs an original-source locator'
                assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
                assert len(source_quote.split()) <= 25, 'New source quote exceeds25 words'
            else:
                assert source_quote.strip()
                if version == 'v16':
                    assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
                    assert len(source_quote.split()) <= 25, 'New source quote exceeds25 words'
            assert fact['identity_review'], 'Reviewed person-source binding is required'
            assert fact['geographic_basis'], 'Geography rationale, including unknown, is required'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south', 'unknown'}
            source_urls = fact.get('source_urls', [fact['source_url']])
            assert isinstance(source_urls, list) and all(isinstance(u, str) and u.strip() for u in source_urls)
            source_urls = list(dict.fromkeys([fact['source_url'], *source_urls]))
            previous = {key: copy.deepcopy(before[key]) for key in sorted(MUTABLE_OLD_FIELDS) if key in before}
            absent = sorted(MUTABLE_OLD_FIELDS - set(before))
            if 'previous_birthplace_fields' in fact:
                assert fact['previous_birthplace_fields'] == previous, 'Supplied rollback snapshot differs from baseline'
            if 'previous_absent_birthplace_fields' in fact:
                assert fact['previous_absent_birthplace_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_birthplace_fields'] = previous
            retained['previous_absent_birthplace_fields'] = absent
            retained['source_grade_role'] = 'person_birthplace_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['prior_selected_evidence_kept_as_history'] = True
            after.update(raw_birthplace=fact['raw_birthplace'],
                         birthplace_source_grade=fact['source_grade'],
                         birthplace_source_url=fact['source_url'],
                         birthplace_source_urls=source_urls,
                         birthplace_claim_excerpt=source_quote,
                         birthplace_claim_status='recovered_explicit_birthplace_' + version,
                         birthplace_evidence_kind=version + '_reviewed_explicit_person_birthplace',
                         hemisphere=hemisphere,
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            if hemisphere == 'unknown':
                after.update(geo_resolution_status='unresolved_' + version + '_birthplace_context',
                             geography_decision=version + '_explicit_birthplace_geography_unresolved',
                             reason='new_explicit_birthplace_geography_unresolved')
            else:
                directional = 'northern' if hemisphere == 'north' else 'southern'
                after.update(geo_resolution_status='resolved_by_' + version + '_explicit_birthplace_region',
                             geography_decision=version + '_reviewed_explicit_birthplace_region',
                             reason='explicit_birthplace_context_wholly_' + directional + '_region')
            after[context_field] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'before_raw_birthplace': before.get('raw_birthplace', ''),
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after['birthplace_source_grade'],
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': hemisphere != 'unknown',
                            'source_url': fact['source_url'],
                            'source_grade_role': 'person_birthplace_support_only',
                            'native_DOB_source_grade_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (MUTABLE_OLD_FIELDS | {context_field})
        for key in before:
            if key not in MUTABLE_OLD_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def apply_geography_only(rows, facts, pilot_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(pilot_ids) <= GEOGRAPHY_PILOT_SCOPE
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V20_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v20_reviewed_authority_birthplace_edge',
                         geography_decision='v20_geography_only_reviewed_authority_birthplace_edge',
                         reason='explicit_birthplace_authority_edge_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V20_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V20_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def load_v15():
    baseline = load_v14()
    target_ids = json_file(ROOT / 'inputs' / 'v15_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v15_followup_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 169
    assert target_ids == target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 8
    assert set(followup_ids) == V15_FOLLOWUP_SCOPE
    facts = json_file(ROOT / 'inputs' / 'v15_accepted_birthplaces.json')
    assert len(facts) == 5
    v15, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v15', V15_FOLLOWUP_SCOPE)
    assert hashlib.sha256(canonical_bytes(v15)).hexdigest() == EXPECTED_V15_CANONICAL
    assert Counter(row['hemisphere'] for row in v15) == {'north': 4162, 'south': 185, 'unknown': 636}
    window = [row for row in v15 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2262, 'south': 180, 'unknown': 202}
    assert len(target_ids_from_rows(v15)) == 164
    return v15


def load_v16():
    baseline = load_v15()
    target_ids = json_file(ROOT / 'inputs' / 'v16_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v16_followup_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 164
    assert target_ids == target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 12
    assert set(followup_ids) == V16_FOLLOWUP_SCOPE
    facts = json_file(ROOT / 'inputs' / 'v16_accepted_birthplaces.json')
    assert len(facts) == 5
    v16, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v16', V16_FOLLOWUP_SCOPE)
    assert hashlib.sha256(canonical_bytes(v16)).hexdigest() == EXPECTED_V16_CANONICAL
    assert Counter(row['hemisphere'] for row in v16) == {'north': 4163, 'south': 186, 'unknown': 634}
    window = [row for row in v16 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2263, 'south': 181, 'unknown': 200}
    assert len(target_ids_from_rows(v16)) == 159
    return v16



def load_v17():
    baseline = load_v16()
    target_ids = json_file(ROOT / 'inputs' / 'v17_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v17_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v17_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 159
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V17_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 15
    assert set(reviewed_ids) == V17_REVIEWED_SCOPE
    assert set(individual_ids) <= set(reviewed_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v17_accepted_birthplaces.json')
    assert len(facts) == 11
    v17, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v17', reviewed_ids)
    assert hashlib.sha256(canonical_bytes(v17)).hexdigest() == EXPECTED_V17_CANONICAL
    assert Counter(row['hemisphere'] for row in v17) == {'north': 4169, 'south': 186, 'unknown': 628}
    window = [row for row in v17 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2269, 'south': 181, 'unknown': 194}
    assert len(target_ids_from_rows(v17)) == 148
    return v17


def load_v18():
    baseline = load_v17()
    target_ids = json_file(ROOT / 'inputs' / 'v18_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v18_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v18_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 148
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V18_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 9
    assert set(reviewed_ids) == V18_REVIEWED_SCOPE
    assert set(individual_ids) <= set(reviewed_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v18_accepted_birthplaces.json')
    assert len(facts) == 3
    v18, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v18', reviewed_ids)
    assert hashlib.sha256(canonical_bytes(v18)).hexdigest() == EXPECTED_V18_CANONICAL
    assert Counter(row['hemisphere'] for row in v18) == {'north': 4169, 'south': 186, 'unknown': 628}
    window = [row for row in v18 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2269, 'south': 181, 'unknown': 194}
    assert len(target_ids_from_rows(v18)) == 145
    return v18


def load_v19():
    baseline = load_v18()
    target_ids = json_file(ROOT / 'inputs' / 'v19_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v19_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v19_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 145
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == V19_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == V19_INDIVIDUAL_FOLLOWUP_SCOPE
    facts = json_file(ROOT / 'inputs' / 'v19_accepted_birthplaces.json')
    assert len(facts) == 4
    v19, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v19', reviewed_ids)
    assert hashlib.sha256(canonical_bytes(v19)).hexdigest() == EXPECTED_V19_CANONICAL
    assert {row['cohort'] for row in v19} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v19) == {'north': 4171, 'south': 186, 'unknown': 626}
    window = [row for row in v19 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2271, 'south': 181, 'unknown': 192}
    assert len(target_ids_from_rows(v19)) == 141
    return v19


def load_v20():
    baseline = load_v19()
    target_ids = json_file(ROOT / 'inputs' / 'v20_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v20_individual_followup_ids.json')
    geography_ids = json_file(ROOT / 'inputs' / 'v20_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v20_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 141
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V20_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(geography_ids) == len(set(geography_ids)) == 1
    assert set(geography_ids) == GEOGRAPHY_PILOT_SCOPE
    assert not (set(geography_ids) & set(target_ids))
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 9
    assert set(reviewed_ids) == set(individual_ids) | set(geography_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v20_accepted_birthplaces.json')
    geography_facts = json_file(ROOT / 'inputs' / 'v20_accepted_geography.json')
    assert len(facts) == 4
    assert geography_facts == [], 'Frozen v20 authority-graph pilot has no accepted facts'
    intermediate, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v20', individual_ids)
    v20, _ = apply_geography_only(intermediate, geography_facts, geography_ids)
    assert hashlib.sha256(canonical_bytes(v20)).hexdigest() == EXPECTED_V20_CANONICAL
    assert {row['cohort'] for row in v20} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v20) == {'north': 4172, 'south': 186, 'unknown': 625}
    window = [row for row in v20 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2272, 'south': 181, 'unknown': 191}
    assert len(target_ids_from_rows(v20)) == 137
    return v20


def load_v21():
    baseline = load_v20()
    target_ids = json_file(ROOT / 'inputs' / 'v21_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v21_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v21_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 137
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V21_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 8
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v21_accepted_birthplaces.json')
    assert len(facts) == 4
    v21, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v21', individual_ids)
    assert hashlib.sha256(canonical_bytes(v21)).hexdigest() == EXPECTED_V21_CANONICAL
    assert {row['cohort'] for row in v21} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v21) == {'north': 4175, 'south': 187, 'unknown': 621}
    window = [row for row in v21 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2275, 'south': 182, 'unknown': 187}
    assert len(target_ids_from_rows(v21)) == 133
    return v21


def load_v22():
    baseline = load_v21()
    target_ids = json_file(ROOT / 'inputs' / 'v22_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v22_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v22_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 133
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V22_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 8
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v22_accepted_birthplaces.json')
    assert len(facts) == 2
    v22, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v22', individual_ids)
    assert hashlib.sha256(canonical_bytes(v22)).hexdigest() == EXPECTED_V22_CANONICAL
    assert {row['cohort'] for row in v22} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v22) == {'north': 4176, 'south': 187, 'unknown': 620}
    window = [row for row in v22 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2276, 'south': 182, 'unknown': 186}
    assert len(target_ids_from_rows(v22)) == 131
    return v22


def load_v23():
    baseline = load_v22()
    target_ids = json_file(ROOT / 'inputs' / 'v23_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v23_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v23_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 131
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == V23_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v23_accepted_birthplaces.json')
    assert len(facts) == 1
    v23, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v23', individual_ids)
    assert hashlib.sha256(canonical_bytes(v23)).hexdigest() == EXPECTED_V23_CANONICAL
    assert {row['cohort'] for row in v23} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v23) == {'north': 4176, 'south': 187, 'unknown': 620}
    window = [row for row in v23 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2276, 'south': 182, 'unknown': 186}
    assert len(target_ids_from_rows(v23)) == 130
    return v23


def load_v24():
    baseline = load_v23()
    target_ids = json_file(ROOT / 'inputs' / 'v24_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v24_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v24_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 130
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == V24_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v24_accepted_birthplaces.json')
    assert len(facts) == 5
    v24, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v24', individual_ids)
    assert hashlib.sha256(canonical_bytes(v24)).hexdigest() == EXPECTED_V24_CANONICAL
    assert {row['cohort'] for row in v24} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v24) == {'north': 4177, 'south': 187, 'unknown': 619}
    window = [row for row in v24 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2277, 'south': 182, 'unknown': 185}
    assert len(target_ids_from_rows(v24)) == 125
    return v24


def load_v25():
    baseline = load_v24()
    target_ids = json_file(ROOT / 'inputs' / 'v25_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v25_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v25_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 125
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == V25_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v25_accepted_birthplaces.json')
    assert len(facts) == 2
    v25, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v25', individual_ids)
    assert hashlib.sha256(canonical_bytes(v25)).hexdigest() == EXPECTED_V25_CANONICAL
    assert {row['cohort'] for row in v25} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v25) == {'north': 4177, 'south': 187, 'unknown': 619}
    window = [row for row in v25 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2277, 'south': 182, 'unknown': 185}
    assert len(target_ids_from_rows(v25)) == 123
    return v25


def load_v26():
    baseline = load_v25()
    target_ids = json_file(ROOT / 'inputs' / 'v26_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v26_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v26_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 123
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == V26_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v26_accepted_birthplaces.json')
    assert len(facts) == 5
    v26, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v26', individual_ids)
    assert hashlib.sha256(canonical_bytes(v26)).hexdigest() == EXPECTED_V26_CANONICAL
    assert {row['cohort'] for row in v26} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v26) == {'north': 4179, 'south': 187, 'unknown': 617}
    window = [row for row in v26 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2279, 'south': 182, 'unknown': 183}
    assert len(target_ids_from_rows(v26)) == 118
    return v26


def load_v27():
    baseline = load_v26()
    target_ids = json_file(ROOT / 'inputs' / 'v27_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v27_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v27_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 118
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == V27_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v27_accepted_birthplaces.json')
    assert len(facts) == 4
    v27, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v27', individual_ids)
    assert hashlib.sha256(canonical_bytes(v27)).hexdigest() == EXPECTED_V27_CANONICAL
    assert {row['cohort'] for row in v27} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v27) == {'north': 4181, 'south': 187, 'unknown': 615}
    window = [row for row in v27 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2281, 'south': 182, 'unknown': 181}
    assert len(target_ids_from_rows(v27)) == 114
    return v27


def load_v28():
    baseline = load_v27()
    target_ids = json_file(ROOT / 'inputs' / 'v28_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v28_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v28_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 114
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == V28_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v28_accepted_birthplaces.json')
    assert len(facts) == 2
    v28, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v28', individual_ids)
    assert hashlib.sha256(canonical_bytes(v28)).hexdigest() == EXPECTED_V28_CANONICAL
    assert {row['cohort'] for row in v28} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v28) == {'north': 4183, 'south': 187, 'unknown': 613}
    window = [row for row in v28 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2283, 'south': 182, 'unknown': 179}
    assert len(target_ids_from_rows(v28)) == 112
    return v28


def load_v29():
    baseline = load_v28()
    target_ids = json_file(ROOT / 'inputs' / 'v29_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v29_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v29_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 112
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 18
    assert set(individual_ids) == V29_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 18
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v29_accepted_birthplaces.json')
    assert len(facts) == 9
    v29, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v29', individual_ids)
    assert hashlib.sha256(canonical_bytes(v29)).hexdigest() == EXPECTED_V29_CANONICAL
    assert {row['cohort'] for row in v29} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v29) == {'north': 4190, 'south': 187, 'unknown': 606}
    window = [row for row in v29 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2290, 'south': 182, 'unknown': 172}
    assert len(target_ids_from_rows(v29)) == 103
    return v29


def geography_target_ids_from_rows(rows):
    """Fixed native-window records with stored birthplace but unresolved geography."""
    return [row['record_id'] for row in rows
            if row['hemisphere'] == 'unknown' and row.get('raw_birthplace') and in_window(row)]


def apply_v30_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V30_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V30_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v30_explicit_person_birth_context',
                         geography_decision='v30_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V30_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V30_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def load_v30():
    baseline = load_v29()
    target_ids = json_file(ROOT / 'inputs' / 'v30_geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v30_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v30_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 69
    assert target_ids == geography_target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 12
    assert set(followup_ids) == V30_GEOGRAPHY_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v30_accepted_geography.json')
    assert len(facts) == 1
    v30, _ = apply_v30_geography(baseline, facts, target_ids, followup_ids)
    assert hashlib.sha256(canonical_bytes(v30)).hexdigest() == EXPECTED_V30_CANONICAL
    assert {row['cohort'] for row in v30} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v30) == {'north': 4191, 'south': 187, 'unknown': 605}
    window = [row for row in v30 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2291, 'south': 182, 'unknown': 171}
    assert len(geography_target_ids_from_rows(v30)) == 68
    assert len(target_ids_from_rows(v30)) == 103
    assert sum(not row.get('raw_birthplace') for row in v30) == 525
    return v30


def apply_v31_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V31_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V31_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v31_explicit_person_birth_context',
                         geography_decision='v31_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V31_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V31_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def load_v31():
    baseline = load_v30()
    target_ids = json_file(ROOT / 'inputs' / 'v31_geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v31_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v31_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 68
    assert target_ids == geography_target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 12
    assert set(followup_ids) == V31_GEOGRAPHY_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v31_accepted_geography.json')
    assert len(facts) == 2
    v31, _ = apply_v31_geography(baseline, facts, target_ids, followup_ids)
    assert hashlib.sha256(canonical_bytes(v31)).hexdigest() == EXPECTED_V31_CANONICAL
    assert {row['cohort'] for row in v31} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v31) == {'north': 4193, 'south': 187, 'unknown': 603}
    window = [row for row in v31 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2293, 'south': 182, 'unknown': 169}
    assert len(geography_target_ids_from_rows(v31)) == 66
    assert len(target_ids_from_rows(v31)) == 103
    assert sum(not row.get('raw_birthplace') for row in v31) == 525
    return v31


def apply_v32_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V32_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V32_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v32_explicit_person_birth_context',
                         geography_decision='v32_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V32_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V32_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def load_v32():
    baseline = load_v31()
    target_ids = json_file(ROOT / 'inputs' / 'v32_geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v32_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v32_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 66
    assert target_ids == geography_target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 12
    assert set(followup_ids) == V32_GEOGRAPHY_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v32_accepted_geography.json')
    assert len(facts) == 1
    v32, _ = apply_v32_geography(baseline, facts, target_ids, followup_ids)
    assert hashlib.sha256(canonical_bytes(v32)).hexdigest() == EXPECTED_V32_CANONICAL
    assert {row['cohort'] for row in v32} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v32) == {'north': 4194, 'south': 187, 'unknown': 602}
    window = [row for row in v32 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2294, 'south': 182, 'unknown': 168}
    assert len(geography_target_ids_from_rows(v32)) == 65
    assert len(target_ids_from_rows(v32)) == 103
    assert sum(not row.get('raw_birthplace') for row in v32) == 525
    return v32


def apply_v33_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V33_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V33_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v33_explicit_person_birth_context',
                         geography_decision='v33_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V33_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V33_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def load_v33():
    baseline = load_v32()
    target_ids = json_file(ROOT / 'inputs' / 'v33_geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v33_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v33_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 65
    assert target_ids == geography_target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 12
    assert set(followup_ids) == V33_GEOGRAPHY_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v33_accepted_geography.json')
    assert len(facts) == 1
    v33, _ = apply_v33_geography(baseline, facts, target_ids, followup_ids)
    assert hashlib.sha256(canonical_bytes(v33)).hexdigest() == EXPECTED_V33_CANONICAL
    assert {row['cohort'] for row in v33} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v33) == {'north': 4195, 'south': 187, 'unknown': 601}
    window = [row for row in v33 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2295, 'south': 182, 'unknown': 167}
    assert len(geography_target_ids_from_rows(v33)) == 64
    assert len(target_ids_from_rows(v33)) == 103
    assert sum(not row.get('raw_birthplace') for row in v33) == 525
    return v33


def apply_v34_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V34_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V34_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v34_explicit_person_birth_context',
                         geography_decision='v34_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V34_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V34_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def load_v34():
    baseline = load_v33()
    target_ids = json_file(ROOT / 'inputs' / 'v34_geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v34_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v34_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 64
    assert target_ids == geography_target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 12
    assert set(followup_ids) == V34_GEOGRAPHY_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v34_accepted_geography.json')
    assert len(facts) == 2
    v34, _ = apply_v34_geography(baseline, facts, target_ids, followup_ids)
    assert hashlib.sha256(canonical_bytes(v34)).hexdigest() == EXPECTED_V34_CANONICAL
    assert {row['cohort'] for row in v34} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v34) == {'north': 4197, 'south': 187, 'unknown': 599}
    window = [row for row in v34 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2297, 'south': 182, 'unknown': 165}
    assert len(geography_target_ids_from_rows(v34)) == 62
    assert len(target_ids_from_rows(v34)) == 103
    assert sum(not row.get('raw_birthplace') for row in v34) == 525
    return v34


def apply_v35_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V35_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V35_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v35_explicit_person_birth_context',
                         geography_decision='v35_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V35_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V35_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def load_v35():
    baseline = load_v34()
    target_ids = json_file(ROOT / 'inputs' / 'v35_geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v35_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v35_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 62
    assert target_ids == geography_target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 6
    assert set(followup_ids) == V35_GEOGRAPHY_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 6
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v35_accepted_geography.json')
    assert len(facts) == 0
    v35, _ = apply_v35_geography(baseline, facts, target_ids, followup_ids)
    assert hashlib.sha256(canonical_bytes(v35)).hexdigest() == EXPECTED_V35_CANONICAL
    assert {row['cohort'] for row in v35} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v35) == {'north': 4197, 'south': 187, 'unknown': 599}
    window = [row for row in v35 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2297, 'south': 182, 'unknown': 165}
    assert len(geography_target_ids_from_rows(v35)) == 62
    assert len(target_ids_from_rows(v35)) == 103
    assert sum(not row.get('raw_birthplace') for row in v35) == 525
    return v35


def apply_v36_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V36_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V36_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] == 'S3', 'Prospective v36 method is S3 geography support only'
            assert fact.get('method_id') == V36_METHOD_ID, 'Missing or wrong prospective method'
            assert fact.get('proof_mode') in V36_PROOF_MODES, 'Unsupported prospective proof mode'
            assert fact.get('source_birthdate') == before['dob'], 'Actual source exact DOB must match native'
            assert isinstance(fact.get('observed_source_full_name'), str) and fact['observed_source_full_name'].strip()
            proof_chain = fact.get('proof_chain')
            assert isinstance(proof_chain, list) and proof_chain, 'Actual source/edge chain is required'
            chain_fields = ('source_url', 'source_node_label', 'edge_property', 'tool_ref', 'locator', 'acquisition_role', 'target_label')
            for position, observation in enumerate(proof_chain):
                assert isinstance(observation, dict)
                assert all(isinstance(observation.get(key), str) and observation[key].strip() for key in chain_fields), 'Incomplete source/edge observation'
                assert observation.get('target_kind') in {'entity', 'literal'}, 'Target kind must be explicit'
                if observation['target_kind'] == 'entity':
                    assert isinstance(observation.get('target_uri'), str) and observation['target_uri'].strip(), 'Entity target needs actual URI'
                else:
                    assert observation.get('target_uri') is None, 'Literal region must not receive an invented URI'
                if position < len(proof_chain) - 1:
                    assert observation['target_kind'] == 'entity', 'Nonterminal chain target must be an actual entity'
            if fact['proof_mode'] != V36_PROOF_MODES[0]:
                assert len(proof_chain) >= 2, 'Linked place proof needs person and target observations'
                assert proof_chain[0]['target_kind'] == 'entity', 'Person born-place edge needs an actual entity URI'
            if fact['proof_mode'] == V36_PROOF_MODES[2]:
                assert all(observation['target_kind'] == 'entity' for observation in proof_chain), 'P19/P131 proof requires actual entity targets throughout'
                assert {'P19', 'P131'} <= {observation['edge_property'] for observation in proof_chain}, 'P19/P131 proof needs both acquired edges'
            # Documentary source QA verifies geographic entity kinds and adjacent
            # actual target/source identity, including any observed redirects.
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v36_explicit_person_birth_context',
                         geography_decision='v36_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V36_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V36_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


EXPECTED_V36_CANONICAL = '56d5117eed499c0116eb088362874c8273bcee79ef7bb74da3e807f27ce0a020'
V36_SOURCE_COMMIT = 'ec2f83b0430f1aa701bca0a86a8158d60d1786b4'
V37_METHOD_ID = V36_METHOD_ID
V37_PROOF_MODES = V36_PROOF_MODES
V37_GEOGRAPHY_FOLLOWUP_SCOPE = {'RS_PAST_NA4113', 'RS_PAST_NA1580', 'RS_PAST_NA6231', 'RS_PAST_NA4918', 'RS_PAST_NA2099', 'RS_PAST_NA6938'}
V37_GEOGRAPHY_FIELD = 'geography_followup_v37'
V37_METHOD_PREREGISTRATION_SHA256 = 'b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147'
V37_APPLICATION_SCOPE_SHA256 = 'ae080b06f8abad9ed7575783486795c977e44ce5e5024bfa2096e16816a44d94'

def load_v36():
    baseline = load_v35()
    target_ids = json_file(ROOT / 'inputs' / 'v36_geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v36_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v36_reviewed_record_ids.json')
    holds = json_file(ROOT / 'inputs' / 'v36_followup_holds.json')
    assert len(target_ids) == len(set(target_ids)) == 62
    assert target_ids == geography_target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 6
    assert set(followup_ids) == V36_GEOGRAPHY_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 6
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v36_accepted_geography.json')
    assert len(facts) == 1 and facts[0]['record_id'] == 'RS_PAST_NA3578'
    assert len(holds) == 5 and len({h['record_id'] for h in holds}) == 5
    assert {facts[0]['record_id']} | {h['record_id'] for h in holds} == set(reviewed_ids)
    assert not ({facts[0]['record_id']} & {h['record_id'] for h in holds})
    v36, _ = apply_v36_geography(baseline, facts, target_ids, followup_ids)
    assert hashlib.sha256(canonical_bytes(v36)).hexdigest() == EXPECTED_V36_CANONICAL
    assert {row['cohort'] for row in v36} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v36) == {'north': 4198, 'south': 187, 'unknown': 598}
    window = [row for row in v36 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2298, 'south': 182, 'unknown': 164}
    assert len(geography_target_ids_from_rows(v36)) == 61
    assert len(target_ids_from_rows(v36)) == 103
    assert sum(not row.get('raw_birthplace') for row in v36) == 525
    return v36


def apply_v37_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert hashlib.sha256((ROOT / 'audit' / 'method_preregistration.json').read_bytes()).hexdigest() == V37_METHOD_PREREGISTRATION_SHA256, 'Historical V36 preregistration changed'
    scope_path = ROOT / 'audit' / 'method_application_scope.json'
    assert hashlib.sha256(scope_path.read_bytes()).hexdigest() == V37_APPLICATION_SCOPE_SHA256, 'Current application scope changed'
    scope = json_file(scope_path)
    assert scope['method_id'] == V37_METHOD_ID and scope['rules_unchanged'] is True
    assert scope['method_amendment_created'] is False and scope['scope_application_extension'] is True
    assert scope['method_reused_from_version'] == 36 and scope['no_new_admission_method_exception'] is True
    assert set(scope['fixed_record_ids']) == V37_GEOGRAPHY_FOLLOWUP_SCOPE
    assert scope['baseline_commit'] == V36_SOURCE_COMMIT
    assert scope['baseline_canonical_sha256'] == EXPECTED_V36_CANONICAL
    assert scope['method_preregistration_sha256'] == V37_METHOD_PREREGISTRATION_SHA256
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V37_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V37_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] == 'S3', 'Prospective v37 method is S3 geography support only'
            assert fact.get('method_application_scope_sha256') == V37_APPLICATION_SCOPE_SHA256, 'Fact is not bound to current application scope'
            assert fact.get('method_preregistration_sha256') == V37_METHOD_PREREGISTRATION_SHA256, 'Fact is not bound to unchanged method preregistration'
            assert fact.get('method_id') == V37_METHOD_ID, 'Missing or wrong prospective method'
            assert fact.get('proof_mode') in V37_PROOF_MODES, 'Unsupported prospective proof mode'
            assert fact.get('source_birthdate') == before['dob'], 'Actual source exact DOB must match native'
            assert isinstance(fact.get('observed_source_full_name'), str) and fact['observed_source_full_name'].strip()
            proof_chain = fact.get('proof_chain')
            assert isinstance(proof_chain, list) and proof_chain, 'Actual source/edge chain is required'
            chain_fields = ('source_url', 'source_node_label', 'edge_property', 'tool_ref', 'locator', 'acquisition_role', 'target_label')
            for position, observation in enumerate(proof_chain):
                assert isinstance(observation, dict)
                assert all(isinstance(observation.get(key), str) and observation[key].strip() for key in chain_fields), 'Incomplete source/edge observation'
                assert observation.get('target_kind') in {'entity', 'literal'}, 'Target kind must be explicit'
                if observation['target_kind'] == 'entity':
                    assert isinstance(observation.get('target_uri'), str) and observation['target_uri'].strip(), 'Entity target needs actual URI'
                else:
                    assert observation.get('target_uri') is None, 'Literal region must not receive an invented URI'
                if position < len(proof_chain) - 1:
                    assert observation['target_kind'] == 'entity', 'Nonterminal chain target must be an actual entity'
            if fact['proof_mode'] != V37_PROOF_MODES[0]:
                assert len(proof_chain) >= 2, 'Linked place proof needs person and target observations'
                assert proof_chain[0]['target_kind'] == 'entity', 'Person born-place edge needs an actual entity URI'
            if fact['proof_mode'] == V37_PROOF_MODES[2]:
                assert all(observation['target_kind'] == 'entity' for observation in proof_chain), 'P19/P131 proof requires actual entity targets throughout'
                assert {'P19', 'P131'} <= {observation['edge_property'] for observation in proof_chain}, 'P19/P131 proof needs both acquired edges'
            # Documentary source QA verifies geographic entity kinds and adjacent
            # actual target/source identity, including any observed redirects.
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v37_explicit_person_birth_context',
                         geography_decision='v37_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V37_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V37_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


EXPECTED_V37_CANONICAL = 'c7fbc21d596077694148aee316baa663697fb3fd7159cd7de79c7a194b2affbe'
V37_SOURCE_COMMIT = '7e00f06eec1f6030f974d241a826be828ce7caee'
V38_METHOD_ID = V37_METHOD_ID
V38_PROOF_MODES = V37_PROOF_MODES
V38_GEOGRAPHY_FOLLOWUP_SCOPE = {'RS_PAST_NA1611', 'RS_PAST_NA4636', 'RS_PAST_NA4568', 'RS_PAST_NA4571', 'RS_PAST_NA6313', 'RS_PAST_NA4774'}
V38_GEOGRAPHY_FIELD = 'geography_followup_v38'
V38_METHOD_PREREGISTRATION_SHA256 = 'b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147'
V38_APPLICATION_SCOPE_SHA256 = 'bd7540715a6b4649ffe79371e38ee2b650bd0176013fbb5418efa02b8995fad0'

def load_v37():
    baseline = load_v36()
    target_ids = json_file(ROOT / 'inputs' / 'v37_geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v37_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v37_reviewed_record_ids.json')
    holds = json_file(ROOT / 'inputs' / 'v37_followup_holds.json')
    assert len(target_ids) == len(set(target_ids)) == 61
    assert target_ids == geography_target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 6
    assert set(followup_ids) == V37_GEOGRAPHY_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 6
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v37_accepted_geography.json')
    assert len(facts) == 1 and facts[0]['record_id'] == 'RS_PAST_NA1580'
    assert len(holds) == 5 and len({h['record_id'] for h in holds}) == 5
    assert {facts[0]['record_id']} | {h['record_id'] for h in holds} == set(reviewed_ids)
    assert not ({facts[0]['record_id']} & {h['record_id'] for h in holds})
    v37, _ = apply_v37_geography(baseline, facts, target_ids, followup_ids)
    assert hashlib.sha256(canonical_bytes(v37)).hexdigest() == EXPECTED_V37_CANONICAL
    assert {row['cohort'] for row in v37} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v37) == {'north': 4199, 'south': 187, 'unknown': 597}
    window = [row for row in v37 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2299, 'south': 182, 'unknown': 163}
    assert len(geography_target_ids_from_rows(v37)) == 60
    assert len(target_ids_from_rows(v37)) == 103
    assert sum(not row.get('raw_birthplace') for row in v37) == 525
    return v37

def apply_v38_geography(rows, facts, target_ids, followup_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert hashlib.sha256((ROOT / 'audit' / 'method_preregistration.json').read_bytes()).hexdigest() == V38_METHOD_PREREGISTRATION_SHA256, 'Historical V36 preregistration changed'
    scope_path = ROOT / 'audit' / 'method_application_scope_v38.json'
    assert hashlib.sha256(scope_path.read_bytes()).hexdigest() == V38_APPLICATION_SCOPE_SHA256, 'Current application scope changed'
    scope = json_file(scope_path)
    assert scope['method_id'] == V38_METHOD_ID and scope['rules_unchanged'] is True
    assert scope['method_amendment_created'] is False and scope['scope_application_extension'] is True
    assert scope['method_reused_from_version'] == 36 and scope['no_new_admission_method_exception'] is True
    assert set(scope['fixed_record_ids']) == V38_GEOGRAPHY_FOLLOWUP_SCOPE
    assert scope['baseline_commit'] == V37_SOURCE_COMMIT
    assert scope['baseline_canonical_sha256'] == EXPECTED_V37_CANONICAL
    assert scope['method_preregistration_sha256'] == V38_METHOD_PREREGISTRATION_SHA256
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(followup_ids) <= V38_GEOGRAPHY_FOLLOWUP_SCOPE
    assert set(followup_ids) <= set(target_ids)
    assert set(by_id) <= set(target_ids)
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V38_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] == 'S3', 'Prospective v38 method is S3 geography support only'
            assert fact.get('method_application_scope_sha256') == V38_APPLICATION_SCOPE_SHA256, 'Fact is not bound to current application scope'
            assert fact.get('method_preregistration_sha256') == V38_METHOD_PREREGISTRATION_SHA256, 'Fact is not bound to unchanged method preregistration'
            assert fact.get('method_id') == V38_METHOD_ID, 'Missing or wrong prospective method'
            assert fact.get('proof_mode') in V38_PROOF_MODES, 'Unsupported prospective proof mode'
            assert fact.get('source_birthdate') == before['dob'], 'Actual source exact DOB must match native'
            assert isinstance(fact.get('observed_source_full_name'), str) and fact['observed_source_full_name'].strip()
            proof_chain = fact.get('proof_chain')
            assert isinstance(proof_chain, list) and proof_chain, 'Actual source/edge chain is required'
            chain_fields = ('source_url', 'source_node_label', 'edge_property', 'tool_ref', 'locator', 'acquisition_role', 'target_label')
            for position, observation in enumerate(proof_chain):
                assert isinstance(observation, dict)
                assert all(isinstance(observation.get(key), str) and observation[key].strip() for key in chain_fields), 'Incomplete source/edge observation'
                assert observation.get('target_kind') in {'entity', 'literal'}, 'Target kind must be explicit'
                if observation['target_kind'] == 'entity':
                    assert isinstance(observation.get('target_uri'), str) and observation['target_uri'].strip(), 'Entity target needs actual URI'
                else:
                    assert observation.get('target_uri') is None, 'Literal region must not receive an invented URI'
                if position < len(proof_chain) - 1:
                    assert observation['target_kind'] == 'entity', 'Nonterminal chain target must be an actual entity'
            if fact['proof_mode'] != V38_PROOF_MODES[0]:
                assert len(proof_chain) >= 2, 'Linked place proof needs person and target observations'
                assert proof_chain[0]['target_kind'] == 'entity', 'Person born-place edge needs an actual entity URI'
            if fact['proof_mode'] == V38_PROOF_MODES[2]:
                assert all(observation['target_kind'] == 'entity' for observation in proof_chain), 'P19/P131 proof requires actual entity targets throughout'
                assert {'P19', 'P131'} <= {observation['edge_property'] for observation in proof_chain}, 'P19/P131 proof needs both acquired edges'
            # Documentary source QA verifies geographic entity kinds and adjacent
            # actual target/source identity, including any observed redirects.
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            if not source_quote.strip():
                assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured birth evidence'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v38_explicit_person_birth_context',
                         geography_decision='v38_geography_only_explicit_person_birth_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V38_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V38_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def write_csv(path, rows):
    fields = ['record_id', 'name', 'dob', 'raw_birthplace', 'hemisphere', 'birthplace_source_grade',
              'qualified_context', 'context_source_grade', 'context_source_url', 'context_version',
              'qualified_geography_context', 'geographic_support_grade', 'geography_source_url',
              'geographic_support_grade_role', 'geo_context_version']
    for v in ('v15', 'v16', 'v17', 'v18', 'v19', 'v20'):
        fields.extend([v + '_birthplace', v + '_birthplace_source_grade', v + '_birthplace_source_url',
                       v + '_source_birthdate_precision', v + '_birthplace_grade_role', v + '_context_version'])
    fields.extend(['v20_geographic_context', 'v20_geographic_support_grade',
                   'v20_geography_source_url', 'v20_geographic_support_grade_role',
                   'v20_geo_context_version'])
    fields.extend(['v21_birthplace', 'v21_birthplace_source_grade', 'v21_birthplace_source_url',
                   'v21_source_birthdate_precision', 'v21_birthplace_grade_role', 'v21_context_version'])
    fields.extend(['v22_birthplace', 'v22_birthplace_source_grade', 'v22_birthplace_source_url',
                   'v22_source_birthdate_precision', 'v22_birthplace_grade_role', 'v22_context_version'])
    fields.extend(['v23_birthplace', 'v23_birthplace_source_grade', 'v23_birthplace_source_url',
                   'v23_source_birthdate_precision', 'v23_birthplace_grade_role', 'v23_context_version'])
    fields.extend(['v24_birthplace', 'v24_birthplace_source_grade', 'v24_birthplace_source_url',
                   'v24_source_birthdate_precision', 'v24_birthplace_grade_role', 'v24_context_version'])
    fields.extend(['v25_birthplace', 'v25_birthplace_source_grade', 'v25_birthplace_source_url',
                   'v25_source_birthdate_precision', 'v25_birthplace_grade_role', 'v25_context_version'])
    fields.extend(['v26_birthplace', 'v26_birthplace_source_grade', 'v26_birthplace_source_url',
                   'v26_source_birthdate_precision', 'v26_birthplace_grade_role', 'v26_context_version'])
    fields.extend(['v27_birthplace', 'v27_birthplace_source_grade', 'v27_birthplace_source_url',
                   'v27_source_birthdate_precision', 'v27_birthplace_grade_role', 'v27_context_version'])
    fields.extend(['v28_birthplace', 'v28_birthplace_source_grade', 'v28_birthplace_source_url',
                   'v28_source_birthdate_precision', 'v28_birthplace_grade_role', 'v28_context_version'])
    fields.extend(['v29_birthplace', 'v29_birthplace_source_grade', 'v29_birthplace_source_url',
                   'v29_source_birthdate_precision', 'v29_birthplace_grade_role', 'v29_context_version'])
    fields.extend(['v30_geographic_hemisphere', 'v30_geographic_support_grade', 'v30_geography_source_url',
                   'v30_source_birthdate_precision', 'v30_geographic_support_grade_role', 'v30_geo_context_version'])
    fields.extend(['v31_geographic_hemisphere', 'v31_geographic_support_grade', 'v31_geography_source_url',
                   'v31_source_birthdate_precision', 'v31_geographic_support_grade_role', 'v31_geo_context_version'])
    fields.extend(['v32_geographic_hemisphere', 'v32_geographic_support_grade', 'v32_geography_source_url',
                   'v32_source_birthdate_precision', 'v32_geographic_support_grade_role', 'v32_geo_context_version'])
    fields.extend(['v33_geographic_hemisphere', 'v33_geographic_support_grade', 'v33_geography_source_url',
                   'v33_source_birthdate_precision', 'v33_geographic_support_grade_role', 'v33_geo_context_version'])
    fields.extend(['v34_geographic_hemisphere', 'v34_geographic_support_grade', 'v34_geography_source_url',
                   'v34_source_birthdate_precision', 'v34_geographic_support_grade_role', 'v34_geo_context_version'])
    fields.extend(['v35_geographic_hemisphere', 'v35_geographic_support_grade', 'v35_geography_source_url',
                   'v35_source_birthdate_precision', 'v35_geographic_support_grade_role', 'v35_geo_context_version'])
    fields.extend(['v36_geographic_hemisphere', 'v36_geographic_support_grade', 'v36_geography_source_url',
                   'v36_source_birthdate_precision', 'v36_geographic_support_grade_role', 'v36_geo_context_version'])
    fields.extend(['v37_geographic_hemisphere', 'v37_geographic_support_grade', 'v37_geography_source_url',
                   'v37_source_birthdate_precision', 'v37_geographic_support_grade_role', 'v37_geo_context_version'])
    fields.extend(['v38_geographic_hemisphere', 'v38_geographic_support_grade', 'v38_geography_source_url',
                   'v38_source_birthdate_precision', 'v38_geographic_support_grade_role', 'v38_geo_context_version'])
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        version = next((v for v in ('v13', 'v12', 'v11') if 'birthplace_followup_' + v in row), '')
        context = row.get('birthplace_followup_' + version, {})
        geography = row.get(GEOGRAPHY_FIELD, {})
        values = {key: row.get(key, '') for key in fields}
        values.update(qualified_context=context.get('qualified_context', ''),
                      context_source_grade=context.get('source_grade', ''),
                      context_source_url=context.get('source_url', ''), context_version=version,
                      qualified_geography_context=geography.get('qualified_context', ''),
                      geographic_support_grade=geography.get('source_grade', ''),
                      geography_source_url=geography.get('source_url', ''),
                      geographic_support_grade_role=geography.get('source_grade_role', ''),
                      geo_context_version='v14' if geography else '')
        for v in ('v15', 'v16', 'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29'):
            birthplace = row.get('birthplace_followup_' + v, {})
            values.update({v + '_birthplace': birthplace.get('raw_birthplace', ''),
                           v + '_birthplace_source_grade': birthplace.get('source_grade', ''),
                           v + '_birthplace_source_url': birthplace.get('source_url', ''),
                           v + '_source_birthdate_precision': birthplace.get('source_birthdate_precision', ''),
                           v + '_birthplace_grade_role': birthplace.get('source_grade_role', ''),
                           v + '_context_version': v if birthplace else ''})
        new_geography = row.get(V20_GEOGRAPHY_FIELD, {})
        values.update(v20_geographic_context=new_geography.get('qualified_context', new_geography.get('geographic_basis', '')),
                      v20_geographic_support_grade=new_geography.get('source_grade', ''),
                      v20_geography_source_url=new_geography.get('source_url', ''),
                      v20_geographic_support_grade_role=new_geography.get('source_grade_role', ''),
                      v20_geo_context_version='v20' if new_geography else '')
        v30_geography = row.get(V30_GEOGRAPHY_FIELD, {})
        values.update(v30_geographic_hemisphere=v30_geography.get('reviewed_hemisphere', ''),
                      v30_geographic_support_grade=v30_geography.get('source_grade', ''),
                      v30_geography_source_url=v30_geography.get('source_url', ''),
                      v30_source_birthdate_precision=v30_geography.get('source_birthdate_precision', ''),
                      v30_geographic_support_grade_role=v30_geography.get('source_grade_role', ''),
                      v30_geo_context_version='v30' if v30_geography else '')
        v31_geography = row.get(V31_GEOGRAPHY_FIELD, {})
        values.update(v31_geographic_hemisphere=v31_geography.get('reviewed_hemisphere', ''),
                      v31_geographic_support_grade=v31_geography.get('source_grade', ''),
                      v31_geography_source_url=v31_geography.get('source_url', ''),
                      v31_source_birthdate_precision=v31_geography.get('source_birthdate_precision', ''),
                      v31_geographic_support_grade_role=v31_geography.get('source_grade_role', ''),
                      v31_geo_context_version='v31' if v31_geography else '')
        v32_geography = row.get(V32_GEOGRAPHY_FIELD, {})
        values.update(v32_geographic_hemisphere=v32_geography.get('reviewed_hemisphere', ''),
                      v32_geographic_support_grade=v32_geography.get('source_grade', ''),
                      v32_geography_source_url=v32_geography.get('source_url', ''),
                      v32_source_birthdate_precision=v32_geography.get('source_birthdate_precision', ''),
                      v32_geographic_support_grade_role=v32_geography.get('source_grade_role', ''),
                      v32_geo_context_version='v32' if v32_geography else '')
        v33_geography = row.get(V33_GEOGRAPHY_FIELD, {})
        values.update(v33_geographic_hemisphere=v33_geography.get('reviewed_hemisphere', ''),
                      v33_geographic_support_grade=v33_geography.get('source_grade', ''),
                      v33_geography_source_url=v33_geography.get('source_url', ''),
                      v33_source_birthdate_precision=v33_geography.get('source_birthdate_precision', ''),
                      v33_geographic_support_grade_role=v33_geography.get('source_grade_role', ''),
                      v33_geo_context_version='v33' if v33_geography else '')
        v34_geography = row.get(V34_GEOGRAPHY_FIELD, {})
        values.update(v34_geographic_hemisphere=v34_geography.get('reviewed_hemisphere', ''),
                      v34_geographic_support_grade=v34_geography.get('source_grade', ''),
                      v34_geography_source_url=v34_geography.get('source_url', ''),
                      v34_source_birthdate_precision=v34_geography.get('source_birthdate_precision', ''),
                      v34_geographic_support_grade_role=v34_geography.get('source_grade_role', ''),
                      v34_geo_context_version='v34' if v34_geography else '')
        v35_geography = row.get(V35_GEOGRAPHY_FIELD, {})
        values.update(v35_geographic_hemisphere=v35_geography.get('reviewed_hemisphere', ''),
                      v35_geographic_support_grade=v35_geography.get('source_grade', ''),
                      v35_geography_source_url=v35_geography.get('source_url', ''),
                      v35_source_birthdate_precision=v35_geography.get('source_birthdate_precision', ''),
                      v35_geographic_support_grade_role=v35_geography.get('source_grade_role', ''),
                      v35_geo_context_version='v35' if v35_geography else '')
        v36_geography = row.get(V36_GEOGRAPHY_FIELD, {})
        values.update(v36_geographic_hemisphere=v36_geography.get('reviewed_hemisphere', ''),
                      v36_geographic_support_grade=v36_geography.get('source_grade', ''),
                      v36_geography_source_url=v36_geography.get('source_url', ''),
                      v36_source_birthdate_precision=v36_geography.get('source_birthdate_precision', ''),
                      v36_geographic_support_grade_role=v36_geography.get('source_grade_role', ''),
                      v36_geo_context_version='v36' if v36_geography else '')
        v37_geography = row.get(V37_GEOGRAPHY_FIELD, {})
        values.update(v37_geographic_hemisphere=v37_geography.get('reviewed_hemisphere', ''),
                      v37_geographic_support_grade=v37_geography.get('source_grade', ''),
                      v37_geography_source_url=v37_geography.get('source_url', ''),
                      v37_source_birthdate_precision=v37_geography.get('source_birthdate_precision', ''),
                      v37_geographic_support_grade_role=v37_geography.get('source_grade_role', ''),
                      v37_geo_context_version='v37' if v37_geography else '')
        v38_geography = row.get(V38_GEOGRAPHY_FIELD, {})
        values.update(v38_geographic_hemisphere=v38_geography.get('reviewed_hemisphere', ''),
                      v38_geographic_support_grade=v38_geography.get('source_grade', ''),
                      v38_geography_source_url=v38_geography.get('source_url', ''),
                      v38_source_birthdate_precision=v38_geography.get('source_birthdate_precision', ''),
                      v38_geographic_support_grade_role=v38_geography.get('source_grade_role', ''),
                      v38_geo_context_version='v38' if v38_geography else '')
        writer.writerow(values)
    path.write_bytes(buf.getvalue().encode('utf-8'))


def blank_diagnostics(rows):
    window = [row for row in rows if in_window(row)]
    unknown = [row for row in rows if row['hemisphere'] == 'unknown']
    unknown_window = [row for row in window if row['hemisphere'] == 'unknown']
    return {'all_blank_raw_birthplace': sum(not row.get('raw_birthplace') for row in rows),
            'window_blank_raw_birthplace': sum(not row.get('raw_birthplace') for row in window),
            'all_unknown': len(unknown),
            'all_unknown_with_blank_raw_birthplace': sum(not row.get('raw_birthplace') for row in unknown),
            'all_unknown_with_nonblank_raw_birthplace': sum(bool(row.get('raw_birthplace')) for row in unknown),
            'window_unknown': len(unknown_window),
            'window_unknown_with_blank_raw_birthplace': sum(not row.get('raw_birthplace') for row in unknown_window),
            'window_unknown_with_nonblank_raw_birthplace': sum(bool(row.get('raw_birthplace')) for row in unknown_window)}


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def main():
    # Root-adjudicated geographic support must exist before publishing any output.
    facts = json_file(ROOT / 'inputs' / 'accepted_geography.json')
    holds = json_file(ROOT / 'audit' / 'followup_holds.json')
    target_ids = json_file(ROOT / 'inputs' / 'geography_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'reviewed_record_ids.json')
    assert isinstance(facts, list) and isinstance(holds, list)
    assert isinstance(target_ids, list) and len(target_ids) == len(set(target_ids)) == 60
    assert isinstance(followup_ids, list) and len(followup_ids) == len(set(followup_ids)) == 6
    assert set(followup_ids) == V38_GEOGRAPHY_FOLLOWUP_SCOPE
    assert isinstance(reviewed_ids, list) and len(reviewed_ids) == len(set(reviewed_ids)) == 6
    assert set(reviewed_ids) == set(followup_ids)
    assert set(followup_ids) <= set(target_ids)
    baseline = load_v37()
    assert target_ids == geography_target_ids_from_rows(baseline), 'Frozen geography queue differs from reconstructed v37'
    baseline_by_id = {row['record_id']: row for row in baseline}
    accepted_ids = [fact['record_id'] for fact in facts]
    held_ids = [hold['record_id'] for hold in holds]
    assert len(set(accepted_ids)) == len(accepted_ids)
    assert len(set(held_ids)) == len(held_ids)
    assert set(accepted_ids) <= set(followup_ids)
    adopted_ids = set(accepted_ids)
    assert not (adopted_ids & set(held_ids)), 'Reviewed key both adopted and held'
    assert adopted_ids | set(held_ids) == set(reviewed_ids)
    updated, changes = apply_v38_geography(baseline, facts, target_ids, followup_ids)
    assert len(updated) == 4983 and len({row['record_id'] for row in updated}) == 4983
    assert len(changes) == len(facts)
    new_counts = Counter(change['after_hemisphere'] for change in changes)
    expected = Counter(row['hemisphere'] for row in baseline)
    expected['unknown'] -= len(changes)
    expected.update(new_counts)
    overall = Counter(row['hemisphere'] for row in updated)
    assert overall == expected
    window = [row for row in updated if in_window(row)]
    assert len(window) == 2644
    assert all(in_window(baseline_by_id[change['record_id']]) for change in changes)
    expected_window = Counter(row['hemisphere'] for row in baseline if in_window(row))
    expected_window['unknown'] -= len(changes)
    expected_window.update(new_counts)
    window_counts = Counter(row['hemisphere'] for row in window)
    assert window_counts == expected_window
    unchanged = sum(before == after for before, after in zip(baseline, updated))
    assert unchanged == 4983 - len(adopted_ids)
    remaining_blank = blank_diagnostics(updated)
    assert remaining_blank['window_blank_raw_birthplace'] == 103
    assert sum(not row.get('raw_birthplace') for row in updated) == 525
    assert all(after['raw_birthplace'] == before['raw_birthplace'] for before, after in zip(baseline, updated))
    assert all(after['dob'] == before['dob'] for before, after in zip(baseline, updated))
    summary = {'schema': 'royal_society_birthplace_completion_v38',
               'method': 'six fixed followups reusing the unchanged V36 canonical-community person/place geography method; no new first birthplaces',
               'method_amendment_created': False, 'method_reused_from_version': 36,
               'scope_application_extension': True, 'no_new_admission_method_exception': True,
               'method_preregistration_sha256': V38_METHOD_PREREGISTRATION_SHA256,
               'method_application_scope_sha256': V38_APPLICATION_SCOPE_SHA256,
               'current_method_application_scope_audit_path': 'audit/method_application_scope_v38.json',
               'historical_V37_application_scope_path_preserved': 'audit/method_application_scope.json',
               'method_id': V38_METHOD_ID,
               'prospective_source_method_not_retroactive': True,
               'allowed_proof_modes': list(V38_PROOF_MODES),
               'baseline_v37_source_commit': V37_SOURCE_COMMIT,
               'baseline_v37_canonical_jsonl_sha256': EXPECTED_V37_CANONICAL,
               'reconstructed_v11_canonical_jsonl_sha256': EXPECTED_V11_CANONICAL,
               'underlying_v10_gzip_sha256': EXPECTED_V10,
               'records': len(updated), 'counting_unit': 'fixed UK cohort records, not cross-cohort independent persons',
               'frozen_nonblank_unknown_window_geography_pool': len(target_ids),
               'frozen_blank_birthplace_target_pool': 0,
               'blank_window_birthplace_queue_not_targeted': 103,
               'fixed_individual_source_followups': len(followup_ids),
               'fixed_first_birthplace_source_followups': 0,
               'fixed_existing_place_geography_pilots': len(followup_ids),
               'fixed_geography_followups': len(followup_ids),
               'actual_unique_reviewed_records': len(reviewed_ids),
               'reviewed_records_outside_geography_pool': len(set(reviewed_ids) - set(target_ids)),
               'new_bulk_source_screening_performed': False,
               'scope_count_note': 'The 60-record existing-place unresolved-geography pool is an eligibility queue, not 60 biographies read. Six fixed individual followups reuse the unchanged V36 method under a prospectively saved V38 application scope. The 103 blank-place window records are unchanged and were not the target of this batch.',
               'new_offline_crosscohort_screening_performed': False,
               'new_birthplaces': 0, 'new_first_birthplace_records': 0,
               'new_primary_person_birthplace_observations': 0,
               'new_geographic_resolutions': len(changes), 'newly_classified': len(changes),
               'new_geographic_resolutions_from_new_birthplaces': 0,
               'new_geography_only_resolutions': len(changes),
               'new_birthplaces_with_unresolved_geography': 0,
               'new_birthplace_source_grade_counts': {},
               'new_geographic_support_grade_counts': dict(Counter(fact['source_grade'] for fact in facts)),
               'birthplace_source_grade_role': 'no new birthplace facts; all original birthplace grades unchanged',
               'geographic_support_grade_role': 'geographic_support_only; original birthplace and DOB source grades unchanged',
               'new_hemisphere_counts': dict(new_counts), 'overall': dict(overall),
               'native_dob_window': '1835-1985 inclusive', 'native_dob_window_records': len(window),
               'native_dob_window_counts': dict(window_counts),
               'newly_classified_in_native_dob_window': len(changes),
               'unchanged_complete_rows': unchanged, 'followup_held_records': len(holds),
               'followup_holds': dict(Counter(hold.get('hold_type', 'unresolved') for hold in holds)),
               'geography_target_pool_remaining_unresolved': len(target_ids) - len(facts),
               'remaining_blank_current_fields': remaining_blank,
               'native_fields_and_prior_evidence_preserved': True,
               'all_v11_v12_v13_v14_v15_v16_v17_v18_v19_v20_v21_v22_v23_v24_v25_v26_v27_v28_v29_v30_v31_v32_v33_v34_v35_v36_v37_evidence_objects_preserved': True,
               'original_DOB_source_grades_preserved': True,
               'original_birthplace_fields_and_source_grades_preserved': True,
               'new_geography_fields_versioned_with_rollback_snapshots': True,
               'prior_selected_evidence_official_field_status_and_source_hashes_kept_as_history': True,
               'other_cohorts_modified': False, 'country_or_personal_coordinates_assigned': False,
               'DOB_calendar_identity_eligibility_modified': False,
               'cross_cohort_statistical_deduplication': False, 'BaZi_or_outcomes': False, 'final_cohort_freeze': False,
               'gzip_note': 'GzipFile uses empty filename/zero mtime; baseline identity checked with canonical objects.',
               'recovery_note': 'Self-contained UK v10 carrier plus frozen v11-v37 inputs; no comprehensive v8 NAS/DE increment reconstruction.'}
    out = ROOT / 'outputs'
    out.mkdir(exist_ok=True)
    (out / 'birthplace_rows.jsonl.gz').write_bytes(encode_gzip(updated))
    write_json(out / 'summary.json', summary)
    write_json(out / 'changes.json', changes)
    write_csv(out / 'birthplaces.csv', updated)
    write_csv(out / 'remaining_unknown_window.csv', [row for row in window if row['hemisphere'] == 'unknown'])
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
