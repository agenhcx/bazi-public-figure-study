#!/usr/bin/env python3
"""Keep-alive transport for the frozen catalogue birthplace field parser."""
from __future__ import annotations
import argparse, asyncio, csv, json, re, time
from collections import Counter
from email.utils import parsedate_to_datetime
from pathlib import Path
import aiohttp
import collect_royal_society_birthplace as parser


class AsyncRateLimiter:
    def __init__(self, rate):
        self.interval = 1 / rate
        self.next_time = 0.0
        self.not_before = 0.0
        self.lock = asyncio.Lock()
    async def wait(self):
        async with self.lock:
            delay = max(self.next_time, self.not_before) - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self.next_time = time.monotonic() + self.interval
    async def pause(self, seconds):
        async with self.lock:
            self.not_before = max(self.not_before, time.monotonic() + seconds)


async def collect(row, out, session, limiter, retries):
    rid = row['record_id']
    assert re.fullmatch(r'NA\d+', rid)
    raw_file = out / 'raw_html' / (rid + '.html')
    meta_file = out / 'response_metadata' / (rid + '.json')
    rec = {'cohort':'UK_Royal_Society','record_id':row['cohort_key'],'archive_id':rid,
           'name':row['display_name'],'existing_dob':row['dob_exact_iso'],
           'source_url':row['source_url'],'http_status':'','final_url':'','retrieved_utc':'',
           'source_sha256':'','source_bytes':0,'raw_placeofbirth':'','parse_status':'not_attempted',
           'error':'','birthplace_source_grade':'S1','DOB_or_acceptance_modified':False}
    raw = None
    if raw_file.exists() and meta_file.exists():
        try:
            meta=json.loads(meta_file.read_text());candidate=raw_file.read_bytes()
            if meta.get('source_url')==row['source_url'] and parser.digest(candidate)==meta.get('source_sha256'):
                raw=candidate
                rec.update({k:meta[k] for k in ['http_status','final_url','retrieved_utc','source_sha256','source_bytes']})
                rec['cache_reused']=True
        except (OSError,ValueError,KeyError):
            pass
    if raw is None:
        for attempt in range(retries+1):
            await limiter.wait()
            try:
                async with session.get(row['source_url']) as response:
                    rec['http_status']=response.status
                    if response.status==200:
                        raw=await response.read()
                        rec.update(final_url=str(response.url),retrieved_utc=parser.now(),
                                   source_sha256=parser.digest(raw),source_bytes=len(raw),cache_reused=False)
                        raw_file.write_bytes(raw)
                        parser.write_json(meta_file,{k:rec[k] for k in ['source_url','http_status','final_url','retrieved_utc','source_sha256','source_bytes']})
                        break
                    rec['error']='HTTPError:'+str(response.status)
                    if response.status not in {408,429,500,502,503,504}:
                        break
                    value=response.headers.get('Retry-After')
                    if value:
                        try:delay=float(value)
                        except ValueError:
                            try:delay=max(0,parsedate_to_datetime(value).timestamp()-time.time())
                            except (ValueError,TypeError,OverflowError):delay=5
                        if delay>60:
                            rec['error']+=':retry_after_deferred';break
                        await limiter.pause(delay)
                    await response.read()
            except (aiohttp.ClientError,asyncio.TimeoutError,OSError) as exc:
                rec['error']=type(exc).__name__+':'+str(exc)[:220]
            if attempt<retries:
                await asyncio.sleep(min(2**(attempt+1),12))
    if raw is None:
        rec['parse_status']='network_failure'
    else:
        rec['error']='';rec.update(parser.parse(raw));rec['raw_source_file']=str(raw_file.relative_to(out))
        if rec['parse_status']=='expected_person_record_fields_absent':
            rec['error']='HTTP_200_without_expected_person_catalogue_record'
    return rec


async def run(args):
    with args.baseline.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==4884 and len({r['cohort_key'] for r in rows})==4884
    for r in rows:assert r['dob_precision']=='exact_day' and r['dob_exact_iso']
    if args.priority_csv:
        with args.priority_csv.open(encoding='utf-8-sig',newline='') as stream:prior={r['record_id']:r for r in csv.DictReader(stream)}
        def key(r):
            x=prior.get(r['cohort_key'],{});sign=x.get('hemisphere','unknown')
            conflict=str(x.get('geographic_conflict_pending_review','')).lower() in {'true','1'}
            return (0 if sign=='unknown' or conflict else 1 if sign=='south' else 2,r['cohort_key'])
        rows.sort(key=key)
    if args.limit:rows=rows[:args.limit]
    out=args.output
    for folder in ['raw_html','response_metadata']:(out/folder).mkdir(parents=True,exist_ok=True)
    limiter=AsyncRateLimiter(args.rate);semaphore=asyncio.Semaphore(args.workers)
    started=parser.now();clock=time.monotonic();results=[]
    connector=aiohttp.TCPConnector(limit=args.workers,limit_per_host=args.workers)
    async with aiohttp.ClientSession(trust_env=True,timeout=aiohttp.ClientTimeout(total=args.timeout),
                                   connector=connector,headers={'User-Agent':parser.UA,'Accept':'text/html,application/xhtml+xml'}) as session:
        async def one(row):
            async with semaphore:return await collect(row,out,session,limiter,args.retries)
        tasks=[asyncio.create_task(one(r)) for r in rows]
        try:
            with (out/'official_birthplace_progress.jsonl').open('w') as progress:
                for future in asyncio.as_completed(tasks):
                    rec=await future;results.append(rec)
                    progress.write(json.dumps(rec,ensure_ascii=False,sort_keys=True)+'\n');progress.flush()
                    n=len(results)
                    if n%50==0 or n==len(rows):
                        elapsed=time.monotonic()-clock;network=sum(not r.get('cache_reused',False) for r in results)
                        status={'started_utc':started,'updated_utc':parser.now(),'completed':n,'total':len(rows),
                                'with_birthplace':sum(bool(r['raw_placeofbirth']) for r in results),
                                'errors':sum(bool(r['error']) for r in results),'elapsed_seconds':round(elapsed,2),
                                'network_results':network,'effective_network_results_per_second':round(network/elapsed,3),
                                'parse_status_counts':dict(Counter(r['parse_status'] for r in results)),
                                'transport':'aiohttp_keepalive','workers':args.workers,'shared_requests_per_second':args.rate}
                        parser.write_json(out/'checkpoint.json',status)
                        if n%200==0 or n==len(rows):print(json.dumps(status),flush=True)
        finally:
            for task in tasks:
                if not task.done():task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
    results.sort(key=lambda r:r['record_id'])
    assert len(results)==len(rows) and len({r['record_id'] for r in results})==len(rows)
    target=out/'official_birthplace_rows.jsonl'
    target.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in results))
    summary={'schema':'royal_society_official_birthplace_fields_v2','started_utc':started,'completed_utc':parser.now(),
             'baseline_csv_sha256':parser.digest(args.baseline.read_bytes()),'script_sha256':parser.digest(Path(__file__).read_bytes()),
             'parser_script_sha256':parser.digest(Path(parser.__file__).read_bytes()),'output_sha256':parser.digest(target.read_bytes()),
             'rows':len(results),'birthplace_nonempty':sum(bool(r['raw_placeofbirth']) for r in results),
             'network_failure':sum(r['parse_status']=='network_failure' for r in results),'errors':sum(bool(r['error']) for r in results),
             'parse_status_counts':dict(Counter(r['parse_status'] for r in results)),'workers':args.workers,
             'shared_requests_per_second':args.rate,'transport':'aiohttp_keepalive','elapsed_seconds':round(time.monotonic()-clock,2),
             'DOB_or_acceptance_modified':False,'rule':'Only exact Place of birth table field; no nationality/death/career inference.'}
    parser.write_json(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--priority-csv',type=Path);ap.add_argument('--workers',type=int,default=32)
    ap.add_argument('--rate','--rps',dest='rate',type=float,default=3);ap.add_argument('--timeout',type=float,default=25)
    ap.add_argument('--retries',type=int,default=2);ap.add_argument('--limit',type=int,default=0)
    args=ap.parse_args()
    if not 1<=args.workers<=32 or not 0<args.rate<=3:raise SystemExit('Workers<=32; global request start rate<=3/s')
    asyncio.run(run(args))

if __name__=='__main__':main()
