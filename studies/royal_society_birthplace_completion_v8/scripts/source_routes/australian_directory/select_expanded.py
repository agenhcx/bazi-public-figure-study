from pathlib import Path
import gzip,json,re,unicodedata,urllib.parse,hashlib
O=Path(__file__).parent;B=O.parents[1]/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v7/outputs/uk_birthplace_rows.jsonl.gz'
R=[r for r in map(json.loads,gzip.open(B,'rt')) if r['hemisphere']=='unknown' and 1835<=int(r['dob'][:4])<=1985]
def n(s):return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).strip()
L=json.loads((O/'expanded_index_links.json').read_text());people=[]
for l in L:
 if '/biogs/' in l['url'] and re.search(r'/[Pp]\d+[bp]\.htm',l['url']):people.append(dict(l,route='eoas'))
 elif '/fellows-biographical-memoirs/' in l['url'] and re.search(r'-\d{4}-\d{4}(?:-\d+)?/?$',l['url']):people.append(dict(l,route='aas_memoir'))
seen=set();P=[]
for l in people:
 if l['url'] not in seen:P.append(l);seen.add(l['url'])
out=[]
for r in R:
 full=r.get('source_authorised_full_name') or r['name'];parts=full.split(';');surname=n(parts[0]);given=[]
 for part in parts[1:]:
  pre=part.split('(')[0]
  if n(pre) not in ['sir','dr','professor','prof','lord','captain','reverend']:given.extend(n(pre).split())
  if '(' in part:break
 m=re.search(r'\((\d{4})\s*[-–]\s*(\d{4})\)',full);birth=int(r['dob'][:4]);death=int(m[2]) if m else None
 for l in P:
  text=n(l['label'] if l['route']=='eoas' else urllib.parse.unquote(l['url'].split('/')[-1]));tokens=text.split()
  if not re.search(r'(?<!\w)'+re.escape(surname)+r'(?!\w)',text):continue
  if given and not (given[0] in tokens or given[0][0] in tokens):continue
  years=[int(y) for y in re.findall(r'\b(?:18|19|20)\d{2}\b',text)]
  if years and birth not in years:continue
  score=4 if l['route']=='eoas' else 0
  score+=3 if given and given[0] in tokens else 0
  score+=10 if given and all(g in tokens for g in given) else 0
  score+=10 if birth in years else 0
  score+=5 if death and death in years else 0
  out.append({**l,'record_id':r['record_id'],'native_dob':r['dob'],'official_full_name':full,'name':r['name'],'score':score,'index_years':years})
out.sort(key=lambda r:(-r['score'],r['record_id'],r['url']));selected=[];ridseen=set()
for l in out:
 if l['record_id'] not in ridseen and len(selected)<8:selected.append(l);ridseen.add(l['record_id'])
(O/'expanded_selection.json').write_text(json.dumps({'input_base_sha256':hashlib.sha256(B.read_bytes()).hexdigest(),'native_window_targets':len(R),'unique_index_person_links':len(P),'candidates':out,'selected':selected,'body_limit':8,'ranking':'Prefer explicit full-name and life-year index matches; EOAS fields before similarly matched AAS prose; at most one new body per native record.'},ensure_ascii=False,indent=2))
print('INDEX_people',len(P),'CANDIDATE_links',len(out),'SELECTED',len(selected))
for l in selected:print(l['record_id'],l['official_full_name'],'=>',l['label'],l['url'])
