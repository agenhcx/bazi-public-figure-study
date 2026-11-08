#!/usr/bin/env python3
"""Replay the France continuation from pinned decisions; no network and no analyses."""
from pathlib import Path
import argparse,csv,json,io,hashlib,re,datetime
R=Path(__file__).resolve().parent
FLAGS=['identity_accepted','membership_accepted','dob_accepted','bazi_computed']
def readcsv(p):
 with p.open(encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f);return list(r),r.fieldnames

def writecsv(p,rows,fields):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def counts(rs):
 return {k:sum(x[k]=='1' for x in rs) for k in FLAGS}|{'all_three_accepted':sum(all(x[k]=='1' for k in FLAGS[:3]) for x in rs)}
def build(out):
 manifest=json.loads((R/'inputs/MANIFEST.json').read_text())
 for entry in manifest['files']:
  p=R/'inputs'/entry['path'];assert p.stat().st_size==entry['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],entry['path']
 base,fields=readcsv(R/'inputs/baseline_master877.csv');s=json.loads((R/'inputs/baseline_summary39.json').read_text());prior=json.loads((R/'inputs/prior_case_dimensions704.json').read_text());new=json.loads((R/'inputs/new_case_decisions57.json').read_text());old_updates=json.loads((R/'inputs/old_membership_updates.json').read_text());source=json.loads((R/'inputs/source_provenance.json').read_text())
 assert len(base)==877 and len(prior)==704 and len(new)==57 and len({x['candidate_group_id'] for x in base})==877
 assert counts(base)==dict(identity_accepted=698,membership_accepted=184,dob_accepted=688,bazi_computed=0,all_three_accepted=183)
 by={x['candidate_group_id']:dict(x) for x in base};oldby={x['candidate_group_id']:x for x in prior};assert len(oldby)==704
 newby={x['candidate_group_id']:x for x in new};assert len(newby)==57 and not(newby.keys()&oldby.keys())
 extra=['membership_role_supported','election_cutoff_stable','election_date_conflict','election_cutoff_note','completion_case_id','completion_status','completion_remaining_dimensions','source_evidence_review_version','accepted_election_precision']
 for x in by.values():
  x.update(dict.fromkeys(extra,''));x['source_evidence_review_version']='France_877_continuation_20261029'
  x['accepted_election_precision']='day' if re.fullmatch(r'\d{4}-\d{2}-\d{2}',x['accepted_full_member_election_date']) else ('year' if x['accepted_full_member_election_year'] else '')
  if x['membership_accepted']=='1':x['membership_role_supported']='1';x['election_cutoff_stable']='1'
  c=oldby.get(x['candidate_group_id']);me=c.get('membership_evidence',{}) if c else {}
  ordinary=any(me.get(k) is True for k in ['ordinary_full_role_explicit','ordinary_full_qualified','ordinary_full_role_explicit_in_Academy_original'])
  if c and x['identity_accepted']=='1' and ordinary:
   x['membership_role_supported']='1'
   if me.get('within2025_cutoff') is True:x['election_cutoff_stable']='1'
  if c and (me.get('known_event_or_role_conflict_in_supplied_material') is True or 'conflict' in str(me.get('status','')) or me.get('election_after_birth') is False):
   x['election_date_conflict']='1';x['election_cutoff_note']='Inherited source/event conflict retained; no conflict chosen by source count.'
 for cid,c in newby.items():
  x=by[cid];assert c['independent_QA_approved'] is True and c['identity_accepted']==1 and c['bazi_computed']==0
  x['identity_accepted']=str(c['identity_accepted']);x['membership_accepted']=str(c['membership_accepted']);x['dob_accepted']=str(c['dob_accepted'])
  x['accepted_canonical_person_name']=c['name'];x['accepted_dob_iso']=c.get('accepted_dob_iso') or '';x['accepted_full_member_election_date']=c.get('accepted_full_member_election_date') or '';x['accepted_full_member_election_year']=str(c.get('accepted_full_member_election_year') or '')
  x['completion_case_id']=c['case_id'];x['adjudication_case_id']=c['case_id'];x['membership_role_supported']=str(c.get('membership_role_supported',''))
  x['election_cutoff_stable']=str(c.get('election_cutoff_stable',''));x['election_date_conflict']=str(c.get('election_date_conflict',''));x['election_cutoff_note']=c.get('election_cutoff_note','');x['accepted_election_precision']=c.get('accepted_full_member_election_precision') or ''
  if x['dob_accepted']=='1':assert datetime.date.fromisoformat(x['accepted_dob_iso']) and x['accepted_dob_iso'] in x['exact_dob_claims'].split('|')
  if x['membership_accepted']=='1':assert c['membership_role_supported']==1 and c['election_cutoff_stable']==1 and not c.get('election_date_conflict')
 for c in old_updates:
  x=by[c['candidate_group_id']];assert x['identity_accepted']=='1' and c['independent_QA_approved'] is True
  x['membership_role_supported']='1';x['election_cutoff_stable']=str(c.get('election_cutoff_stable',''));x['election_date_conflict']=str(c.get('election_date_conflict',''));x['election_cutoff_note']=c.get('election_cutoff_note','');x['completion_case_id']=c['case_id']
  if c.get('membership_accepted')==1:
   assert not c.get('election_date_conflict') and c['election_cutoff_stable']==1
   x['membership_accepted']='1';x['accepted_full_member_election_date']=c.get('accepted_full_member_election_date') or '';x['accepted_full_member_election_year']=str(c.get('accepted_full_member_election_year') or '');x['accepted_election_precision']=c.get('accepted_full_member_election_precision') or ''
  else:assert x['membership_accepted']=='0'
 for x in by.values():
  missing=[k.replace('_accepted','') for k in FLAGS[:3] if x[k]!='1'];x['completion_remaining_dimensions']='|'.join(missing)
  x['completion_status']='accepted_all_three' if not missing else ('reviewed_with_holds' if x['adjudication_case_id'] else 'unreviewed_or_parked')
  assert x['bazi_computed']=='0'
 # Historical DOB and identity holds can never be lifted merely by a membership overlay.
 for orig in base:
  cid=orig['candidate_group_id'];cur=by[cid]
  if cid not in newby:
   assert cur['identity_accepted']==orig['identity_accepted'] and cur['dob_accepted']==orig['dob_accepted']
   assert cur['accepted_dob_iso']==orig['accepted_dob_iso']
   for k in fields:
    if k not in ['membership_accepted','accepted_full_member_election_date','accepted_full_member_election_year']:
     assert cur[k]==orig[k],(cid,k)
 rows=[by[x['candidate_group_id']] for x in base];accepted=[x for x in rows if x['completion_status']=='accepted_all_three'];gaps=[x for x in rows if x['completion_status']!='accepted_all_three']
 out.mkdir(parents=True,exist_ok=True);writecsv(out/'france_candidate_master877.csv',rows,fields+extra);writecsv(out/'france_accepted_all_three.csv',accepted,fields+extra);writecsv(out/'france_remaining_gaps.csv',gaps,fields+extra)
 external=json.loads((R/'inputs/external_case_updates_santy_abragam.json').read_text())
 exclusion=[];corroboration=[]
 for rec in external['records']:
  if rec['cths_person_id']=='110681':
   assert not any('110681' in x['cths_person_ids'].split('|') or x['candidate_group_id']=='CTHS_110681' for x in rows)
   assert rec['case_disposition']=='EXCLUDE_FROM_PRIMARY_FULL_MEMBER_CANDIDATE_LAYER'
   exclusion.append({'cths_person_id':'110681','name':'Paul Santy','present_in_master877':'0','firstparty_role':'CORRESPONDENT_AT_DEATH','source_url':rec['source_url'],'source_locator':rec['page_locator'],'disposition':rec['case_disposition'],'DOB_conflict_resolved':'0','DOB_claims_retained':'1887-04-16|1887-04-18','candidate_reintroduction_blocked':'1'})
  elif rec['cths_person_id']=='111758':
   abr=by['CTHS_111758'];assert abr['dob_accepted']=='1' and abr['membership_accepted']=='0'
   corroboration.append({'candidate_group_id':'CTHS_111758','name':'Anatole Abragam','dob_accepted_after':'1','membership_accepted_after':'0','corroborating_DOB':'1914-12-15','source_url':rec['source_url'],'ordinary_foreign_role_conflict_resolved':'0','note':'Employer corroboration preserved; no new ordinary-member acceptance.'})
 writecsv(out/'france_external_case_exclusions.csv',exclusion,list(exclusion[0]))
 writecsv(out/'france_existing_case_corroboration.csv',corroboration,list(corroboration[0]))
 summary={'scope':'877 restored candidate groups, not a complete verified national roster','date':'2026-10-29','baseline_round':39,'baseline':counts(base),'current':counts(rows),'increment':{k:counts(rows)[k]-counts(base)[k] for k in counts(base)},'new_candidates_reviewed':57,'cumulative_case_reviewed':761,'old_membership_cases_revisited':len(old_updates),'role_supported_groups':sum(x['membership_role_supported']=='1' for x in rows),'cutoff_stable_groups':sum(x['election_cutoff_stable']=='1' for x in rows),'date_conflict_flagged_groups':sum(x['election_date_conflict']=='1' for x in rows),'all_three_remaining_gaps':len(gaps),'historical_day_source_claim_coverage_unchanged':804,'raw_missing_day_claim_groups_unchanged':73,'exact_DOB_conflict_groups_unchanged':3,'old_identity_holds_unchanged':12,'old_unreviewed_primary_queue_after57':15,'old_deferred_priority18_unchanged':18,'bazi_computed':0,'analysis_cohort_frozen':False,'collection_complete':False,'limits':'Incomplete candidate and membership census; all-three gaps include member-role evidence, identity and DOB holds. Exact DOB evidence approvals are not equivalent to accepted ordinary members or a national birth-date denominator. New role/cutoff/date-conflict columns are separate evidence dimensions and do not relax historical strict membership acceptance.'}
 summary['external_Santy_exclusion_explicitly_preserved']=True
 summary['Santy_present_in_restored877']=False
 summary['Abragam_CEA_corroboration_retained_membership_still_held']=True
 dump(out/'summary.json',summary)
 hashes=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file() and p.name!='MANIFEST.json'];dump(out/'MANIFEST.json',{'files':hashes})
 return summary
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--output-dir',required=True,type=Path);args=a.parse_args();print(json.dumps(build(args.output_dir),ensure_ascii=False,indent=2))
