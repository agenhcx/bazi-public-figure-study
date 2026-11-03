#!/usr/bin/env python3
"""Check complete native-field invariance, evidence boundaries and deterministic replay."""
from pathlib import Path
from collections import Counter
import csv,gzip,hashlib,importlib.util,json,subprocess,sys,tempfile
s=Path(__file__).resolve().parents[1];repo=s.parents[1]
spec=importlib.util.spec_from_file_location('v7_assembler',s/'scripts/assemble.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def read(p):
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
base=read(repo/'studies/royal_society_birthplace_completion_v6/outputs/uk_birthplace_rows.jsonl.gz');old={r['record_id']:r for r in base}
rows=read(s/'outputs/uk_birthplace_rows.jsonl.gz');assert len(rows)==4983==len({r['record_id'] for r in rows})
for r in rows:
 b=old[r['record_id']]
 assert all(r.get(k)==v for k,v in b.items() if k not in m.GEO_FIELDS),(r['record_id'],'non-geographic field changed')
 assert r['dob']==b['dob'] and r['lookup_qid']==b['lookup_qid'] and r['wikidata_qid']==b['wikidata_qid']
 assert r['final_analysis_eligibility_assigned']==b['final_analysis_eligibility_assigned']
 invalid={c['candidate_id'] for c in r.get('quarantined_birthplace_evidence_candidates',[])}
 assert not invalid & {c['candidate_id'] for c in r['birthplace_evidence_candidates']}
 if r.get('v7_lookup_replacement_evidence'):
  link=r['v7_lookup_replacement_evidence'];assert link['identity_verified'] is True
  assert r['active_geography_lookup_qid']==link['new_active_qid']
  assert link['native_dob']==r['dob']
 elif r.get('geography_lookup_qid_quarantined'):assert r['active_geography_lookup_qid']==''
 if b['hemisphere']!='unknown':assert r['hemisphere']==b['hemisphere']
 for c in r['birthplace_evidence_candidates']:
  if c['origin'].startswith('v7_'):
   fact=c['birthplace_fact_evidence'];assert fact['native_dob']==r['dob'];assert fact['record_id']==r['record_id']
   assert len(c['evidence_quote'].split())<=25
   assert c['geography'].get('country_assigned') is not True
   assert c['geography'].get('birthpoint_coordinates_assigned') is not True
summary=json.loads((s/'outputs/summary.json').read_text());assert summary['hemisphere_counts']==dict(Counter(r['hemisphere'] for r in rows))
for p,digest in summary['inputs_sha256'].items():assert hashlib.sha256((repo/p).read_bytes()).hexdigest()==digest
with (s/'outputs/uk_birthplaces.csv').open() as f:csvrows=list(csv.DictReader(f))
assert len(csvrows)==4983 and Counter(r['hemisphere'] for r in csvrows)==Counter(r['hemisphere'] for r in rows)
for fn in ['all_country_birthplace_summary.csv']:
 with (s/'outputs'/fn).open() as f:now=list(csv.DictReader(f))
 with (repo/'studies/royal_society_birthplace_completion_v6/outputs'/fn).open() as f:prior=list(csv.DictReader(f))
 assert [r for r in now if r['cohort']!='UK_Royal_Society']==[r for r in prior if r['cohort']!='UK_Royal_Society']
with tempfile.TemporaryDirectory() as d:
 subprocess.run([sys.executable,str(s/'scripts/assemble.py'),'--output',d],stdout=subprocess.DEVNULL,check=True)
 for p in (s/'outputs').iterdir():
  if p.is_file():assert p.read_bytes()==(Path(d)/p.name).read_bytes(),p.name
print(json.dumps({'status':'PASS','rows':4983,'all_existing_non_geography_fields_preserved':True,'DOB_and_original_identity_flags_unchanged':True,'old_quarantined_candidates_inactive':True,'new_lookup_replacements_independently_verified':True,'other_countries_unchanged':True,'all_outputs_byte_identical_offline_replay':True,'hemisphere_counts':summary['hemisphere_counts']},indent=2))
