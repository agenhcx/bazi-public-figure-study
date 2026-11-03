"""Independent exported-CSV, summary, source overlay, and deterministic replay checks."""
from pathlib import Path
import collections
import csv
import gzip
import hashlib
import json
import re

ROOT=Path('/workspace/scratch/7e8aa4e0d4af')
STUDY=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2'
OUT=STUDY/'outputs'
QA=ROOT/'academy_next_workers/qa'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):
    b=p.read_bytes()
    if p.suffix=='.gz':b=gzip.decompress(b)
    return [json.loads(x) for x in b.splitlines() if x]
def csvread(p):
    with p.open(newline='') as f:
        rd=csv.DictReader(f)
        return rd.fieldnames,list(rd)
def cv(v):return '' if v is None else str(v)
def key(r):return r['cohort'],r['record_id']
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))

rows=jl(OUT/'birthplace_rows.jsonl.gz')
assert [key(x) for x in rows]==sorted(key(x) for x in rows)
bykey={key(r):r for r in rows}
base=jl(ROOT/'uk_birthplace_checkout/studies/academy_birthplace_screen_v1/outputs/birthplace_rows.jsonl.gz')
uk=jl(ROOT/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v10/outputs/uk_birthplace_rows.jsonl.gz')
base=[x for x in base if x['cohort']!='UK_Royal_Society']+uk
before={key(r):r for r in base}

cols,export=csvread(OUT/'birthplaces.csv')
expected=[{c:cv(r.get(c)) for c in cols} for r in rows]
assert export==expected
ucols,unknown=csvread(OUT/'remaining_unknown.csv')
assert ucols==cols and unknown==[r for r in export if r['hemisphere']=='unknown']
assert len(export)==11094 and len(unknown)==1766

diff=[r for r in rows if canon(r)!=canon(before[key(r)])]
changes=[]
for r in diff:
    b=before[key(r)]
    changes.append({'cohort':r['cohort'],'record_id':r['record_id'],'name':r['name'],'dob':r['dob'],
        'before_hemisphere':b['hemisphere'],'after_hemisphere':r['hemisphere'],
        'before_raw_birthplace':b['raw_birthplace'],'after_raw_birthplace':r['raw_birthplace'],
        'birthplace_source_grade':r['birthplace_source_grade']})
assert changes==jl(OUT/'changes.jsonl.gz')
ccols,cexport=csvread(OUT/'changed_records.csv')
assert cexport==[{c:cv(x[c]) for c in ccols} for x in changes]

countries=[]
for c in sorted({r['cohort'] for r in rows}):
    cohort=[r for r in rows if r['cohort']==c]
    old=[r for r in base if r['cohort']==c]
    counts=collections.Counter(r['hemisphere'] for r in cohort)
    oldcounts=collections.Counter(r['hemisphere'] for r in old)
    countries.append({'cohort':c,'baseline_rows':len(cohort),
        **{h:counts[h] for h in ('north','south','equator','unknown')},
        'previous_unknown':oldcounts['unknown'],
        'newly_classified':oldcounts['unknown']-counts['unknown']})
sc,cs=csvread(OUT/'all_country_birthplace_summary.csv')
assert cs==[{c:cv(r[c]) for c in sc} for r in countries]

summary=json.loads((OUT/'summary.json').read_text())
assert summary['country_summary']==countries
assert summary['cohort_records']==summary['unique_within_cohort_keys']==11094
assert summary['new_fact_candidates']==summary['newly_classified']==3
assert summary['new_fact_source_grade_counts']=={'S1':3}
assert summary['new_fact_cohort_counts']=={'Fields_main':2,'Nobel_science':1}
assert summary['other_unchanged_rows']==11091
assert summary['new_country_or_birthpoint_assignments']==0
assert summary['cross_cohort_deduplicated'] is False
assert summary['final_cohort_frozen'] is False
assert summary['BaZi_or_outcomes_added'] is False
for c,data in summary['observed_native_DOB_windows'].items():
    observed=[r for r in rows if r['cohort']==c and re.fullmatch(r'\d{4}-\d{2}-\d{2}',r['dob'])]
    window=[r for r in observed if 1835<=int(r['dob'][:4])<=1985]
    assert data['native_nonblank_day_rows']==len(observed)
    assert data['native_window_1835_1985_rows']==len(window)
    assert data['hemisphere_counts']==dict(collections.Counter(r['hemisphere'] for r in window))
    assert data['descriptive_only_not_calendar_eligibility_adjudication'] is True
    assert data['source_birth_years_not_used_to_fill_native_DOB_or_window'] is True
for path,h in summary['inputs_sha256'].items():
    assert sha(STUDY.parents[1]/path)==h

facts=jl(STUDY/'inputs/new_birthplace_facts.jsonl.gz')
original=jl(ROOT/'academy_next_workers/fields/accepted.jsonl')+jl(ROOT/'academy_next_workers/nobel/retained/birthplace_facts.jsonl')
original={key(f):f for f in original}
for f in facts:
    src=original[key(f)]
    r=bykey[key(f)]
    assert r['v2_birthplace_fact_evidence']==f
    assert f['raw_birthplace']==src['raw_birthplace']
    assert f['source_sha256']==src['source_sha256']==r['birthplace_source_sha256']
    assert f['evidence_quote']==src['evidence_quote']==r['birthplace_evidence_excerpt']
    assert f['source_grade']==src['source_grade']=='S1'
    assert f['native_dob']==src['native_dob']==r['dob']
    assert f['geography']['country_assigned'] is False
    assert f['geography']['birthpoint_coordinates_assigned'] is False
    assert r['v2_geographic_review']==f['geography']

files=sorted(p for p in OUT.iterdir() if p.is_file())
replay=QA/'replay_outputs'
assert len(files)==7
assert [p.name for p in files]==sorted(p.name for p in replay.iterdir() if p.is_file())
replayhash={}
for p in files:
    assert p.read_bytes()==(replay/p.name).read_bytes(),p.name
    replayhash[p.name]=sha(p)
    if p.suffix=='.gz':assert int.from_bytes(p.read_bytes()[4:8],'little')==0
report={'status':'PASS','csv_rows':{'birthplaces':len(export),'remaining_unknown':len(unknown),
    'changed_records':len(cexport),'country_summary':len(cs)},
    'all_csv_values_match_jsonl':True,'summary_recomputed_from_rows_and_composed_baseline':True,
    'source_facts_match_frozen_worker_captures':True,'native_window_counts_recomputed_without_source_year_adoption':True,
    'byte_identical_replay_output_count':len(files),'gzip_mtime_zero':True,'output_sha256':replayhash}
(QA/'csv_summary_replay_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','replayed':len(files),'csv_rows':report['csv_rows']}))
