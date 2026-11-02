from pathlib import Path
from urllib.parse import urlparse
from collections import Counter
import json,csv,gzip,re,hashlib
ROOT=Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_checkout');OUT=Path(__file__).parent
source=ROOT/'data/royal_society_dob_freeze_v1/royal_society_current_exact_dob_final_v1.csv'
existing={r['record_id']:r for r in (json.loads(l) for l in gzip.open(ROOT/'studies/academy_birthplace_screen_v1/inputs/existing/UK_Royal_Society.jsonl.gz','rt')) if r['record_id'].startswith('RS_CURRENT_')}
MONTH='January|February|March|April|May|June|July|August|September|October|November|December'
DATE=rf'\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTH})\s+\d{{4}}'
manual={
'RS_CURRENT_11301':('Dacca, East Bengal, India (Asia)','Date of birth 17 November 1942 Place Dacca, East Bengal, India (Asia)'),
'RS_CURRENT_12067':('Shaftesbury, Dorset','Date of birth 27th March 1956 at Shaftesbury, Dorset.'),
'RS_CURRENT_12105':('Berlin, Germany (Europe)','Date of birth 23 January 1929 Place Berlin, Germany (Europe)'),
'RS_CURRENT_11027':('Farnham, Surrey, U.K.','DATE AND PLACE OF BIRTH 19 May 1948; Farnham, Surrey, U.K.'),
'RS_CURRENT_11385':('Victor Harbour, South Australia','Ronald David Ekers was born at Victor Harbour, South Australia on 18 September 1941.'),
'RS_CURRENT_11412':('Gloucestershire, England','Evans was born on 1 January 1941 in Gloucestershire, England.'),
'RS_CURRENT_11468':('Germany','Professor Uta Frith was born on 25th May 1941 in Germany.'),
'RS_CURRENT_11521':('Stourport, Worcestershire, UK','He was born on 8 February 1941 in Stourport, Worcestershire, UK'),
'RS_CURRENT_11607':('Edinburgh, Scotland','I was born in Edinburgh, Scotland, on 19th July 1945.'),
'RS_CURRENT_11726':('Austin, Texas','Biography: Born in Austin, Texas; June 30, 1967'),
'RS_CURRENT_11903':('London, England','DAVID WILLIAM MASSER: Born 8th November 1948 in London, England.'),
'RS_CURRENT_12104':('Ripon, North Yorks, England','Curriculum Vitae - Raymond Alan Plumb March 24, 2011 Born: 30 March 1948; Ripon, North Yorks, England'),
'RS_CURRENT_12276':('London, England','Joseph Ivor Silk, born in London, England, on 3 December 1942'),
'RS_CURRENT_12320':('Wetzlar, Germany','Born: December 29, 1946 (Wetzlar, Germany)'),
'RS_CURRENT_12326':('Harpenden, Hertfordshire','Where and when were you born? 15 May 1949, in Harpenden, Hertfordshire'),
'RS_CURRENT_12339':('Folkestone, Kent','Where and when were you born? Folkestone, on the coast in Kent, on 24 September 1945.'),
'RS_CURRENT_12434':('Toronto, Canada','Scott Tremaine was born in Toronto, Canada, on May 25, 1950.'),
'RS_CURRENT_12512':('Berlin, Germany','Gerald Westheimer was born on May 13, 1924 in Berlin, Germany'),
'RS_CURRENT_12575':('Egypt','Sir Magdi Habib Yacoub, FRS; born 16 November 1935 in Egypt'),
'RS_CURRENT_25290':('Harrogate, UK','Place of Birth Harrogate, UK'),
'RS_CURRENT_35026':('Stranraer, United Kingdom','Interviewee biographical information Born June 21, 1967 Stranraer, United Kingdom'),
'RS_CURRENT_36236':('Lesotho','Tebello Nyokong was born in Lesotho on 20 October 1951'),
'RS_CURRENT_36728':('Lancaster, England','Date and place of birth: 23.5.53, Lancaster, England.'),
}
def grade(u):
 host=urlparse(u).netloc
 return 'S2' if any(x in host for x in ['eoas.info','mathshistory','timeshighereducation','universitas']) else 'S1'
def geo(place,old):
 if place==old.get('raw_birthplace') and old.get('hemisphere') in {'north','south'}:return old['hemisphere'],old.get('country',''),'existing named-locality mapping'
 # The order prevents New South Wales from being mistaken for UK Wales.
 if re.search(r'Australia|New Zealand|South Africa|Lesotho',place,re.I):return 'south','Australia' if 'Australia' in place else 'New Zealand' if 'New Zealand' in place else 'South Africa' if 'South Africa' in place else 'Lesotho','explicit birthplace in wholly southern country or named region'
 if re.search(r'England|Scotland|Wales|United Kingdom|\bU\.?K\.?\b|United States|Canada|Romania|Hungary|Netherlands|Germany|Austria|Egypt|Russia|Texas|India|Bavaria|Scotland',place,re.I):return 'north','','explicit named northern country or region'
 if place in {'Montréal','Saint-Lin','London','Harpenden, Hertfordshire','Folkestone, Kent','Shaftesbury, Dorset','Clyde coast, Scotland','Bavaria'}:return 'north','','named locality with northern geographic resolution'
 return 'unknown','','geography requires explicit disambiguation'
rows=[]
for r in csv.DictReader(source.open(encoding='utf-8-sig')):
 rid=r['cohort_key'];old=existing[rid]
 rec={'cohort':'UK_Royal_Society','record_id':rid,'name':r['display_name'],'dob':r['exact_dob'],'raw_birthplace':'','source_url':'','evidence_quote':'','birthplace_source_grade':'unknown','hemisphere':'unknown','country':'','reason':'no explicit target-person birthplace found','original_DOB_or_flags_modified':False}
 meta=OUT/'cache'/(rid+'.json');http=json.loads(meta.read_text()) if meta.exists() else {}
 txt=(OUT/'cache'/(rid+'.txt'));flat=re.sub(r'\s+',' ',txt.read_text()) if txt.exists() else ''
 place=quote='';method=''
 u=r['provenance_source_url'];host=urlparse(u).netloc
 if rid in manual and flat:
  p,q=manual[rid]
  if q.lower() in flat.lower():place,quote,method=p,q,'target_person_specific_body_passage_reviewed'
 if not place and 'eoas.info' in host:
  m=re.search(rf'\bBorn\s+({DATE})\s+(.*?)(?=\s+Occupation\b|\s+Summary\b|\s+Died\b)',flat,re.I)
  if m:place=m.group(2).strip();quote=m.group(0);method='explicit_EOAS_Born_field'
 if not place and 'mathshistory' in host:
  m=re.search(rf'Quick Info\s+Born\s+({DATE})\s+(.*?)\s+(?:Summary|Died)\b',flat,re.I)
  if m:place=m.group(2).strip();quote=m.group(0).rsplit(' ',1)[0];method='explicit_MacTutor_QuickInfo_Born_field'
 if not place and ('nobelprize.org' in host or rid=='RS_CURRENT_14128'):
  m=re.search(rf'\bBorn:\s+({DATE}),\s+(.*?)(?=\s+Affiliation\b|\s+Died:)',flat,re.I)
  if m:place=m.group(2).strip();quote=m.group(0);method='explicit_Nobel_Born_field'
 if not place and 'prixduquebec' in host:
  m=re.search(r'Naissance le\s+.*?\d{4}\s+à\s+(.+?)\s*,\s*décès',flat,re.I)
  if m:place=m.group(1).strip();quote=m.group(0).rsplit(',',1)[0];method='explicit_Quebec_Naissance_field'
 if place:
  sign,country,why=geo(place,old);rec.update(raw_birthplace=place,source_url=u,evidence_quote=quote,birthplace_source_grade=grade(u),hemisphere=sign,country=country,reason=why,evidence_kind=method,source_sha256=http.get('source_sha256',''),retrieved_utc=http.get('retrieved_utc',''),body_read_this_round=True)
 elif old.get('raw_birthplace'):
  rec.update(raw_birthplace=old['raw_birthplace'],source_url=old['birthplace_source_url'],evidence_quote=old.get('birthplace_claim_excerpt',''),birthplace_source_grade='S1_or_S2_existing_body_metadata_not_reopened',hemisphere=old['hemisphere'],country=old.get('country',''),reason='reused_existing_explicit_birthplace_evidence',evidence_kind=old.get('birthplace_evidence_kind',''),body_read_this_round=False)
 if not rec['raw_birthplace']:
  second_meta=OUT/'royal_cache'/(rid+'.json');second_text=OUT/'royal_cache'/(rid+'.txt')
  if second_meta.exists() and second_text.exists():
   second=json.loads(second_meta.read_text());body=re.sub(r'\s+',' ',second_text.read_text());p=q='';kind=''
   m=re.search(rf'\bBorn:\s+({DATE}),\s+(.*?)(?=\s+Affiliation\b|\s+Died:)',body,re.I)
   if m:p=m.group(2).strip();q=m.group(0);kind='explicit_Nobel_Born_field_second_source'
   if rid=='RS_CURRENT_10607' and 'Bavarian-born engineer' in body:p='Bavaria';q='Professor Sir Ralf Speth is a Bavarian-born engineer';kind='explicit_RoyalSociety_adjectival_birthplace'
   if rid=='RS_CURRENT_12862' and 'Jim Dunlop was born and raised on the Clyde coast.' in body:p='Clyde coast, Scotland';q='Jim Dunlop was born and raised on the Clyde coast.';kind='explicit_RoyalSociety_born_clause_region'
   if p:
    sign,country,why=geo(p,old);rec.update(raw_birthplace=p,source_url=second['original_url'],evidence_quote=q,birthplace_source_grade='S1',hemisphere=sign,country=country,reason=why,evidence_kind=kind,source_sha256=second.get('source_sha256',''),retrieved_utc=second.get('retrieved_utc',''),body_read_this_round=True)
 if rid=='RS_CURRENT_11226':
  rec['birthplace_correction_recommended']=True;rec['correction_note']='Existing EOAS explicit Born field confirms Camden NSW Australia; prior Wikidata P19 Linkoping Sweden is contradicted. Keep raw S3 claim; no DOB or native acceptance change.'
 rec['http_error']=http.get('error','')
 rows.append(rec)
assert len(rows)==99 and len({r['record_id'] for r in rows})==99
(OUT/'current99_birthplace_rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
print(json.dumps({'rows':len(rows),'counts':dict(Counter(r['hemisphere'] for r in rows)),'explicit_places':sum(bool(r['raw_birthplace']) for r in rows)},ensure_ascii=False))
for r in rows:
 if not r['raw_birthplace']:print('MISSING',r['record_id'],r['name'])
