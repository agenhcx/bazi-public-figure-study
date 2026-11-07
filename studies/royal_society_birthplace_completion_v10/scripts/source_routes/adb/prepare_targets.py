"""Deterministic read-only ADB target projection; retains authority names and native DOB."""
import gzip,json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v9/outputs/uk_birthplace_rows.jsonl.gz'
EXPECTED='e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
assert hashlib.sha256(BASE.read_bytes()).hexdigest()==EXPECTED
rows=[json.loads(x) for x in gzip.open(BASE,'rt')]
targets=[]
for r in rows:
 if r.get('hemisphere')!='unknown':continue
 past=r['record_id'].startswith('RS_PAST_')
 authority=r.get('source_authorised_full_name','') if past else r['name']
 assert authority
 if past:
  bits=[x.strip() for x in authority.split(';')]
  surname=bits[0]
  givens=next((re.sub(r'\s*\([^)]*\).*','',b).strip() for b in bits[1:] if b and b not in ['Sir','Dame','Lord','Lady','Rev','Reverend','Dr']), '')
  canonical=(givens+' '+surname).strip()
 else:
  canonical=authority;surname=canonical.rsplit(' ',1)[-1];givens=canonical.rsplit(' ',1)[0]
 targets.append({'record_id':r['record_id'],'authority_full_name':authority,'canonical_full_name':canonical,'surname':surname,'givens':givens,'native_dob':r['dob'],'in_analysis_window':1835<=int(r['dob'][:4])<=1985,'source_name_basis':'source_authorised_full_name' if past else 'current_full_name','formal_identity_modified':False,'native_dob_modified':False})
targets.sort(key=lambda x:(not x['in_analysis_window'],x['surname'].casefold(),x['givens'].casefold()))
with (ROOT/'targets.jsonl').open('w') as f:
 for t in targets:f.write(json.dumps(t,ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps({'baseline_sha256':EXPECTED,'rows':len(rows),'unknown':len(targets),'window_unknown':sum(t['in_analysis_window'] for t in targets)}))
