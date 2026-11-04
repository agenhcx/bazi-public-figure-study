#!/usr/bin/env python3
"""Local independent QA of the two explicitly frozen v5 memoir source lanes."""
from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
from datetime import datetime
from urllib.parse import urljoin,urldefrag
from PIL import Image
import gzip,hashlib,json,re

W=Path('/workspace/scratch/7e8aa4e0d4af');Q=W/'academy_v5_workers/qa'
BASE=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v4/outputs/birthplace_rows.jsonl.gz'
BASE_SHA='abbce4e99ad51252dd5e127a0609bc6c4950c121afa2dd126bfc2187b39cd4e8'
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.suppressed=0;self.parts=[];self.links=[];self.images=[]
 def handle_starttag(self,t,a):
  if t in {'script','style','nav'}:self.suppressed+=1
  if not self.suppressed and t in {'p','div','h1','h2','h3','h4','li','br'}:self.parts.append('\n')
  if t=='a':self.links.extend(v for k,v in a if k=='href')
  if t=='img':self.images.extend(v for k,v in a if k in {'src','data-original'})
 def handle_endtag(self,t):
  if not self.suppressed and t in {'p','div','h1','h2','h3','h4','li'}:self.parts.append('\n')
  if t in {'script','style','nav'}:self.suppressed-=1
 def handle_data(self,s):
  if not self.suppressed:self.parts.append(s)
 def text(self):return re.sub(r'\s+',' ',''.join(self.parts)).strip()
def parsed(p):
 p1=Parser();p1.feed(p.read_text());return p1
def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp(x):return datetime.fromisoformat(x)
def compatible(a,b):
 a=re.findall('[a-z]+',a.lower());b=re.findall('[a-z]+',b.lower())
 match=lambda x,y:x==y or len(x)==1 and x==y[0] or len(y)==1 and y==x[0]
 return match(a[0],b[0]) and match(a[-1],b[-1]) and (len(a)==2 or len(b)==2 or len(a)==len(b) and all(match(x,y) for x,y in zip(a[1:-1],b[1:-1])))
