from pathlib import Path
import hashlib,json,zipfile
root=Path('/workspace/scratch/7e8aa4e0d4af');s=root/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v6'
files=sorted(p for p in s.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='MANIFEST.sha256')
(s/'MANIFEST.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(s))+'\n' for p in files))
files.append(s/'MANIFEST.sha256');files.sort()
zip_path=root/'scientist_birthplace_completion_v6.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files:z.write(p,'scientist_birthplace_completion_v6/'+str(p.relative_to(s)))
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(files)
 for l in (s/'MANIFEST.sha256').read_text().splitlines():
  h,name=l.split('  ',1);assert hashlib.sha256(z.read('scientist_birthplace_completion_v6/'+name)).hexdigest()==h
metadata=[]
for p in files:
 data=p.read_bytes();metadata.append({'path':str(p.relative_to(root/'uk_birthplace_checkout')),'local':str(p),'size':len(data),'sha':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),'sha256':hashlib.sha256(data).hexdigest()})
(root/'academy_v6_workers/git_files.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'files':len(files),'file_bytes':sum(x['size'] for x in metadata),'master_sha256':hashlib.sha256((s/'outputs/birthplace_rows.jsonl.gz').read_bytes()).hexdigest(),'ZIP':str(zip_path),'ZIP_bytes':zip_path.stat().st_size,'ZIP_sha256':hashlib.sha256(zip_path.read_bytes()).hexdigest(),'CRC_and_MANIFEST':'PASS'},indent=2))
