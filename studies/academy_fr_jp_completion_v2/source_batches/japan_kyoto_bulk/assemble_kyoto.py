#!/usr/bin/env python3
"""Offline extraction and guarded name/specialty assignment of Kyoto archive facts."""
from pathlib import Path
import csv,json,re,hashlib,datetime,collections
from collect_kyoto import txt,read_candidates,norm,BASE
ROOT=Path(__file__).resolve().parent
POLICY_URL=BASE+'files/pdf/legend.pdf'
PAIR_REJECTIONS={('jpa-unlinked-a8fc2a0b9c3ac0d3','000707'):'Same Japanese name, different person: candidate metallurgy; Kyoto000707 medicine/anatomy. Correct candidate match is000706.',('jpa-unlinked-363d031907d26f0c','000706'):'Same Japanese name, different person: candidate anatomy/embryology; Kyoto000706 metallurgy. Correct candidate match is000707.'}
def field(body,name):
 m=re.search(r'<th[^>]*>\s*'+re.escape(name)+r'\s*</th>\s*<td[^>]*>(.*?)</td>',body,re.S)
 return txt(m.group(1)) if m else ''
def datevalue(raw):
 if not raw:return 'missing','','','','',''
 m=re.fullmatch(r'(\d{4})/(\d{1,2})(?:/(\d{1,2}))?',raw)
 if not m:return 'unparsed','','','','',''
 y,mo,dy=m.groups();y=int(y);mo=int(mo);dy=int(dy) if dy else None
 assert 1<=mo<=12
 if dy:
  assert 1<=dy<=31
  # Do not Gregorian-validate lunar dates; no calendar conversion occurs.
  if y>=1873:datetime.date(y,mo,dy)
 precision='day' if dy else 'month'
 val=f'{y:04d}-{mo:02d}'+(f'-{dy:02d}' if dy else '')
 calendar='lunar_explicit_by_database_legend' if y<=1872 else 'western_calendar_from_database_policy'
 return precision,str(y),str(mo),str(dy) if dy else '',val,calendar
def writecsv(name,rows):
 with (ROOT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['member_key']);w.writeheader();w.writerows(rows)
def main():
 matches=json.loads((ROOT/'candidate_index_matches.json').read_text());claims=[];reject=[]
 for k in matches:
  p=ROOT/'private'/('detail_'+k['kyoto_id']+'.html');data=p.read_bytes();body=data.decode();name=field(body,'氏名');assert norm(name)==norm(k['name_jp']),(name,k['name_jp'])
  source_url=BASE+'?c=detail&id='+k['kyoto_id'];pair=(k['member_key'],k['kyoto_id'])
  if pair in PAIR_REJECTIONS:
   reject.append({'member_key':pair[0],'name_jp':k['name_jp'],'candidate_specialty':k['specialty_jp'],'rejected_kyoto_id':pair[1],'source_url':source_url,'source_department':field(body,'部局等'),'source_death_raw':field(body,'死去'),'reason':PAIR_REJECTIONS[pair]});continue
  raw=field(body,'生年月日');precision,y,mo,dy,val,cal=datevalue(raw);death=field(body,'死去');dp,_,_,_,death_iso,_=datevalue(death)
  official_retirement=k.get('final_retirement_date','');death_comp='exact_match' if death_iso and death_iso==official_retirement else 'different_values_not_assumed_equivalent_events' if death_iso and official_retirement else 'not_comparable'
  specialty=field(body,'専門');department=field(body,'部局等')
  evidence=f"Exact compact Japanese name; Kyoto department: {department}; archive specialty: {specialty or '(not recorded)'}; candidate specialty: {k['specialty_jp'] or '(not recorded)'}; archive death: {death or '(not recorded)'}; academy final retirement: {official_retirement or '(not recorded)'}."
  identity_status='name_and_matching_archive_death_academy_retirement_support' if death_comp=='exact_match' else 'name_professional_context_support_requires_crosscheck'
  quality='birthyear_conflict_with_NDL1872_and_Morioka1872' if k['kyoto_id']=='000583' else 'no_new_conflict_adjudicated_in_this_batch'
  claims.append({'member_key':k['member_key'],'name_jp':k['name_jp'],'candidate_input_scope':k['candidate_input_scope'],'source_name':name,'source_url':source_url,'kyoto_id':k['kyoto_id'],'source_tier':'university_archive_employer_records_database','source_department':department,'source_specialty':specialty,'source_birth_raw':raw,'birth_precision':precision,'birth_year_component':y,'birth_month_component':mo,'birth_day_component':dy,'birth_iso_components':val,'calendar':cal,'calendar_policy_url':POLICY_URL,'gregorian_dob':val if precision=='day' and cal=='western_calendar_from_database_policy' else '','source_death_raw':death,'official_final_retirement_raw':official_retirement,'death_retirement_comparison':death_comp,'identity_evidence':evidence,'identity_evidence_status':identity_status,'source_quality_status':quality,'identity_accepted':False,'final_cohort_accepted':False,'bazi_computed':False,'source_capture_sha256':hashlib.sha256(data).hexdigest(),'retrieved_at':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat()})
 writecsv('claims.csv',claims);writecsv('rejected_pairs.csv',reject)
 coverage=[]
 for c in read_candidates():
  cm=[x for x in claims if x['member_key']==c['member_key']];coverage.append({'member_key':c['member_key'],'name_jp':c['name_jp'],'candidate_input_scope':c['candidate_input_scope'],'index_exact_name_matches':sum(x['member_key']==c['member_key'] for x in matches),'nonrejected_source_records':len(cm),'birth_precision':cm[0]['birth_precision'] if cm else 'no_database_match','calendar':cm[0]['calendar'] if cm else '','source_quality_status':cm[0]['source_quality_status'] if cm else '','final_cohort_accepted':False})
 writecsv('candidate_coverage.csv',coverage)
 policy={'source_url':POLICY_URL,'source_quote':'明治5年以前の太陰暦については、年表記のみを西暦に直した。','policy_interpretation':'1872 and earlier entries retain lunar month/day with a westernized year number; do not treat the formatted date as Gregorian.1873+ western calendar dates follow the stated database policy. No conversion by collector.','source_scope':'Kyoto presidents, professors, associate professors in office on/before1949-05-30; archival personnel records generally preferred over conflicting external sources.','calendar_conversion_performed':False}
 (ROOT/'calendar_policy.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2))
 summary={'input_candidates':475,'restored_candidate_input':435,'legacy_qualification_input':40,'index_records':1025,'name_match_pairs':len(matches),'rejected_same_name_different_person_pairs':len(reject),'nonrejected_source_records':len(claims),'distinct_nonrejected_candidates':len({x['member_key'] for x in claims}),'precision_counts':dict(collections.Counter(x['birth_precision'] for x in claims)),'calendar_counts':dict(collections.Counter(x['calendar'] for x in claims)),'source_scope_counts':{scope:{'candidates':sum(x['candidate_input_scope']==scope for x in claims),'precision_counts':dict(collections.Counter(x['birth_precision'] for x in claims if x['candidate_input_scope']==scope)),'western_day':sum(x['candidate_input_scope']==scope and bool(x['gregorian_dob']) for x in claims)} for scope in ['restored435','legacy40']},'literal_january1_values_not_collector_padding':sum(x['birth_month_component']=='1' and x['birth_day_component']=='1' for x in claims),'name_death_retirement_supported_records':sum(x['death_retirement_comparison']=='exact_match' for x in claims),'birthyear_conflicts_retained':1,'unmatched_candidates':sum(x['nonrejected_source_records']==0 for x in coverage),'global_DOB_missing_count':None,'identity_accepted':0,'final_cohort_accepted':0,'bazi_computed':0,'limitation':'Source-supported candidate facts, not a frozen national academy cohort or independently verified civil DOB. Archive death and academy retirement are different event types; differing values alone are not identity rejection or a DOB conflict. All lunar expressions retained without conversion.'}
 (ROOT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
