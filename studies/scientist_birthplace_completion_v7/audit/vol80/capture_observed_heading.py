from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,urllib.request,re
P=Path(__file__).parent;now=lambda:datetime.now(timezone.utc).isoformat();html=(P/'raw_transient/chapter_20.html').read_text();url='https://nap.nationalacademies.org/books/10269/gif/349.gif';assert url in re.findall(r'(?:data-original|src)=[\"\']([^\"\']+)',html)
intent={'utc':now(),'kind':'observed_page_image','url':url,'chapter':20,'printed_page':349,'purpose':'Distinguish HTML text-layer1915 header from printed source; no date correction or native field adoption. Single read under existing8body cap.'}
with (P/'intent_ledger.jsonl').open('a') as f:f.write(json.dumps(intent)+'\n');f.flush()
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
 data=r.read();meta={'url':url,'final_url':r.url,'status':r.status,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'retrieved_utc':now(),'kind':'original_page_image_GIF','observed_href_in_chapter_original_SHA':hashlib.sha256((P/'raw_transient/chapter_20.html').read_bytes()).hexdigest()}
(P/'raw_transient/chapter_20_page_349.gif').write_bytes(data);(P/'chapter_20_page_349_capture.json').write_text(json.dumps(meta,indent=2))
from PIL import Image
Image.open(P/'raw_transient/chapter_20_page_349.gif').save(P/'raw_transient/chapter_20_page_349.png')
print(json.dumps(meta))
