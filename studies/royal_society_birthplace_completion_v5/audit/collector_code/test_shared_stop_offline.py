"""Run the exact patched collector in isolated scratch copies with all I/O network mocked.

No real URL opener or socket connection is permitted. The as-run collector is
read-only and never executed. Test fixtures use three synthetic records.
"""
from pathlib import Path
from unittest import mock
import contextlib,datetime,hashlib,io,json,runpy,socket,tempfile,urllib.error

O=Path(__file__).resolve().parent
SOURCE=O/'fetch_batch.py'
AS_RUN=O/'fetch_batch_as_run.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_sha=sha(SOURCE);as_run_sha=sha(AS_RUN)
audit=json.loads((O/'collector_code_audit.json').read_text())
assert source_sha==audit['patched_not_run_sha256']
assert as_run_sha==audit['as_run_sha256']
fixtures=[{'record_id':f'TEST_{i}','dob':'1900-01-01','source_authorised_full_name':f'Test; Subject {i} (1900 - 1940)','full_name':f'Subject {i} Test','birthyear':'1900','deathyear':'1940','memoir_query':f'Subject {i} Test 1900 1940'} for i in range(3)]
results=[];real_network_attempts=[]
def forbidden_socket(*args,**kwargs):
    real_network_attempts.append('forbidden_socket_connect_attempt')
    raise AssertionError('Real network is forbidden in this offline test')
def fixture(root,name):
    dest=root/name;dest.mkdir()
    target=dest/'fetch_batch.py';target.write_bytes(SOURCE.read_bytes())
    assert sha(target)==source_sha
    (dest/'cohort.json').write_text(json.dumps(fixtures))
    return dest,target

def execute(target,opener):
    # Both urllib and sockets are guarded for a meaningful no-network guarantee.
    with mock.patch('urllib.request.urlopen',side_effect=opener) as patched, \
         mock.patch('socket.create_connection',side_effect=forbidden_socket), \
         mock.patch.object(socket.socket,'connect',side_effect=forbidden_socket), \
         contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(str(target),run_name='offline_guard_test')
    rows=[json.loads(l) for l in (target.parent/'crossref_results.jsonl').read_text().splitlines()]
    return patched.call_count,rows,json.loads((target.parent/'fetch_summary.json').read_text())

with tempfile.TemporaryDirectory(prefix='crossref-stop-offline-') as raw:
    root=Path(raw)
    # Shared stop already present before a worker starts: no URL calls at all.
    shared=root/'CROSSREF_SHARED_STOP.json';shared.write_text(json.dumps({'reason':'offline fixture existing shared stop'}))
    folder,target=fixture(root,'already_shared_stopped')
    def fail_if_urlopen(*args,**kwargs):raise AssertionError('urlopen called despite existing marker')
    calls,rows,summary=execute(target,fail_if_urlopen)
    assert calls==0 and len(rows)==3 and all(r['attempted_this_round'] is False for r in rows)
    assert summary['attempted']==0
    results.append({'case':'shared_marker_already_exists','status':'PASS','fake_urlopen_calls':calls,'not_attempted_rows':len(rows)})
    shared.unlink()
    # A local external stop marker is also recognized before network dispatch.
    folder,target=fixture(root,'already_locally_stopped');(folder/'shared_429_stop.json').write_text('{}')
    calls,rows,summary=execute(target,fail_if_urlopen)
    assert calls==0 and all(r['attempted_this_round'] is False for r in rows)
    results.append({'case':'local_marker_already_exists','status':'PASS','fake_urlopen_calls':calls,'not_attempted_rows':len(rows)})
    # Simulate HTTP429 in exactly one fake opener. The remaining queued records
    # must be held, and the worker must persist the shared marker for peers.
    folder,target=fixture(root,'first_fake_429')
    def fake_429(req,*args,**kwargs):raise urllib.error.HTTPError(req.full_url,429,'offline simulated Too Many Requests',None,None)
    calls,rows,summary=execute(target,fake_429)
    assert calls==1 and shared.exists() and summary['HTTP429_stop'] is True
    attempted=[r for r in rows if r['attempted_this_round']]
    assert len(attempted)==1 and attempted[0]['http_status']==429
    assert len([r for r in rows if not r['attempted_this_round']])==2
    marker=json.loads(shared.read_text());assert marker['record_id']==attempted[0]['record_id']
    results.append({'case':'fake_429_writes_shared_marker_and_stops_queue','status':'PASS','fake_urlopen_calls':calls,'attempted_rows':1,'not_attempted_rows':2,'shared_marker_created':True})
    # A fresh peer worker has its own Event/lock and observes only the shared
    # marker written by the first worker; it too must make zero URL calls.
    folder,target=fixture(root,'peer_after_shared_429')
    calls,rows,summary=execute(target,fail_if_urlopen)
    assert calls==0 and summary['attempted']==0 and all(r['attempted_this_round'] is False for r in rows)
    results.append({'case':'fresh_peer_observes_previous_worker_429_marker','status':'PASS','fake_urlopen_calls':calls,'not_attempted_rows':len(rows)})
    # Inject an external marker during the rate-gate interval wait. This checks
    # the second marker read immediately before dispatch, rather than relying
    # only on the queue-entry guard.
    shared.unlink();folder,target=fixture(root,'marker_arrives_during_interval_wait')
    class Fake200:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self):return b'{"message":{"items":[]}}'
    interval_waits=[]
    def inject_marker_during_sleep(delay):
        interval_waits.append(delay);shared.write_text('{"reason":"offline external stop during interval wait"}')
    with mock.patch('time.sleep',side_effect=inject_marker_during_sleep):
        calls,rows,summary=execute(target,lambda *args,**kwargs:Fake200())
    assert calls==1 and interval_waits and all(delay>0 for delay in interval_waits)
    assert sum(r['attempted_this_round'] for r in rows)==1
    assert any(r.get('error')=='not_attempted_shared_Crossref429' for r in rows)
    results.append({'case':'shared_marker_arrives_during_gate_wait','status':'PASS','fake_urlopen_calls':calls,'attempted_rows':1,'not_attempted_rows':2,'external_stop_rechecked_after_interval':True})
assert not real_network_attempts
assert sha(SOURCE)==source_sha and sha(AS_RUN)==as_run_sha
output={'status':'PASS','tested_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'test_type':'Exact patched collector bytes copied into isolated temporary fixtures and executed with urllib opener and socket connections mocked','patched_collector_sha256':source_sha,'as_run_collector_sha256_unchanged':as_run_sha,'test_script_sha256':sha(Path(__file__).resolve()),'real_network_requests':0,'socket_connection_attempts':0,'cases':results,'scope_limit':'These offline tests exercise existing shared/local markers, a simulated HTTP429, queued work, fresh peer recognition and an external stop arriving during the interval gate wait. They do not claim the earlier as-run process stopped correctly or validate live service behavior.'}
(O/'shared_stop_offline_test_result.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
