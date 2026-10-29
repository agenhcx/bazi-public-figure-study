#!/usr/bin/env python3
"""Public NDL Authorities batch retrieval. Names only are provisional matches."""
import csv,json,re,urllib.request,urllib.parse,hashlib,datetime,time,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PREFIX='''PREFIX foaf:<http://xmlns.com/foaf/0.1/> PREFIX rda:<http://RDVocab.info/ElementsGr2/> PREFIX xl:<http://www.w3.org/2008/05/skos-xl#> PREFIX skos:<http://www.w3.org/2004/02/skos/core#> '''
def compact(s):return re.sub(r'\s+','',s)
def endpoint(q):return 'https://id.ndl.go.jp/auth/ndla/sparql?query='+urllib.parse.quote(q)+'&output=json'
def fetch(q,p):
 u=endpoint(q);now=datetime.datetime.now(datetime.timezone.utc).isoformat();r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'AcademyResearch/1.0 (public biographical source audit)','Accept':'application/sparql-results+json'}),timeout=60);data=r.read();p.write_bytes(data)
 return json.loads(data),{'url':u,'retrieved_at':now,'http_status':r.status,'sha256':hashlib.sha256(data).hexdigest(),'raw_capture':str(p),'bytes':len(data)}
def project_root():
 return next((base for a in [ROOT,*ROOT.parents] for base in [a,a/'academy_completion_checkout'] if (base/'studies/academy_reopen_fr_jp_v1/inputs/japan_science_candidates.csv').exists()),ROOT.parent.parent/'academy_completion_checkout')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--input',default=str(project_root()/'studies/academy_reopen_fr_jp_v1/inputs/japan_science_candidates.csv'));args=parser.parse_args()
 rows=list(csv.DictReader(open(args.input,encoding='utf-8-sig')));raw=ROOT/'private';raw.mkdir(exist_ok=True);log=[];out=[];events=[]
 for start in range(0,len(rows),45):
  batch=rows[start:start+45];names=[compact(r['name_jp']) for r in batch]
  q=PREFIX+'SELECT ?auth ?entity ?name ?birth ?death ?label WHERE { VALUES ?name {'+' '.join(json.dumps(n,ensure_ascii=False) for n in names)+'} ?auth foaf:primaryTopic ?entity. ?entity foaf:name ?name. OPTIONAL {?entity rda:dateOfBirth ?birth} OPTIONAL {?entity rda:dateOfDeath ?death} OPTIONAL {?auth xl:prefLabel/xl:literalForm ?label} } LIMIT 1000'
  p=raw/f'batch_{start:03}.json'
  try:
   if p.exists():d=json.loads(p.read_bytes()); meta={'url':endpoint(q),'retrieved_at':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),'http_status':200,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'raw_capture':str(p),'cache_replay':True}
   else:d,meta=fetch(q,p)
   log.append(meta);bindings=d['results']['bindings'];print(start,len(bindings),flush=True)
   for row in batch:
    matches=[{k:v['value'] for k,v in b.items()} for b in bindings if b['name']['value']==compact(row['name_jp'])]
    unique={m['auth'] for m in matches}; status='unique_name_match_not_identity_accepted' if len(unique)==1 else 'ambiguous_name_match' if len(unique)>1 else 'no_exact_name_match'
    events.append({'member_key':row['member_key'],'name_jp':row['name_jp'],'match_status':status,'authority_candidates':len(unique),'authority_uris':'|'.join(sorted(unique))})
    for m in matches:
     birth=m.get('birth','');precision='day' if re.fullmatch(r'\d{4}-\d{2}-\d{2}',birth) else 'month' if re.fullmatch(r'\d{4}-\d{2}',birth) else 'year' if re.fullmatch(r'\d{4}',birth) else 'unparsed' if birth else 'missing'
     out.append({'member_key':row['member_key'],'name_jp':row['name_jp'],'source_name':m['name'],'source_url':m['auth'].replace('http:','https:'),'source_entity':m['entity'],'source_label':m.get('label',''),'source_death_raw':m.get('death',''),'source_birth_raw':birth,'birth_precision':precision,'calendar':'not_stated','source_tier':'national_library_authority_body','match_status':status,'identity_accepted':False,'final_cohort_accepted':False,'bazi_computed':False,'source_capture_sha256':meta['sha256'],'retrieved_at':meta['retrieved_at']})
  except Exception as e:log.append({'batch_start':start,'error':repr(e),'url':endpoint(q)});print(start,'ERROR',repr(e),flush=True)
  (ROOT/'request_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2));time.sleep(.5)
 for name,data in [('claims.csv',out),('candidate_matches.csv',events)]:
  with (ROOT/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]) if data else ['member_key']);w.writeheader();w.writerows(data)
 summary={'input_candidates':len(rows),'processed_candidates':len(events),'authority_claim_rows':len(out),'candidates_with_exact_name_match':sum(x['authority_candidates']>0 for x in events),'candidates_unique_name_match':sum(x['authority_candidates']==1 for x in events),'ambiguous_candidates':sum(x['authority_candidates']>1 for x in events),'no_exact_name_match':sum(x['authority_candidates']==0 for x in events),'precision_counts':{p:sum(x['birth_precision']==p for x in out) for p in ['day','month','year','missing','unparsed']},'source_requests':len(log),'failed_requests':sum('error' in x for x in log),'identity_accepted':0,'final_cohort_accepted':0,'bazi_computed':0,'limitation':'Exact compact-name matching only. All authority assignments remain provisional pending same-person evidence; never promote name-only matches to accepted DOB. Birth precision reflects literal authority field without padding or calendar conversion.'}
 summary['candidates_with_at_least_one_birthyear_name_match']=len({x['member_key'] for x in out if x['birth_precision']=='year'})
 summary['unique_name_candidates_with_birthyear']=len({x['member_key'] for x in out if x['birth_precision']=='year' and x['match_status']=='unique_name_match_not_identity_accepted'})
 summary['successful_batch_row_counts']=[len(json.loads(p.read_bytes())['results']['bindings']) for p in sorted(raw.glob('batch_*.json'))]
 summary['source_documentation_urls']=['https://id.ndl.go.jp/information/sparql/','https://id.ndl.go.jp/information/sparql-11/']
 (ROOT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(summary)
if __name__=='__main__':main()
