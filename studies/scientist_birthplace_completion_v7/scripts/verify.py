#!/usr/bin/env python3
"""Verify geography-only changes against the explicit current snapshot vector."""
from pathlib import Path
from collections import Counter
import csv,hashlib,importlib.util,json,subprocess,sys,tempfile
s=Path(__file__).resolve().parents[1];repo=s.parents[1]
spec=importlib.util.spec_from_file_location('v7_assembler',s/'scripts/assemble.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
base,paths=m.baseline(s);old={m.key(r):r for r in base};rows=m.read(s/'outputs/birthplace_rows.jsonl.gz')
facts=m.read(s/'inputs/new_birthplace_facts.jsonl.gz');accepted={m.key(f) for f in facts}
assert len(rows)==len({m.key(r) for r in rows})==11094
changed=[]
for r in rows:
 b=old[m.key(r)]
 assert all(r.get(k)==v for k,v in b.items() if k not in m.GEO_FIELDS),(m.key(r),'native field changed')
 if r!=b:changed.append(m.key(r));assert m.key(r) in accepted
 else:assert m.key(r) not in accepted
 if r['cohort']=='UK_Royal_Society':assert r==b
 if r['cohort']=='Nobel_science':assert r['dob']==b['dob']=='' and r['baseline_identification_status']==b['baseline_identification_status']
 if r['cohort']=='CAS':assert r['accepted_gregorian_dob']==b['accepted_gregorian_dob']==''
 if b['hemisphere']!='unknown':assert r['hemisphere']==b['hemisphere']
assert set(changed)==accepted
summary=json.loads((s/'outputs/summary.json').read_text())
assert summary['new_fact_candidates']==len(facts)
for p,h in summary['inputs_sha256'].items():assert hashlib.sha256((repo/p).read_bytes()).hexdigest()==h
with (s/'outputs/birthplaces.csv').open() as f:csvrows=list(csv.DictReader(f))
assert len(csvrows)==11094 and Counter((r['cohort'],r['hemisphere']) for r in csvrows)==Counter((r['cohort'],r['hemisphere']) for r in rows)
for cohort in {r['cohort'] for r in rows}:
 if cohort not in {f['cohort'] for f in facts}:assert [r for r in rows if r['cohort']==cohort]==[r for r in base if r['cohort']==cohort]
with tempfile.TemporaryDirectory() as d:
 subprocess.run([sys.executable,str(s/'scripts/assemble.py'),'--output',d],check=True,stdout=subprocess.DEVNULL)
 for p in (s/'outputs').iterdir():
  if p.is_file():assert p.read_bytes()==(Path(d)/p.name).read_bytes(),p.name
print(json.dumps({'status':'PASS','cohort_records':11094,'changed_rows':len(changed),
 'all_preexisting_non_geographic_fields_preserved':True,'UK_4983_complete_objects_equal':True,
 'Nobel_DOB_blank_and_reconstruction_flags_preserved':True,'CAS_acceptance_still_blank':True,
 'unaffected_cohorts_exactly_unchanged':True,'all_seven_outputs_byte_identical_offline_replay':True},indent=2))
