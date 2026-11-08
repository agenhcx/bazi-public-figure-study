"""Offline exact-collector guard tests. urllib/socket network I/O is forbidden."""
from pathlib import Path
from unittest import mock
import contextlib,csv,datetime,gzip,hashlib,io,json,runpy,socket,tempfile,urllib.error,email.message
O=Path(__file__).parent;SOURCE=O/'fetch_batch.py';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();source_sha=sha(SOURCE);cases=[];socket_calls=[]
def denied(*a,**k):socket_calls.append(1);raise AssertionError('Network forbidden')
def setup(root):
 target=root/'uk_birthplace_v6_workers/pending53/fetch_batch.py';target.parent.mkdir(parents=True);target.write_bytes(SOURCE.read_bytes())
 study=root/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v5';(study/'outputs').mkdir(parents=True);(study/'audit').mkdir()
 rows=[{'record_id':f'TEST_{i}','dob':'1900-01-01','hemisphere':'unknown','birthplace_evidence_candidates':[]} for i in range(53)]
 (study/'outputs/uk_birthplace_rows.jsonl.gz').write_bytes(gzip.compress(''.join(json.dumps(x)+'\n' for x in rows).encode()))
 with (study/'audit/pending_search_queue.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['record_id','name','source_authorised_full_name','dob','journal_issn','reason']);w.writeheader()
  for i,r in enumerate(rows):w.writerow({'record_id':r['record_id'],'name':f'Subject {i}','source_authorised_full_name':f'Test; Subject {i} (1900 - 1940)','dob':r['dob'],'journal_issn':'2053-9118' if i<3 else '1748-8494','reason':'synthetic_offline_fixture'})
 return target,target.parent.parent/'CROSSREF_SHARED_STOP.json'
def run(target,sender,sleeper=None):
 with mock.patch('urllib.request.urlopen',side_effect=sender) as calls,mock.patch('socket.create_connection',side_effect=denied),mock.patch.object(socket.socket,'connect',side_effect=denied),contextlib.redirect_stdout(io.StringIO()):
  if sleeper:
   with mock.patch('time.sleep',side_effect=sleeper):runpy.run_path(str(target),run_name='offline_test')
  else:runpy.run_path(str(target),run_name='offline_test')
 return calls.call_count,json.loads((target.parent/'fetch_summary.json').read_text()),[json.loads(l) for l in (target.parent/'crossref_results.jsonl').read_text().splitlines()]
with tempfile.TemporaryDirectory(prefix='v6-stop-offline-') as raw:
 root=Path(raw)
 target,marker=setup(root/'existing');marker.write_text('{"reason":"existing test stop"}')
 n,s,r=run(target,denied);assert n==0 and s['attempted']==0 and s['not_attempted']==53;cases.append({'case':'existing_shared_marker','status':'PASS','fake_urlopen_calls':0,'not_attempted':53})
 target,marker=setup(root/'http429');headers=email.message.Message();headers['Retry-After']='120'
 def fake429(req,*a,**k):raise urllib.error.HTTPError(req.full_url,429,'simulated',headers,io.BytesIO(b'offline429'))
 n,s,r=run(target,fake429);m=json.loads(marker.read_text());assert n==1 and s['attempted']==1 and s['not_attempted']==52 and m['Retry-After']=='120';assert r[0]['journal_issn']=='2053-9118' and all(not x['attempted_this_round'] for x in r[1:]);cases.append({'case':'fake429_captures_retry_after_and_stops_all53_without_switching_journal','status':'PASS','fake_urlopen_calls':1,'not_attempted':52,'Retry-After_captured':'120'})
 target,marker=setup(root/'wait');waits=[]
 class OK:
  status=200;headers={}
  def __enter__(self):return self
  def __exit__(self,*a):return False
  def read(self):return b'{"message":{"items":[]}}'
 def stop_in_wait(delay):waits.append(delay);marker.write_text('{"reason":"stop arrives during interval wait"}')
 n,s,r=run(target,lambda *a,**k:OK(),stop_in_wait);assert n==1 and waits and s['attempted']==1 and s['not_attempted']==52 and s['stop_reason']=='shared_or_local_stop_marker_after_wait';cases.append({'case':'stop_marker_arrives_during_interval_wait_rechecked_before_dispatch','status':'PASS','fake_urlopen_calls':1,'not_attempted':52})
assert not socket_calls and sha(SOURCE)==source_sha
out={'status':'PASS','tested_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':source_sha,'test_script_sha256':sha(Path(__file__)),'real_network_requests':0,'socket_connection_attempts':0,'cases':cases,'scope':'Exact collector byte copies with synthetic53 fixtures; no real API calls or edits to collector as-run.'}
(O/'guard_offline_test_result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
