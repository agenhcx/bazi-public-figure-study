"""Audit the v3 exports and seven-output replay; all fact totals are dynamic."""
from pathlib import Path
import argparse
import collections
import csv
import gzip
import hashlib
import json
import re

ROOT=Path('/workspace/scratch/7e8aa4e0d4af')
QA=ROOT/'academy_v3_workers/qa'
BASE=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):
    b=p.read_bytes()
    if p.suffix=='.gz':b=gzip.decompress(b)
    return [json.loads(x) for x in b.splitlines() if x]
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def key(r):return r['cohort'],r['record_id']
def cv(x):return '' if x is None else str(x)
def readcsv(p):
    with p.open(newline='') as h:
        rd=csv.DictReader(h)
        return rd.fieldnames,list(rd)
p=argparse.ArgumentParser()
p.add_argument('--study',required=True,type=Path)
p.add_argument('--replay',required=True,type=Path)
a=p.parse_args();out=a.study/'outputs'
base=jl(BASE);rows=jl(out/'birthplace_rows.jsonl.gz')
before={key(r):r for r in base}
assert len(rows)==11094 and [key(r) for r in rows]==sorted(key(r) for r in rows)
facts=jl(a.study/'inputs/new_birthplace_facts.jsonl.gz')
cols,allcsv=readcsv(out/'birthplaces.csv')
assert allcsv==[{c:cv(r.get(c)) for c in cols} for r in rows]
ucols,unknown=readcsv(out/'remaining_unknown.csv')
assert ucols==cols and unknown==[r for r in allcsv if r['hemisphere']=='unknown']
changed=[r for r in rows if canon(r)!=canon(before[key(r)])]
assert len(changed)==len(facts)
changes=[]
for r in changed:
    old=before[key(r)]
    changes.append({'cohort':r['cohort'],'record_id':r['record_id'],'name':r['name'],'dob':r['dob'],
        'before_hemisphere':old['hemisphere'],'after_hemisphere':r['hemisphere'],
        'before_raw_birthplace':old['raw_birthplace'],'after_raw_birthplace':r['raw_birthplace'],
        'birthplace_source_grade':r['birthplace_source_grade']})
assert jl(out/'changes.jsonl.gz')==changes
ccols,changes_csv=readcsv(out/'changed_records.csv')
assert changes_csv==[{c:cv(r[c]) for c in ccols} for r in changes]
summaryrows=[]
for c in sorted({r['cohort'] for r in rows}):
    rs=[r for r in rows if r['cohort']==c]
    bs=[r for r in base if r['cohort']==c]
    n=collections.Counter(r['hemisphere'] for r in rs)
    b=collections.Counter(r['hemisphere'] for r in bs)
    summaryrows.append({'cohort':c,'baseline_rows':len(rs),
        **{h:n[h] for h in ('north','south','equator','unknown')},
        'previous_unknown':b['unknown'],'newly_classified':b['unknown']-n['unknown']})
scols,summary_csv=readcsv(out/'all_country_birthplace_summary.csv')
assert summary_csv==[{c:cv(r[c]) for c in scols} for r in summaryrows]
summary=json.loads((out/'summary.json').read_text())
assert summary['country_summary']==summaryrows
assert summary['cohort_records']==summary['unique_within_cohort_keys']==11094
assert summary['new_fact_candidates']==len(facts)
assert summary['new_fact_source_grade_counts']==dict(collections.Counter(f['source_grade'] for f in facts))
assert summary['new_fact_cohort_counts']==dict(collections.Counter(f['cohort'] for f in facts))
assert summary['newly_classified']==sum(x['newly_classified'] for x in summaryrows)
assert summary['other_unchanged_rows']==11094-len(facts)
assert summary['new_country_or_birthpoint_assignments']==0
assert summary['cross_cohort_deduplicated'] is False
assert summary['final_cohort_frozen'] is False
assert summary['BaZi_or_outcomes_added'] is False
for c,s in summary['observed_native_DOB_windows'].items():
    observed=[r for r in rows if r['cohort']==c and re.fullmatch(r'\d{4}-\d{2}-\d{2}',r['dob'])]
    window=[r for r in observed if 1835<=int(r['dob'][:4])<=1985]
    assert s['native_nonblank_day_rows']==len(observed)
    assert s['native_window_1835_1985_rows']==len(window)
    assert s['hemisphere_counts']==dict(collections.Counter(r['hemisphere'] for r in window))
    assert s['descriptive_only_not_calendar_eligibility_adjudication'] is True
    assert s['source_birth_years_not_used_to_fill_native_DOB_or_window'] is True
for path,h in summary['inputs_sha256'].items():
    assert sha(a.study.parents[1]/path)==h

files=sorted(p for p in out.iterdir() if p.is_file())
assert len(files)==7
assert sorted(p.name for p in files)==sorted(p.name for p in a.replay.iterdir() if p.is_file())
hashes={}
for f in files:
    assert f.read_bytes()==(a.replay/f.name).read_bytes(),f.name
    if f.suffix=='.gz':assert int.from_bytes(f.read_bytes()[4:8],'little')==0
    hashes[f.name]=sha(f)
report={'status':'PASS','new_facts':len(facts),'csv_rows':{'birthplaces':len(allcsv),
    'remaining_unknown':len(unknown),'changed_records':len(changes_csv),'country_summary':len(summary_csv)},
    'every_CSV_value_matches_JSONL':True,'summary_recomputed_from_direct_v2_baseline':True,
    'native_windows_recomputed_without_source_year_adoption':True,
    'byte_identical_replay_output_count':len(files),'gzip_mtime_zero':True,'output_sha256':hashes}
(QA/'csv_summary_replay_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','new_facts':len(facts),'replayed':len(files),'csv_rows':report['csv_rows']}))
