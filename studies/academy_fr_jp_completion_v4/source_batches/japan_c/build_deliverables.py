import csv, datetime, hashlib, json, pathlib, re
P=pathlib.Path(__file__).resolve().parent
BASE=P.parent.parent/'academy_completion_checkout/studies/academy_fr_jp_completion_v3/outputs'
q=list(csv.DictReader((P.parent/'queues/japan_3.csv').open()))
master=list(csv.DictReader((BASE/'japan_master.csv').open()))
obs=json.loads((P/'observations.json').read_text())
caps=json.loads((P/'source_capture_log.json').read_text()); capmap={x['source_url']:x for x in caps}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def claim(o,r,bulk=False):
    c=capmap.get(o['url'],{}); y,m,d=o['date'];pre=not o['calendar_comparable']
    x=dict(member_key=r['member_key'],name_jp=r['name_jp'],year=y,month=m,day=d,
      precision='day' if d is not None else ('month' if m is not None else 'year'),
      calendar=o['calendar'],calendar_comparable=o['calendar_comparable'],body_verified=True,identity_body_supported=True,
      source_url=o['url'],source_tier='edited_reference' if o['layer']=='secondary' else 'institution_or_university',
      source_subtier=('official_corporate_cv' if o.get('i')==15 else ('publisher_dictionary' if o['layer']=='secondary' else 'official_institution_body')),
      publisher=o['publisher'],book=o['book'],raw_birth_statement=o['raw'],identity_support=o['identity'],
      source_sha256=c.get('source_sha256'),retrieved_utc=c.get('retrieved_utc',now),source_location=o['loc'],
      calendar_note=o.get('note',''),body_verification_route=o.get('ref','local_original_pdf_body'),
      cohort_accepted=False,bazi_variables_computed=False,
      evidence_status='claim_calendar_hold' if pre else 'body_birth_claim',
      selected=False,selection_note='Candidate evidence only; no final cohort or DOB freeze.',
      source_body_redistributed=False)
    x['claim_id']=hashlib.sha256((x['member_key']+'|'+x['source_url']+'|'+x['book']+'|'+str(y)+'|'+str(m)+'|'+str(d)+'|'+x['calendar']).encode()).hexdigest()[:20]
    return x
institution=[claim(o,q[o['i']]) for o in obs if o['layer']=='institution']
secondary=[claim(o,q[o['i']]) for o in obs if o['layer']=='secondary']
(P/'claims.json').write_text(json.dumps(institution,ensure_ascii=False,indent=2))
(P/'secondary_claims.json').write_text(json.dumps(secondary,ensure_ascii=False,indent=2))
holds=[]
for x in institution+secondary:
    if not x['calendar_comparable']:
        holds.append(dict(member_key=x['member_key'],name_jp=x['name_jp'],claim_id=x['claim_id'],hold_type='pre1873_era_calendar_unspecified',hold_scope='claim',global_member_hold=False,note='No lunar conversion or Gregorian selection; year-only parenthesis or identical month/day in Western digits is insufficient.'))
failure={
 12:('bounded_no_acceptable_body_candidate','Exact-name one-query results had NDL year-only metadata and unrelated modern namesake; NDL bulk was already screened in prior rounds. No new date accepted.'),
 17:('bounded_no_acceptable_body_candidate','Exact-name one-query results principally unrelated mechanical engineer 松岡信 (d2011 aged87), not the plant-breeding academy member. No false identity match.'),
 28:('body_capture_failed','Nagasaki institutional commemorative PDF lead not accepted: web file-size limit, direct HTTP redirect loop. No snippet-based birth claim.'),
 33:('body_capture_failed','Open University PDF lead not accepted: web429/direct503. Direct Kotobank 名取礼二 fallback path inaccessible. No snippet-based year or date accepted.')}
processed=[]
for i,r in enumerate(q):
    oo=[o for o in obs if o['i']==i];cc=[x for x in institution+secondary if x['member_key']==r['member_key']]
    if oo:
        o=oo[0];status=('body_'+cc[0]['precision']+'_'+o['layer']) if o['calendar_comparable'] else 'body_day_claim_calendar_hold'
        note=o.get('note','')
    else:status,note=failure[i];holds.append(dict(member_key=r['member_key'],name_jp=r['name_jp'],hold_type=status,hold_scope='search_outcome',global_member_hold=False,note=note))
    processed.append(dict(member_key=r['member_key'],name_jp=r['name_jp'],specialty_jp=r['specialty_jp'],baseline_dob_status=r['dob_status'],query='"'+r['name_jp'].replace(' ','')+'" '+('歯学 ' if i==27 else '神経 ' if i==36 else '')+'生年月日',query_engine='system2',query_count=1,screened=True,outcome=status,new_claim_count=len(cc),claim_ids=json.dumps([x['claim_id'] for x in cc],ensure_ascii=False),body_source_urls=json.dumps([x['source_url'] for x in cc],ensure_ascii=False),note=note,cohort_accepted=False,bazi_variables_computed=False))
with (P/'processed.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(processed[0]));w.writeheader();w.writerows(processed)
inv=json.loads((P/'bulk_sendai_inventory.json').read_text())
bulkdefs={
 '本多光太郎':([1870,2,23],2,'明治3年2月23日','東京帝国大学卒、KS鋼発見、東北帝国大学鉄鋼研究所長・総長、物性磁性・物理冶金。'),
 '村上武次郎':([1882,11,10],7,'明治15年11月10日','物理冶金・特殊鋼研究、村上試薬、東北大学金属材料研究所長、日本金属学会会長、文化勲章。'),
 '増本量':([1895,1,9],9,'明治28年1月9日','物理冶金・磁性材料、超不変鋼とセンダスト、東北大学金属材料研究所長、日本金属学会会長。'),
 '野副鉄男':([1902,5,16],10,'明治35年5月16日','有機化学者、ヒノキチオール・トロポロン合成、東北大学教授・名誉教授、文化勲章。'),
 '西澤潤一':([1926,9,12],17,'大正15年9月12日','東北大学工学部卒・教授・総長、半導体光通信・光ファイバー・電子工学、文化勲章。'),
 '岩崎俊一':([1926,8,3],23,'大正15年8月3日','東北大学工学部卒・電気通信研究所長、東北工業大学長、垂直磁気記録研究、文化勲章。'),
 '熊谷岱蔵':([1880,7,19],5,'明治13年7月19日','東北帝国大学総長・抗酸菌病研究所長、結核臨床とBCG研究、文化勲章。'),
 '志賀潔':([1870,12,18],3,'明治3年12月18日','細菌学者、東京帝国大学医学卒、志賀赤痢菌発見、京城帝国大学総長、文化勲章。'),
 '黒川利雄':([1897,1,15],13,'明治30年1月15日','東北大学医学卒・学長、日本学士院院長、消化器病・胃癌集団検診、文化勲章。'),
 '阿部次郎':([1883,8,27],8,'明治16年8月27日','東北帝国大学法文学部長・名誉教授、三太郎の日記著者、思想・文学研究、1947帝国学士院会員。')}
bulk=[]
for h in inv['matches']:
    n=re.sub(r'\s','',h['name_jp']);date,page,raw,identity=bulkdefs[n];pre=date[0]<1873
    o=dict(layer='institution',date=date,calendar='japanese_era_pre1873_unspecified' if pre else 'japanese_era_post1873',calendar_comparable=not pre,raw='生年月日 '+raw,url=inv['source_url'],publisher='仙台市',book='仙台市名誉市民',identity=identity,loc=f'Printed p{page+1}/PDFindex{page}, labelled 生年月日 and career',ref='private_reused_original_pdf',note='Pre-1873 source era expression retained as a noncomparable claim only; existing source-supplied modern claim is not downgraded.' if pre else 'Existing 482-row roster only. No inference about academy section or final membership scope.')
    x=claim(o,h,True);x['source_sha256']=inv['source_sha256'];x['retrieved_utc']='2026-10-29T11:56:46.626067+00:00';x['capture_reuse_note']='Original captured in earlier institutional batch; same-hash redundant GET occurred once in v4 uniform capture script and is logged.';bulk.append(x)
    if pre:holds.append(dict(member_key=x['member_key'],name_jp=x['name_jp'],claim_id=x['claim_id'],hold_type='pre1873_era_calendar_unspecified',hold_scope='claim',global_member_hold=False,note='Historical era expression only. Do not mark a birth conflict against source-supplied modern calendar dates or downgrade that existing evidence.'))
    h.update(source_birth_precision='day',calendar_comparable=not pre,claim_id=x['claim_id'],detailed_pdf_page=page+1,existing_membership_scope_unchanged=True)
(P/'bulk_sendai_claims.json').write_text(json.dumps(bulk,ensure_ascii=False,indent=2))
(P/'bulk_sendai_inventory.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2))
(P/'holds.json').write_text(json.dumps(holds,ensure_ascii=False,indent=2))
summary=dict(worker='japan_c',baseline='academy_fr_jp_completion_v3',assigned_queue_rows=40,processed_queue_rows=len(processed),single_query_screened=40,unprocessed_queue_rows=0,institution_claims=len(institution),institution_day_claims=sum(x['precision']=='day' for x in institution),institution_month_claims=sum(x['precision']=='month' for x in institution),institution_year_claims=sum(x['precision']=='year' for x in institution),secondary_claims=len(secondary),secondary_day_claims=len(secondary),secondary_calendar_comparable_day_claims=sum(x['calendar_comparable'] for x in secondary),queue_calendar_comparable_day_people=sum(x['precision']=='day' and x['calendar_comparable'] for x in institution+secondary),queue_calendar_held_day_people=3,queue_no_new_birth_claim_people=4,bulk_sendai_roster_screened=482,bulk_sendai_matched_people=len(bulk),bulk_sendai_day_claims=len(bulk),bulk_sendai_calendar_comparable_day_claims=sum(x['calendar_comparable'] for x in bulk),bulk_sendai_new_body_day_people_vs_v3=['熊谷岱蔵','阿部次郎'],bulk_sendai_extra_person_not_in_queue=['阿部次郎'],source_date_conflict_holds=0,claim_only_calendar_holds=5,original_source_capture_urls=len(caps),valid_original_source_capture_urls=sum(x['valid_original_body_captured'] for x in caps),no_bazi_variables_computed=True,final_cohort_acceptances=0,final_dob_freeze=False,note='Do not sum bulk and queue claims as unique people: 熊谷岱蔵 appears in both. Secondary stays a separate layer. All candidate DOB rows selected=false.')
(P/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
assert len(q)==40 and len(processed)==40 and len({r['member_key'] for r in processed})==40
assert len(obs)==36 and len(institution)==10 and len(secondary)==26
assert all(x['body_verified'] and x['identity_body_supported'] for x in institution+secondary+bulk)
assert all(x['source_sha256'] for x in institution+secondary+bulk)
assert all(not x['bazi_variables_computed'] and not x['cohort_accepted'] for x in institution+secondary+bulk)
print(json.dumps(summary,ensure_ascii=False,indent=2))
