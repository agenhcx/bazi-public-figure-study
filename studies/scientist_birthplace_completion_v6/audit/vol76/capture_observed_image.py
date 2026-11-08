import pathlib,json,sys,datetime,urllib.request,hashlib
B=pathlib.Path('academy_v6_workers/vol76');ch=int(sys.argv[1]);page=sys.argv[2];imgs=json.loads((B/f'raw_transient/chapter_{ch}_observed_images.json').read_text());matches=[i for i in imgs if i.get('alt')=='Page '+page];assert len(matches)==1;url=matches[0]['data-original'];ledger=[json.loads(x) for x in (B/'retained/intents.jsonl').read_text().splitlines()];n=sum(x['operation']=='chapter_body' for x in ledger);assert n<12;assert not any(x.get('url')==url for x in ledger)
intent={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'operation':'chapter_body','ordinal':n+1,'capture_form':'observed_source_page_image','url':url,'purpose':'Read genuinely observed chapter page image because chapter HTML contains no prose; counts against total12bodyrequests','url_provenance':f'chapter_{ch}.html img data-original for Page {page}','retry_authorized':False}
with (B/'retained/intents.jsonl').open('a') as f:f.write(json.dumps(intent)+'\n')
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as r:
  b=r.read();raw=B/f'raw_transient/chapter_{ch}_page_{page}.gif';raw.write_bytes(b);meta={'request_url':url,'final_url':r.url,'status':r.status,'public_headers':{k:v for k,v in r.headers.items() if k.lower() in ['content-type','content-length','date','etag','last-modified']},'capture_kind':'original_http_response_bytes_page_image','captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'raw_file':str(raw),'scope':f'original source image printed page {page}, chapter {ch}'}
 (B/f'retained/chapter_{ch}_page_{page}_capture.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta))
 from PIL import Image
 Image.open(raw).save(B/f'raw_transient/chapter_{ch}_page_{page}.png')
except Exception as e:
 err={'request_url':url,'error':str(e),'type':type(e).__name__,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'no_retry':True};(B/f'retained/chapter_{ch}_page_{page}_capture.json').write_text(json.dumps(err,indent=2));print(err)
