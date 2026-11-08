"""Cumulative quote review across targeted native objects and actual current observations."""
import datetime,json,re
import qa_v43_source as q
W=q.W;S=q.S
def url(d,parent=None):
 for key in ['source_url','url','source_doi','birthplace_source_url']:
  v=d.get(key)
  if isinstance(v,str) and v:
   if ' | ' in v:
    originals=[part.strip() for part in v.split(' | ') if part.strip().startswith('https://doi.org/')]
    if len(originals)==1:return originals[0]
   return 'https://doi.org/'+v if key=='source_doi' and not v.startswith('http') else v
 for key in ['source_urls','birthplace_source_urls']:
  v=d.get(key)
  if isinstance(v,list) and len(v)==1 and isinstance(v[0],str):return v[0]
 return parent
def walk(d,parent=None):
 if isinstance(d,dict):
  u=url(d,parent)
  for key in ['source_quote','evidence_quote','quote']:
   if isinstance(d.get(key),str) and d[key].strip():yield u,' '.join(d[key].split())
  for v in d.values():yield from walk(v,u)
 elif isinstance(d,list):
  for v in d:yield from walk(v,parent)
def main():
 paths=[W/f'v43_scope_{g}.json' for g in 'abc']+[W/f'v43_sources_{g}.json' for g in 'abc']+[S/'inputs/accepted_geography.json',S/'audit/followup_holds.json',S/'audit/root_followups.json'];works={};missing=[]
 historical=[p for p in sorted((q.OLD/'audit').glob('*.json')) if re.fullmatch(r'prior_v\d+_(holds|geography_candidates)\.json',p.name)]
 ids=set(q.rd(W/'v43_method_application_scope.json')['fixed_record_ids'])
 def targeted(d):
  if isinstance(d,dict):
   if d.get('record_id') in ids:yield d
   else:
    for v in d.values():yield from targeted(v)
  elif isinstance(d,list):
   for v in d:yield from targeted(v)
 for p in historical:
  # Read every complete history inventory before selecting its targeted contexts.
  obj=q.rd(p)
  for record in targeted(obj):
   for u,quote in walk(record):
    if not u:missing.append({'path':p.name,'quote':quote})
    else:works.setdefault(u,set()).add(quote)
 for p in paths:
  for u,quote in walk(q.rd(p)):
   if not u:missing.append({'path':p.name,'quote':quote})
   else:works.setdefault(u,set()).add(quote)
 snippets={u:sorted(v for v in values if not any(v!=other and v in other for other in values)) for u,values in works.items()};counts={u:sum(len(v.split()) for v in values) for u,values in snippets.items()}
 for g in 'abc':
  for u in q.rd(W/f'v43_sources_{g}.json').get('source_quote_words_by_original_work',{}):counts.setdefault(u,0)
 for u in q.rd(S/'audit/root_followups.json').get('quote_words_by_original_work',{}):counts.setdefault(u,0)
 passed=not missing and all(v<=25 for v in counts.values());out={'schema':'UK_v43_cumulative_quote_prefinal_v1','written_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'targeted_inherited_worker_root_quote_prefinal','passed':passed,'scope':'Retained quote/evidence_quote/source_quote fields from complete current target objects and all targeted historical holds/candidates, deduplicated by observed work URL; DOI/carrier combined strings map to the original DOI. Contained duplicate passages counted once. No raw source acquisition.','original_work_distinct_whitespace_quoted_word_counts':dict(sorted(counts.items())),'retained_distinct_passages':snippets,'unattributed_quotations':missing,'artifact_sha256':{str(p.relative_to(W)):q.sha(p) for p in paths+historical}}
 (W/'v43_source_qa_quote_prefinal.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':passed,'works':len(counts),'counts':counts,'unattributed':missing}));return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
