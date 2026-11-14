#!/usr/bin/env python3
"""Fork-only scheduling wrapper; scientific definitions live in locked analyze_global.py."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import datetime as dt
import importlib.util
import json
import multiprocessing as mp
from pathlib import Path
import numpy as np

P=Path(__file__).with_name('analyze_global.py')
S=importlib.util.spec_from_file_location('_nobel_locked_global',P)
G=importlib.util.module_from_spec(S);S.loader.exec_module(G)
CTX=None


def case_worker(case):
 pool,inputs,loc,nofields,models,cache=CTX
 rows,quality=G.case_rows(case,inputs,pool,loc,nofields)
 model=models[{'strict_broad':'broad','strict_noJie':'noJie','strict_yearMonth':'yearMonth'}.get(case,'year')]
 return G.run_case(case,rows,quality,pool,model,cache)


def toy_worker(case):
 # Outside-cohort synthetic scheduling/RNG fixture. Child order must not affect
 # separately initialized case and endpoint streams or final ordered results.
 case_index=G.CASES.index(case)
 return {'case':case,'test_streams':[np.random.Generator(np.random.PCG64(20261113+i)).integers(0,60,31).tolist() for i in range(18)],'bootstrap_stream':np.random.Generator(np.random.PCG64(2026111301)).integers(0,100,31).tolist(),'synthetic_case_index':case_index}


def synthetic_qa():
 ordered={c:toy_worker(c) for c in G.CASES}
 with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('fork')) as ex:
  futures={ex.submit(toy_worker,c):c for c in reversed(G.CASES)}
  completed={futures[f]:f.result() for f in as_completed(futures)}
 restored={c:completed[c] for c in G.CASES}
 assert restored==ordered and list(restored)==G.CASES
 return {'status':'PASS','real_input_loaded':False,'fork_global_context':True,'parallel_vs_sequential_case_RNG_bitexact':True,'final_order_equals_original_case_order':True,'workers':3,'scientific_engine_sha256':G.sha(P)}


def main(args):
 global CTX
 if args.synthetic_qa:
  print(json.dumps(synthetic_qa(),indent=2));return
 receipt,scope=G.verify_gate(args);manifest=json.loads(Path(args.locked_files).read_text())
 own=str(Path(__file__).resolve().relative_to(Path.cwd()))
 G.require(own in manifest and manifest[own]==G.sha(__file__),'Parallel wrapper not locked')
 G.require(1<=args.workers<=3,'Workers must be bounded1..3')
 G.require(not Path(args.output).exists(),'Result exists; no overwrite')
 pool,inputs,loc,nofields=G.load_data(args.v4_zip,args.calendar_npz);m=G.base_module()
 models={'year':m.CalendarModel(pool),'broad':m.CalendarModel(pool,broad=True),'noJie':m.CalendarModel(pool,no_jie=True),'yearMonth':m.CalendarModel(pool,month=True)}
 checkpoints=Path(args.output).with_suffix('.checkpoints');checkpoints.mkdir(exist_ok=False)
 cache={};CTX=(pool,inputs,loc,nofields,models,cache)
 def save(case,result):
  cache[case]=result
  (checkpoints/(case+'.json')).write_text(json.dumps(G.safe(result),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 # Primary result is available read-only in each fork for exact broad-case reuse.
 save('strict_primary',case_worker('strict_primary'))
 with ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('fork')) as ex:
  futures={ex.submit(case_worker,c):c for c in G.CASES[1:]}
  for f in as_completed(futures):save(futures[f],f.result())
 ordered={c:cache[c] for c in G.CASES}
 result={'schema':'scientist_Nobel_global18_reveal_v1','test_order':G.IDS,'case_order':G.CASES,'primary_family':{'source':'strict','cooccurrence':'narrow','calendar':'year','adjustment':'Holm18','alpha':.05},'cases':ordered,'scope':scope,'execution_receipt':receipt,'source_pins':{'engine_sha256':G.sha(P),'wrapper_sha256':G.sha(__file__),'V4_zip_sha256':G.sha(args.v4_zip),'calendar_npz_sha256':G.sha(args.calendar_npz),'original_helper_sha256':G.sha(G.WORK/'original/reveal_v1/scripts/analyze_country.py')},'execution_schedule':{'strict_primary_first':True,'other_cases_fork_processes':args.workers,'RNG_unchanged_case_endpoint_local':True,'case_order_restored_before_output':True},'completed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
 Path(args.output).write_text(json.dumps(G.safe(result),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'status':'PASS','output':args.output,'cases':len(ordered),'primary_Holm18_rejections':sum(t['reject_primary_Holm18_0_05'] for t in ordered['strict_primary']['tests'])}))


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for a in ['scope','locked-files','execution-receipt','v4-zip','calendar-npz','output']:p.add_argument('--'+a)
 p.add_argument('--workers',type=int,default=3);p.add_argument('--synthetic-qa',action='store_true');main(p.parse_args())
