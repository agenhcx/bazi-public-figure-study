from pathlib import Path
import json,re,html,hashlib,gzip,datetime
O=Path(__file__).parent
rows=json.loads((O/'targets.json').read_text());byid={r['record_id']:r for r in rows}
ledger=[json.loads(l) for l in (O/'request_ledger.jsonl').read_text().splitlines()]
meta={r['title']:r for r in ledger}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s))).strip()
def out(name,rs):(O/name).write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rs))
choices=[('RS_PAST_NA1510','Lindley','physician, born at Lindley on 23 Jan. 1835','Edward Mansfield Brockbank',1,226,'Page:Dictionary of National Biography, Second Supplement, volume 1.djvu/246'),('RS_PAST_NA3559','Falkirk','born on 6 March 1849 at Falkirk','Humphry Davy Rolleston',2,192,'Page:Dictionary of National Biography, Second Supplement, volume 2.djvu/212')]
accepted=[]
for rid,place,quote,author,volume,page,scan in choices:
 b=byid[rid];p=O/'raw'/f'{rid}.json';d=json.loads(p.read_bytes());body=d['parse']['text'];txt=clean(body)
 assert quote in txt and len(quote.split())<=25
 title=d['parse']['title'];m=meta[title];assert sha(p)==m['source_sha256']
 # Transclusion metadata records provenance; no image/facsimile was visually read.
 assert scan in html.unescape(body)
 r={'record_id':rid,'name':b['name'],'native_dob':b['dob'],'dob':b['dob'],'source_authorised_full_name':b['source_authorised_full_name'],
 'raw_birthplace':place,'source_grade':'S3','birthplace_source_grade':'S3',
 'source_grade_basis':'Editable Wikisource transcription of an edited DNB article; original page scan not read, so no S2 claim',
 'source_url':'https://en.wikisource.org/wiki/'+title.replace(' ','_'),'source_urls':['https://en.wikisource.org/wiki/'+title.replace(' ','_')],
 'source_author':author,'source_title':title,'source_book':'Dictionary of National Biography, Second Supplement (1912)','source_volume':volume,'source_printed_page':page,
 'scan_transclusion_title':scan,'scan_visually_verified':False,'transclusion_page_quality_observed':1,
 'evidence_quote':quote,'evidence_locator':'parse.text; first named-subject paragraph, explicit born clause',
 'source_capture_kind':'Original Wikisource parse API HTTP JSON; SHA of full retrieved bytes, not a scan hash','source_sha256':m['source_sha256'],'raw_source_file':str(p.relative_to(O)),
 'request_url':m['request_url'],'retrieved_utc':m['request_started_utc'],'article_title':title,'article_pageid':d['parse'].get('pageid'),
 'identity_verified':True,'identity_review':'Manual official full name, same lifespan, named subject, and exact printed birthday match native DOB; father clauses kept separate',
 'birthplace_anchor_links':[],'DOB_or_native_acceptance_modified':False,'article_DOB_not_used_to_update_native':True,'geography_not_newly_assigned':True,'birth_country_or_birthpoint_assigned':False,
 'review_note':'No geographic expansion from father residence, schooling, professional affiliation or nationality. Original birthplace token retained.'}
 accepted.append(r)
out('accepted.jsonl',accepted)
coverage=[]
for b in rows:
 r={'record_id':b['record_id'],'native_dob':b['dob'],'official_full_name':b['source_authorised_full_name'],'original_hemisphere':b['hemisphere'],'original_raw_birthplace':b.get('raw_birthplace',''),'attempted_article_body':b['record_id'] in {a['record_id'] for a in accepted},'decision':'accepted_S3_transcription_birthplace' if b['record_id'] in {a['record_id'] for a in accepted} else 'held','hold_reason':'' if b['record_id'] in {a['record_id'] for a in accepted} else 'not_covered_by_bounded_available_index_match; no claim of absence from original printed DNB','DOB_or_flags_modified':False}
 coverage.append(r)
out('coverage.jsonl',coverage);out('held.jsonl',[r for r in coverage if r['decision']=='held'])
summary={'schema':'UK_v8_bounded_historical_DNB_transcription','frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_rows':4983,'target_window_unknown_death_pre1932':len(rows),
 'web_discovery_queries':5,'direct_API_requests':4,'article_body_requests':2,'index_API_requests':2,'direct_API_HTTP_status_counts':{'200':4},'retries':0,'HTTP429':0,
 'direct_API_request_note':'index_links.json (three verified1912 volume titles in one API call, continuation not followed); index1927 parse; two article parses. Only bounded available indices examined, not a full DNB census.',
 'accepted':len(accepted),'accepted_source_grade_counts':{'S3':len(accepted)},'held_target_rows':len(rows)-len(accepted),'raw_birthplace_or_native_modified':False,
 'geography_assigned':False,'scan_images_fetched_or_read':0,'original_edited_book_metadata_retained_but_not_S2_verified':True,
 'input_base_sha256':sha(Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_checkout/studies/royal_society_birthplace_completion_v7/outputs/uk_birthplace_rows.jsonl.gz')),
 'output_sha256':{n:sha(O/n) for n in ['accepted.jsonl','coverage.jsonl','held.jsonl']}}
(O/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(O/'verification.json').write_text(json.dumps({'status':'PASS','accepted':2,'native_DOB_copied_unchanged':True,'source_SHA_verified':True,'exact_quote_max25words':True,'named_subject_birth_clause_reviewed':True,'no_scan_read_no_grade_upgrade':True,'no_geography_or_birthcountry_or_birthpoint_assigned':True},indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
