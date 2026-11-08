from pathlib import Path
import json,csv
ns={'__file__':'/workspace/scratch/7e8aa4e0d4af/uk_birthplace_v2_workers/current99/fetch_current99.py'}
exec(Path(ns['__file__']).read_text().split('out=[]')[0],ns)
OUT=Path(__file__).parent;CACHE=OUT/'royal_cache';CACHE.mkdir(exist_ok=True);ns['CACHE']=CACHE
prev=[json.loads(l) for l in (OUT/'current99_birthplace_rows.jsonl').read_text().splitlines()]
missing={r['record_id'] for r in prev if not r['raw_birthplace']}
roster=list(csv.DictReader((ns['ROOT']/'data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv').open(encoding='utf-8-sig')))
source={r['cohort_key']:r for r in ns['rows']}
rows=[]
for r in roster:
 if r['cohort_key'] in missing:
  q=dict(source[r['cohort_key']]);q['provenance_source_url']=r['source_url'];rows.append(q)
# For the known Nobel CV-only cases, exact same person's Nobel facts page is
# an additional existing institutional route rather than a name search.
for q in rows:
 if q['cohort_key']=='RS_CURRENT_11666':q['provenance_source_url']='https://www.nobelprize.org/prizes/medicine/2001/hunt/facts/'
 if q['cohort_key']=='RS_CURRENT_12105':q['provenance_source_url']='https://www.nobelprize.org/prizes/chemistry/1986/polanyi/facts/'
 if q['cohort_key']=='RS_CURRENT_12148':q['provenance_source_url']='https://www.nobelprize.org/prizes/medicine/2019/ratcliffe/facts/'
out=[]
with ns['ThreadPoolExecutor'](max_workers=8) as pool:
 for f in ns['as_completed']([pool.submit(ns['fetch'],r) for r in rows]):out.append(f.result())
(OUT/'second_http_observations.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'attempted':len(out),'errors':sum(bool(r['error']) for r in out),'birth_contexts':sum(bool(r.get('birth_contexts')) for r in out)}),flush=True)
