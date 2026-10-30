#!/usr/bin/env python3
"""Run the same bounded NDL collector in a separate 40-candidate scope."""
from pathlib import Path
import sys,json,csv,hashlib
import collect_ndl
root=Path(__file__).resolve().parent
collect_ndl.ROOT=root/'remaining40'
collect_ndl.ROOT.mkdir(exist_ok=True)
if '--input' not in sys.argv:
 sys.argv.extend(['--input',str(collect_ndl.project_root()/'data/academy_jobs_japan_inputs_v1/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv')])
collect_ndl.main()
# Qualification overlays are inherited, not newly adjudicated by this DOB pass.
status={'jpa-unlinked-67412ee03b08c5d2':'inherited_broad_section_ii','jpa-unlinked-ff84801ab056cf46':'inherited_section_i_exclusion','jpa-unlinked-6b0513d4d49815ad':'inherited_section_i_exclusion','jpa-unlinked-f21fcc61cad96158':'inherited_section_i_exclusion'}
for name in ['claims','candidate_matches']:
 p=collect_ndl.ROOT/(name+'.csv');r=list(csv.DictReader(p.open()))
 for x in r:x['qualification_status']=status.get(x['member_key'],'qualification_unresolved');x['science_cohort_accepted']=False
 with (root/(name+'40.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(r[0]));w.writeheader();w.writerows(r)
s=json.loads((collect_ndl.ROOT/'summary.json').read_text());s['scope']='40 old qualification queue, disjoint from restored 435 candidates';s['inherited_qualification_counts']={'broad_section_ii':1,'section_i_excluded':3,'unresolved':36};s['this_pass_new_qualification_decisions']=0
(root/'summary40.json').write_text(json.dumps(s,ensure_ascii=False,indent=2))
(root/'request_log40.json').write_bytes((collect_ndl.ROOT/'request_log.json').read_bytes())
