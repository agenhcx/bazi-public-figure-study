import pathlib,json,re,unicodedata,hashlib,collections
ROOT=pathlib.Path('academy_v3_workers/nas_memoirs')
rows=[json.loads(l) for l in (ROOT/'unknown_selection.jsonl').read_text().splitlines()]
nas=['Myriam P. Sarachik','Louis Agassiz','Joseph Henry','Thomas Edison','Alexander Graham Bell','Margaret Mead','John Dewey','Richard D. Alexander','Wylie W. Vale Jr.','Stuart A. Rice','Kenneth Wiberg','Jay Quade','Shlomo Sternberg','Luis Sequeira','Walter J. Gehring','Ira B. Bernstein','John B. Gurdon']
nap=['HERBERT L. ANDERSON','ARCHIBALD PHILIP BARD','SUBRAHMANYAN CHANDRASEKHAR','ROBERT BRAINARD COREY','ALBERT DORFMAN','LEE ALVIN DUBRIDGE','LEO GOLDBERG','LOUIS PLACK HAMMETT','EMIL WALTER HAURY','RAYMOND GEORGE HERB','JAMES GORDON HORSFALL','EMIL THOMAS KAISER','DONALD WILLIAM KERST','PAUL JACKSON KRAMER','MILTON STANLEY LIVINGSTON','WILLIAM WILSON MORGAN','MARCUS MORTON RHOADES','HENRY STOMMEL','JOSEPH E. VARNER','PAUL ALFRED WEISS']
nap_pages=['1-13','14-27','28-49','50-69','70-87','88-113','114-135','136-149','150-175','176-191','192-217','218-233','234-245','246-263','264-287','288-313','314-329','330-351','352-371','372-386']
def toks(s):
 s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
 return [x for x in re.sub('[^a-z ]',' ',s).split() if x not in ['jr','sr','ii','iii']]
def compatibility(a,b):
 a,b=toks(a),toks(b)
 if a==b:return 'normalized_exact_name'
 if a[-1]!=b[-1]:return None
 if len(a)==len(b) and all(x==y or len(x)==1 and x==y[0] or len(y)==1 and y==x[0] for x,y in zip(a[:-1],b[:-1])):return 'initials_compatible_name'
 if len(b)==2 and len(a)==3 and a[0]==b[0]:return 'omitted_middle_name_weak'
 return None
out=[];subject_rows=[]
for names,source in [(nas,'NAS_landing'),(nap,'NAP_volume72_contents')]:
 for i,name in enumerate(names):
  f=ROOT/('raw/nas_memoirs_nav_01.web_projection.json' if source=='NAS_landing' else 'raw/nas_memoirs_query_03.web_projection.json')
  txt='\n'.join(c.get('text','') for c in json.loads(f.read_text()).get('content',[]));assert name in txt
  url='https://www.nasonline.org/publications/biographical-memoirs/' if source=='NAS_landing' else 'https://www.nationalacademies.org/read/5859'
  loc='turn2102view0; Recently Published L185; observed link89' if source=='NAS_landing' and name=='Jay Quade' else ('turn2110search1; Contents item '+name+' '+nap_pages[i] if source!='NAS_landing' else 'turn2102view0; NAS memoirs landing subject list')
  subject_rows.append({'observed_name':name,'role':'memoir_subject','source':source,'source_url':url,'raw_source_file':str(f),'locator':loc})
  for r in rows:
   match=compatibility(name,r['name'])
   if not match:continue
   out.append({'cohort':'NAS','record_id':r['record_id'],'name':r['name'],'native_dob':r['dob'],'native_dob_status':r['dob_status'],'observed_subject_name':name,'match_kind':match,'identity_status':'provisional_name_only_no_source_dob_or_lifespan','source_dob':None,'source_lifespan':None,'source_subject_role':'memoir_subject','source_grade':'official_index_navigation_only_not_birthplace_evidence','source_url':url,'source_urls':[url],'locator':loc,'evidence_quote':name+(' '+nap_pages[i] if source!='NAS_landing' else ''),'raw_source_file':str(f),'web_projection_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'capture_kind':'web_tool_text_projection','capture_scope':'observed official subject-name index/search-result projection; original HTTP bytes unavailable','observed_chapter_or_pdf_url':None,'birthplace_fact':False,'formal_identity_or_native_dob_modified':False,'qid_used_or_modified':False,'geographic_assignment':False,'frozen_baseline_row':r})
(ROOT/'match_candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in out))
(ROOT/'retained/observed_subject_lists.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in subject_rows))
summary={'official_subject_names_observed':len(subject_rows),'NAS_landing_subjects':len(nas),'NAP_volume72_subjects':len(nap),'matching_candidates':len(out),'unique_baseline_rows_matched':len({r['record_id'] for r in out}),'match_kind_counts':dict(collections.Counter(r['match_kind'] for r in out)),'all_provisional':True,'index_source_dob_or_lifespan_present':False,'birthplace_facts':0,'network_requests_by_matcher':0,'excluded':'authors are not memoir subjects; surname-only mismatches excluded; nonofficial search sources excluded','limitations':'NAP Volume72 was observed in search-result projection, not a complete runtime index. No observed individual chapter URL is present yet. Native DOB values are frozen baseline values, not source-index claims.'}
(ROOT/'retained/match_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps(summary,indent=2))
for r in out:print(r['name'],r['native_dob'],r['match_kind'])
