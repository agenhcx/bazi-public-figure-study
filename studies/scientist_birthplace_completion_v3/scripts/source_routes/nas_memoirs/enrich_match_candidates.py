import pathlib,json,re,html,hashlib,collections
R=pathlib.Path('academy_v3_workers/nas_memoirs')
p=R/'raw/nas_memoirs_nav_05.html';raw=p.read_bytes();text=raw.decode('utf-8').replace('\\"','"');sha=hashlib.sha256(raw).hexdigest()
ledger=[json.loads(x) for x in (R/'retained/request_ledger.jsonl').read_text().splitlines()]
meta=next(x for x in ledger if x.get('request_id')=='nas_memoirs_nav_05' and x.get('event')=='result');assert meta['original_bytes_sha256']==sha
pat=r'<p class="tocchap"><a href="([^"]+)">([^<]+)</a><br\s*/>\s*(.*?)</p>'
toc={}
for m in re.finditer(pat,text,re.S):
 href,name,author=m.groups();chapter=int(re.search('/chapter/(\d+)',href)[1]);author=' '.join(html.unescape(re.sub('<[^>]+>',' ',author)).split())
 toc[name]={'observed_subject_name':html.unescape(name),'observed_chapter_or_pdf_url':href,'observed_chapter_url':href,'observed_chapter_number':chapter,'memoir_author_as_printed':author,'memoir_author':re.sub('^BY ','',author),'source_author':re.sub('^BY ','',author),'index_publisher':'National Academy of Sciences / National Academy Press','index_locator':f'original HTML p.tocchap at line {text.count(chr(10),0,m.start())+1}; exact subject-name anchor and following author line','index_raw_source_file':str(p),'original_bytes_sha256':sha,'capture_kind':meta['capture_kind'],'capture_scope':meta['capture_scope'],'retrieved_utc':meta['utc'],'index_source_url':'https://www.nationalacademies.org/read/5859','source_dob':None,'source_dob_precision':'none','source_lifespan':None,'identity_status':'provisional_name_compatibility_only_no_source_dob_or_lifespan','approval_status':'hold_for_fulltext_approval','full_memoir_body_fetched':False,'proposed_fulltext_source_grade':'S2_edited_memoir'}
rows=[json.loads(x) for x in (R/'match_candidates.jsonl').read_text().splitlines()];strong=[];weak=[]
for r in rows:
 if r['observed_subject_name'] not in toc:continue
 r.update(toc[r['observed_subject_name']]);r['locator']=r['index_locator'];r['raw_source_file']=str(p);r['web_projection_sha256']=None;r['source_urls']=['https://www.nationalacademies.org/read/5859',r['observed_chapter_url']];r['source_url']='https://www.nationalacademies.org/read/5859';r['evidence_quote']=r['observed_subject_name']+'; '+r['memoir_author_as_printed'];r['strong_linked_candidate']=r['match_kind']=='initials_compatible_name'
 if r['strong_linked_candidate']:strong.append(r)
 else:weak.append(r)
assert len(strong)==8 and {r['observed_chapter_number'] for r in strong}=={4,7,11,14,15,17,18,20}
assert len(weak)==1 and weak[0]['name']=='Robert Corey'
for filename,data in [('match_candidates.jsonl',rows),('retained/strong_linked_candidates.jsonl',strong),('retained/weak_candidates.jsonl',weak),('retained/nap_volume72_toc_metadata.jsonl',list(toc.values()))]:
 (R/filename).write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in data))
summary=json.loads((R/'retained/match_summary.json').read_text());summary.update({'strong_linked_candidates':8,'weak_omitted_middle_candidates':1,'landing_only_exact_candidate':1,'original_index_bytes_sha256':sha,'strong_linked_chapters':sorted(r['observed_chapter_number'] for r in strong),'all_hold_for_fulltext_approval':True,'full_memoir_body_reads':0,'limitations':'Observed complete NAP volume72 frontmatter/contents HTML gives actual subject names, authors, and chapter URLs. These index entries contain no subject DOB/lifespan; all identity matches remain provisional. Robert Corey omitted-middle candidate is held separately and excluded from the eight initials-compatible linked candidates. Jay Quade remains landing-only. No individual chapter was requested by this matcher.'})
(R/'retained/match_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
for r in strong:print(r['name'],r['native_dob'],r['observed_chapter_url'],r['memoir_author'])
print('strong',len(strong),'weak',len(weak),'index_sha',sha)
