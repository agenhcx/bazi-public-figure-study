import gzip,json,re,pathlib,hashlib,unicodedata
BASE=pathlib.Path('academy_v5_workers/vol76');baseline=pathlib.Path('uk_birthplace_checkout/studies/scientist_birthplace_completion_v4/outputs/birthplace_rows.jsonl.gz')
assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='abbce4e99ad51252dd5e127a0609bc6c4950c121afa2dd126bfc2187b39cd4e8'
allrows=[json.loads(l) for l in gzip.open(baseline,'rt')];nas=[r for r in allrows if r['cohort']=='NAS'];unknown=[r for r in nas if r['hemisphere']=='unknown'];links=json.loads((BASE/'retained/volume76_toc_observed_links.json').read_text());toc=[{'source_heading':re.sub(r' [0-9]+-[0-9]+$','',n),'observed_url':u,'source_lifespan':'not_present_in_TOC'} for u,n in links if re.search(r' [0-9]+-[0-9]+$',n)]
def parts(n):
 n=unicodedata.normalize('NFKD',n).encode('ascii','ignore').decode().lower();t=re.findall('[a-z]+',n);return [a for a in t if a not in ['jr','sr','ii','iii','iv']]
def compare(n,t):
 a,b=parts(n),parts(t)
 if a==b:return 'canonical_full_name'
 if a[-1:]==b[-1:] and a[0][:1]==b[0][:1]:
  if len(a)==len(b) and all(x==y or len(x)==1 and y.startswith(x) or len(y)==1 and x.startswith(y) for x,y in zip(a,b)):return 'surname_plus_compatible_fullnames_initials_routing_only'
  if a[0]==b[0]:return 'surname_plus_exact_first_name_with_middle_name_difference_routing_only'
  return 'surname_plus_first_initial_candidate_collision_routing_only'
 return None
coverage=[]
for r in unknown:
 matches=[{**t,'routing_method':m} for t in toc if (m:=compare(r['name'],t['source_heading']))]
 coverage.append({'cohort':'NAS','record_id':r['record_id'],'name':r['name'],'native_dob':r['dob'],'native_window_1835_1985':bool(r['dob'] and '1835-01-01'<=r['dob']<='1985-12-31'),'toc_matches':matches,'coverage_scope':'all_20_Vol76_TOC_headings_compared_to_this_unknown; name/initial routes are not accepted identity','lifespan_check':'baseline has no lifespan/death fields; not independently matched'})
with (BASE/'retained/unknown_coverage.jsonl').open('w') as f:
 for c in coverage:f.write(json.dumps(c)+'\n')
for t in toc:
 t['all_NAS_routing_matches']=[{'name':r['name'],'record_id':r['record_id'],'native_dob':r['dob'],'hemisphere':r['hemisphere'],'method':m} for r in nas if (m:=compare(r['name'],t['source_heading']))]
(BASE/'retained/toc_routing_all2242.json').write_text(json.dumps(toc,indent=2))
print('unknown count',len(unknown),'TOC chapters',len(toc));print(json.dumps([c for c in coverage if c['toc_matches']],indent=2))
