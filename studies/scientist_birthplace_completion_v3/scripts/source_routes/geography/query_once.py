#!/usr/bin/env python3
"""Execute the approved single exact-locality query once; no retry or redirect."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
BASELINE = BASE / 'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
FACTS = BASE / 'academy_v3_workers/fields/accepted.jsonl'
EXPECTED_BASELINE_SHA = '2b7897d0c4e2655ecb6f10311e1bdf7b06b8eeae3f181e9bebe92cbc7f066ee0'
QUERY = '''PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?item ?matchedLiteral ?matchKind ?itemLabel
  ?instanceOf ?instanceOfLabel ?country ?countryLabel
  ?coordinateStatement ?rank ?latitude ?longitude ?precision ?globe
WHERE {
  {
    SELECT DISTINCT ?item ?matchedLiteral ?matchKind WHERE {
      VALUES ?matchedLiteral { "Châtenay-Malabry"@en "Châtenay-Malabry"@fr }
      { ?item rdfs:label ?matchedLiteral . BIND("label" AS ?matchKind) }
      UNION
      { ?item skos:altLabel ?matchedLiteral . BIND("alias" AS ?matchKind) }
    }
  }
  OPTIONAL { ?item rdfs:label ?itemLabel . FILTER(LANG(?itemLabel) IN ("en", "fr")) }
  OPTIONAL {
    ?item wdt:P31 ?instanceOf .
    OPTIONAL { ?instanceOf rdfs:label ?instanceOfLabel . FILTER(LANG(?instanceOfLabel) IN ("en", "fr")) }
  }
  OPTIONAL {
    ?item wdt:P17 ?country .
    OPTIONAL { ?country rdfs:label ?countryLabel . FILTER(LANG(?countryLabel) IN ("en", "fr")) }
  }
  OPTIONAL {
    ?item p:P625 ?coordinateStatement .
    ?coordinateStatement ps:P625 ?coordinate ; wikibase:rank ?rank ; psv:P625 ?coordinateValue .
    ?coordinateValue wikibase:geoLatitude ?latitude ; wikibase:geoLongitude ?longitude ; wikibase:geoGlobe ?globe .
    OPTIONAL { ?coordinateValue wikibase:geoPrecision ?precision . }
    FILTER(?globe = wd:Q2)
  }
}
ORDER BY ?item ?coordinateStatement ?instanceOf ?country ?matchedLiteral ?matchKind ?itemLabel ?instanceOfLabel ?countryLabel
'''

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write_json(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    raw = ROOT / 'raw'
    raw.mkdir(exist_ok=True)
    ledger = ROOT / 'request_ledger.jsonl'
    if ledger.exists():
        raise SystemExit('Single-query ledger already exists; network query will not run again.')
    assert sha(BASELINE) == EXPECTED_BASELINE_SHA
    facts = [json.loads(s) for s in FACTS.read_text().splitlines() if s]
    assert {f['record_id'] for f in facts} == {'fields-de5a4b4e279eaf4f', 'fields-ef72cb77368d48fe'}
    inputs = [{'path': str(BASELINE), 'sha256': sha(BASELINE)}, {'path': str(FACTS), 'sha256': sha(FACTS)}]
    for f in facts:
        p = Path(f['raw_source_file'])
        assert sha(p) == f['source_sha256']
        inputs.append({'path': str(p), 'sha256': sha(p), 'source_capture_kind': f['source_capture_kind'], 'source_capture_scope': f['source_capture_scope']})
    write_json(ROOT / 'input_locks.json', {'frozen_utc': now(), 'inputs': inputs, 'source_fact_rows': len(facts), 'baseline_sha_verified': True})
    (ROOT / 'chatenay_malabry_exact.sparql').write_text(QUERY)
    endpoint = 'https://query.wikidata.org/sparql'
    url = endpoint + '?' + urllib.parse.urlencode({'query': QUERY, 'format': 'json'})
    request = {'request_id': 'geo_v3_exact_001', 'intent_recorded_utc': now(), 'endpoint': endpoint,
      'method': 'GET', 'query_file': str(ROOT / 'chatenay_malabry_exact.sparql'), 'query_sha256': hashlib.sha256(QUERY.encode()).hexdigest(),
      'exact_labels_aliases': ['Châtenay-Malabry@en', 'Châtenay-Malabry@fr'], 'has_limit': False,
      'maximum_queries': 1, 'maximum_retries': 0, 'follow_redirects': False,
      'person_queries': False, 'birthdate_queries': False, 'status': 'intent_before_network'}
    ledger.write_text(json.dumps(request, ensure_ascii=False, sort_keys=True)+'\n')
    req = urllib.request.Request(url, headers={'Accept': 'application/sparql-results+json', 'User-Agent': 'ScientistBirthplaceGeographyAudit/3.0 (bounded one-shot locality hemisphere review)'})
    outcome = {'request_id': request['request_id'], 'attempt_started_utc': now()}
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=40) as response:
            data = response.read()
            outcome.update(http_status=response.status, response_headers=dict(response.headers), response_url=response.url)
    except urllib.error.HTTPError as e:
        data = e.read()
        outcome.update(http_status=e.code, response_headers=dict(e.headers), error_type='HTTPError', error=str(e))
    except Exception as e:
        data = b''
        outcome.update(error_type=type(e).__name__, error=str(e))
    destination = raw / 'geo_v3_exact_001.response'
    destination.write_bytes(data)
    outcome.update(completed_utc=now(), response_path=str(destination), response_byte_count=len(data), response_sha256=sha(destination), source_capture_kind='direct_http_response_bytes', query_attempts=1, retries=0)
    try:
        parsed = json.loads(data)
        bindings = parsed['results']['bindings']
        write_json(raw / 'geo_v3_exact_001.parsed.json', parsed)
        outcome.update(valid_sparql_results=True, bindings_count=len(bindings), unique_item_count=len({x['item']['value'] for x in bindings}))
    except Exception as e:
        outcome.update(valid_sparql_results=False, parse_error=type(e).__name__ + ': ' + str(e))
    write_json(ROOT / 'query_outcome.json', outcome)
    with ledger.open('a') as f:
        f.write(json.dumps({'event': 'outcome', **outcome}, ensure_ascii=False, sort_keys=True)+'\n')
    print(json.dumps(outcome, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
