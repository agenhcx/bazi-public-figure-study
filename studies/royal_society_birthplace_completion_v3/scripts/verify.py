#!/usr/bin/env python3
"""Independent snapshot, quarantine and offline replay checks for v3."""
from collections import Counter
from pathlib import Path
import csv,gzip,hashlib,json,subprocess,sys,tempfile
s=Path(__file__).resolve().parents[1];repo=s.parents[1]
def read(p):
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
base=read(repo/'studies/royal_society_birthplace_completion_v2/outputs/uk_birthplace_rows.jsonl.gz')
rows=read(s/'outputs/uk_birthplace_rows.jsonl.gz');old={r['record_id']:r for r in base}
assert len(rows)==4983==len({r['record_id'] for r in rows})
geo={'hemisphere','raw_birthplace','country','lat','lon','birthplace_source_grade','birthplace_source_urls','birthplace_source_url','birthplace_evidence_kind','birthplace_claim_excerpt','source_sha256','reason','northern_birthplace_candidate','southern_birthplace_separate','geographic_conflict_pending_review','geography_decision','birthplace_discrepancy_retained','birthplace_evidence_candidates','selected_birthplace_evidence'}
for r in rows:
 b=old[r['record_id']]
 assert all(r.get(k)==v for k,v in b.items() if k not in geo)
 assert r['dob']==b['dob']
 assert r['final_analysis_eligibility_assigned']==b['final_analysis_eligibility_assigned']
 assert r['lookup_qid']==b['lookup_qid']
 if r.get('geography_lookup_qid_quarantined'):
  assert r['active_geography_lookup_qid']==''
  quarantined={c['candidate_id'] for c in r['quarantined_birthplace_evidence_candidates']}
  assert not quarantined & {c['candidate_id'] for c in r['birthplace_evidence_candidates']}
  assert not r['selected_birthplace_evidence'] or r['selected_birthplace_evidence']['candidate_id'] not in quarantined
  badqid=r['lookup_qid']
  for c in r['birthplace_evidence_candidates']:
   assert c.get('qid')!=badqid
   assert not any('/'+badqid+'#P19' in u for u in c.get('source_urls',[]))
 for c in r['birthplace_evidence_candidates']:
  if c['origin'].startswith('new_') and 'birthplace_fact_evidence' in c:
   f=c['birthplace_fact_evidence'];assert f['record_id']==r['record_id']
   assert f.get('dob',f.get('native_dob'))==r['dob']
   assert len(c['evidence_quote'].split())<=25
with (s/'outputs/uk_birthplaces.csv').open() as f:csvrows=list(csv.DictReader(f))
assert len(csvrows)==4983
assert Counter(r['hemisphere'] for r in csvrows)==Counter(r['hemisphere'] for r in rows)
summary=json.loads((s/'outputs/summary.json').read_text())
assert summary['hemisphere_counts']==dict(Counter(r['hemisphere'] for r in rows))
for p,digest in summary['inputs_sha256'].items():assert hashlib.sha256((repo/p).read_bytes()).hexdigest()==digest
# Replay into a fresh directory, requiring byte-identical outputs (including deterministic gzip).
with tempfile.TemporaryDirectory() as d:
 subprocess.run([sys.executable,str(s/'scripts/assemble.py'),'--output',d],check=True,stdout=subprocess.DEVNULL)
 for p in (s/'outputs').iterdir():
  if p.is_file():assert p.read_bytes()==(Path(d)/p.name).read_bytes(),p.name
print(json.dumps({'status':'PASS','baseline_rows':4983,'non_geography_fields_preserved':True,'current99_bad_QID_candidates_inactive':True,'all_output_files_byte_identical_offline_replay':True,'hemisphere_counts':summary['hemisphere_counts']},indent=2))
