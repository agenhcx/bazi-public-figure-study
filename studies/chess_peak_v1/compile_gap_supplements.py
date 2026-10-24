"""Compile exact original-list bridges for explicitly unavailable API windows.

This offline compiler neither requests network data nor inspects associations.
The source ZIP cache must already have been downloaded and fingerprinted.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata
import zipfile

from collect_fide import CUTOFF, load_roster, parse_provider

PROTOCOL = 'chess-peak-official-list-supplement-v1'
PRIMARY = 'fide_official_list_archive'
HISTORICAL = 'olimpbase_transcription'
MONTHS = ('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec')
HISTORICAL_SHA = '41131d4b573f033ccf8f2df927f820046cfbee305051b83145c2955220d89003'
HISTORICAL_URL = 'https://www.olimpbase.org/Elo/data/elo2002-2009.zip'
KNOWN_NAMES = {
    '3901211': ('Iturrizaga, Eduardo', 'Iturrizaga Bonelli, Eduardo'),
    '4101685': ('Landa, Konstantin',),
    '4600010': ('Huebner, Robert', 'Huebner, Robert, Dr.'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def normalize_name(value):
    value = unicodedata.normalize('NFKD', value)
    return ''.join(c for c in value.lower() if c.isalpha() and not unicodedata.combining(c))


def expected_periods(first_api_month):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', first_api_month):
        raise ValueError('Invalid first API month')
    result = []
    for year in range(2010, int(first_api_month[:4]) + 1):
        months = (1,3,5,7,9,11) if year < 2012 else (1,3,5,7,8,9,10,11,12) if year == 2012 else range(1,13)
        result.extend(f'{year:04d}-{month:02d}' for month in months if f'{year:04d}-{month:02d}' < first_api_month)
    return result


def eligible_entry(entry):
    audit = entry.get('source_coverage_audit')
    return (entry.get('status') == 'history_acquired_requires_snapshot_audit'
        and isinstance(audit, dict) and audit.get('unresolved') is True
        and entry.get('source_provider') in ('lichess_fide_history', 'fide_official_chart')
        and not entry.get('snapshot_disagreement'))


def safe_file(base, name):
    base = Path(base).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base) or path == base:
        raise ValueError('Evidence path escapes acquisition root')
    return path


def api_evidence(base, person, entry):
    """Bind retained rows to original sealed raw, metadata and normalized bytes."""
    cid, provider = person['canonical_id'], entry['source_provider']
    for key in ('canonical_id','role','name','exact_dob_frozen','snapshot','snapshot_elo','wikidata_person_qids'):
        if entry.get(key) != person[key]:
            raise ValueError('Gap bridge changed a frozen person field')
    if not eligible_entry(entry):
        raise ValueError('Gap bridge is restricted to explicit unresolved coverage')
    evidence = [x for x in entry['source_coverage_audit']['sources']
        if x['source_provider'] == provider and x['raw_sha256'] == entry['raw_sha256']]
    if len(evidence) != 1:
        raise ValueError('No unique preferred API evidence')
    e = evidence[0]
    compressed = safe_file(base,e['raw_file']).read_bytes()
    raw = gzip.decompress(compressed)
    metadata_bytes = safe_file(base,e['metadata_file']).read_bytes()
    if (digest(compressed) != e['gzip_sha256'] or digest(raw) != e['raw_sha256']
        or digest(metadata_bytes) != e['metadata_sha256']):
        raise ValueError('API evidence fingerprint differs')
    metadata = json.loads(metadata_bytes)
    if (metadata.get('canonical_id') != cid or metadata.get('source_provider') != provider
        or metadata.get('source_url') != entry['source_url'] or metadata.get('raw_sha256') != digest(raw)):
        raise ValueError('API source identity differs')
    normalized_path = entry['normalized_history_file']
    normalized_bytes = safe_file(base,normalized_path).read_bytes()
    if digest(normalized_bytes) != entry['normalized_history_sha256']:
        raise ValueError('Original normalized history fingerprint differs')
    normalized = json.loads(normalized_bytes)
    if (normalized.get('canonical_id') != cid or normalized.get('source_provider') != provider
        or normalized.get('source_raw_sha256') != digest(raw)):
        raise ValueError('Normalized API identity differs')
    parsed = parse_provider(raw,cid,provider,snapshot=person['snapshot'])['all_standard_history']
    if normalized['standard_history'] != parsed:
        raise ValueError('Normalized history differs from independently parsed API bytes')
    all_rows = normalized['standard_history']
    raw_value = json.loads(raw.decode('utf-8-sig'))
    raw_indices = {}
    if provider == 'lichess_fide_history':
        for index, value in enumerate(raw_value['standard']):
            stamp,rating = divmod(value,10000)
            month = f'{stamp//100:04d}-{stamp%100:02d}'
            raw_indices.setdefault((month,rating),(index,value))
    retained=[]
    for index,row in enumerate(all_rows):
        if row['month'] > CUTOFF:
            continue
        item={**row,'source':provider,'source_url':entry['source_url'],
              'source_raw_sha256':digest(raw),'api_history_point_index':index}
        if provider == 'lichess_fide_history' and row.get('source_point') is True and not row.get('derived_state'):
            raw_index,packed=raw_indices[(row['month'],row['standard_elo'])]
            item.update(api_raw_point_index=raw_index,api_raw_packed_value=packed)
        retained.append(item)
    if not retained:
        raise ValueError('No API points through the cutoff')
    primary_points=[x for x in all_rows if not x.get('derived_state')]
    first=min(x['month'] for x in primary_points)
    original_entry=safe_file(base,f'entries/{cid}.json').read_bytes()
    proof={'source_provider':provider,'source_url':entry['source_url'],
        'raw_file':e['raw_file'],'raw_sha256':e['raw_sha256'],'gzip_sha256':e['gzip_sha256'],
        'metadata_file':e['metadata_file'],'metadata_sha256':e['metadata_sha256'],
        'original_normalized_file':normalized_path,'normalized_file':f'list-supplements/evidence/{cid}.api-normalized.json',
        'normalized_sha256':digest(normalized_bytes),'original_entry_file':f'entries/{cid}.json',
        'entry_file':f'list-supplements/evidence/{cid}.api-entry.json','entry_sha256':digest(original_entry),
        'first_period':first,'last_available_period':max(x['month'] for x in primary_points),
        'retained_through_cutoff_n':len(retained),'excluded_future_point_n':len(all_rows)-len(retained),
        'api_index_convention':'zero_based_original_normalized_standard_history',
        'original_source_coverage_audit':entry['source_coverage_audit']}
    return retained,proof


def archive_index(cache_dirs):
    index={}
    for folder in cache_dirs:
        for path in sorted(Path(folder).glob('*.metadata.json')):
            m=read_json(path)
            if m.get('status') != 200:
                continue
            url=m.get('url',m.get('requested_url'))
            match=re.fullmatch(r'https://ratings\.fide\.com/download/(?:standard_)?([a-z]{3})(\d{2})frl\.zip',str(url))
            if not match or match[1] not in MONTHS:
                continue
            month=f'{2000+int(match[2]):04d}-{MONTHS.index(match[1])+1:02d}'
            file=path.parent/url.rsplit('/',1)[-1]
            if not file.is_file():
                continue
            raw=file.read_bytes()
            if digest(raw) != m.get('sha256') or len(raw) != m.get('bytes'):
                raise ValueError('Official archive cache fingerprint differs')
            if month in index and index[month]['sha256'] != digest(raw):
                raise ValueError('Multiple different official archives for one period')
            index[month]={'path':file,'source_url':url,'sha256':digest(raw),'bytes':len(raw)}
    return index


def parse_original_line(person,line,header,month,member,line_number,archive):
    cid=person['canonical_id']
    text=line.rstrip('\r\n')
    if not re.match(r'\s*'+re.escape(cid)+r'\s',text):
        raise ValueError('Original list row has another FIDE ID')
    lower=header.lower()
    start=lower.index('name')
    ends=[pos for term in ('titl','fed','country') if (pos:=lower.find(term,start+4))>start]
    if not ends:
        raise ValueError('Unknown original-list name layout')
    source_name=text[start:min(ends)].strip()
    allowed=KNOWN_NAMES.get(cid,(person['name'],))
    if normalize_name(source_name) not in {normalize_name(n) for n in allowed}:
        raise ValueError(f'Unregistered exact source name alias for {cid}: {source_name}')
    numbers=re.findall(r'\b\d+\b',text)
    if numbers[0] != cid or len(numbers)<3 or str(int(person['exact_dob_frozen'][:4])) not in numbers[2:]:
        raise ValueError('Original list birthday or identity differs')
    rating=int(numbers[1])
    if not 0<rating<=3500:
        raise ValueError('Invalid original published rating')
    yr,mo=map(int,month.split('-'))
    filename_token=MONTHS[mo-1]+str(yr)[-2:]
    if filename_token not in member.lower():
        raise ValueError('Official ZIP member period differs')
    full_months=('january','february','march','april','may','june','july','august','september','october','november','december')
    header_match=any(re.search(re.escape(token)+r'\s*'+str(yr)[-2:],header,re.I)
        for token in (MONTHS[mo-1],full_months[mo-1]))
    row={'month':month,'standard_elo':rating,'source_point':True,'source':PRIMARY,
        'source_url':archive['source_url'],'archive_sha256':archive['sha256'],
        'archive_member':member,'source_line_number':line_number,'source_line':text,
        'source_header':header,'source_header_period_mismatch':not header_match,
        'source_name':source_name,'source_birth_year':int(person['exact_dob_frozen'][:4]),
        'identity_anchor':'same_exact_FIDE_ID_and_registered_full_name_alias_and_birthyear',
        'period_evidence':'original_official_download_URL_and_exact_ZIP_member'}
    ledger={'period':month,**{k:row[k] for k in ('source','source_url','archive_sha256','archive_member','source_line_number','source_line')},
        'header':header,'bytes':archive['bytes'],'player_unlisted':False,
        'source_header_period_mismatch':not header_match}
    return row,ledger


def original_rows(index,people,needed):
    rows={cid:[] for cid in people};ledger={cid:[] for cid in people}
    all_needed=sorted({period for periods in needed.values() for period in periods})
    missing=[period for period in all_needed if period not in index]
    if missing:
        raise ValueError('Missing official source archives: '+','.join(missing))
    for month in all_needed:
        archive=index[month];found={cid:[] for cid in people if month in needed[cid]}
        with zipfile.ZipFile(archive['path']) as z:
            for member in z.namelist():
                if not member.lower().endswith('.txt'):
                    continue
                with z.open(member) as stream:
                    header=stream.readline().decode('latin1').rstrip('\r\n')
                    for no,binary in enumerate(stream,2):
                        text=binary.decode('latin1')
                        match=re.match(r'\s*(\d+)\s',text)
                        if match and match[1] in found:
                            found[match[1]].append(parse_original_line(people[match[1]],text,header,month,member,no,archive))
        missing_names={normalize_name(name):cid for cid,matches in found.items() if not matches
            for name in KNOWN_NAMES.get(cid,(people[cid]['name'],))}
        if missing_names:
            with zipfile.ZipFile(archive['path']) as z:
                for candidate_member in z.namelist():
                    if not candidate_member.lower().endswith('.txt'):
                        continue
                    with z.open(candidate_member) as stream:
                        candidate_header=stream.readline().decode('latin1').rstrip('\r\n')
                        name_start=candidate_header.lower().index('name')
                        name_end=min(pos for term in ('titl','fed','country')
                            if (pos:=candidate_header.lower().find(term,name_start+4))>name_start)
                        for binary in stream:
                            candidate_text=binary.decode('latin1')
                            candidate=normalize_name(candidate_text[name_start:name_end].strip())
                            if candidate in missing_names:
                                match=re.match(r'\s*(\d+)\s',candidate_text)
                                other=match[1] if match else 'unknown'
                                raise ValueError(f'Exact registered target name under another FIDE ID requires identity adjudication: {missing_names[candidate]}/{month}/{other}')
        for cid,matches in found.items():
            if len(matches)>1:
                raise ValueError(f'Duplicate original list rows for {cid}/{month}: {len(matches)}')
            if not matches:
                ledger[cid].append({'period':month,'source':PRIMARY,'source_url':archive['source_url'],
                    'archive_sha256':archive['sha256'],'archive_member':member,'header':header,
                    'bytes':archive['bytes'],'player_unlisted':True,'searched_canonical_id':cid,
                    'searched_names':list(KNOWN_NAMES.get(cid,(people[cid]['name'],))),
                    'search_method':'complete_official_ZIP_member_scanned_for_exact_ID_and_registered_full_names; no alternative_identity_assumed',
                    'source_line_number':None,'source_line':None})
            else:
                row,item=matches[0];rows[cid].append(row);ledger[cid].append(item)
    return rows,ledger


def source_dob_discrepancy(value,frozen):
    text=str(value).strip().replace('.','-')
    year=re.match(r'^([12][0-9]{3})(?:$|-)',text)
    if not year:
        return False
    if re.fullmatch(r'[12][0-9]{3}-[0-9]{2}-[0-9]{2}',text) and text[5:7]!='00' and text[8:10]!='00':
        return text!=frozen
    return year[1]!=frozen[:4]


def historical_rows(archive_path,people):
    path=Path(archive_path);raw=path.read_bytes()
    if digest(raw)!=HISTORICAL_SHA:
        raise ValueError('Historical source archive fingerprint differs')
    rows={cid:[] for cid in people};ledger={cid:[] for cid in people}
    with zipfile.ZipFile(path) as z:
        for year in range(2003,2010):
            member=f'{year}.txt'
            with z.open(member) as stream:
                for no,line in enumerate(io.TextIOWrapper(stream,encoding='latin1',newline=''),1):
                    text=line.rstrip('\r\n');f=next(csv.reader([text],delimiter=';'))
                    if len(f)<7 or f[2].strip() not in people:
                        continue
                    cid=f[2].strip();person=people[cid];month=f[1][:4]+'-'+f[1][4:6]
                    if not '2003-07'<=month<='2009-12':
                        continue
                    allowed=KNOWN_NAMES.get(cid,(person['name'],))
                    if normalize_name(f[0]) not in {normalize_name(n) for n in allowed}:
                        raise ValueError(f'Unregistered historical exact-name alias for {cid}: {f[0]}')
                    rating=int(f[6]);assert 0<rating<=3500
                    row={'month':month,'standard_elo':rating,'source_point':True,'source':HISTORICAL,
                        'source_url':HISTORICAL_URL,'archive_sha256':HISTORICAL_SHA,
                        'archive_member':member,'source_line_number':no,'source_line':text,
                        'source_name':f[0],'historical_source_dob_raw':f[3],
                        'historical_source_dob_differs_from_frozen':source_dob_discrepancy(f[3],person['exact_dob_frozen']),
                        'identity_anchor':'same_exact_FIDE_ID_and_registered_full_name; original_list_birthyear_verified',
                        'period_evidence':'YYYYMM_column_of_original_selected_source_row'}
                    rows[cid].append(row)
                    ledger[cid].append({'period':month,**{k:row[k] for k in ('source','source_url','archive_sha256','archive_member','source_line_number','source_line')},
                        'header':'[No header row] semicolon columns: name;YYYYMM;FIDE_ID;DOB;title;federation;rating;delta;games;inactive;...',
                        'source_has_header':False,'bytes':len(raw),'player_unlisted':False})
    return rows,ledger


def source_window_metadata(last_period):
    if not isinstance(last_period,str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',last_period):
        raise ValueError('Invalid observed source-window endpoint')
    reaches=last_period>=CUTOFF
    return {'verified_source_window_end':last_period,'source_window_reaches_cutoff':reaches,
        'source_tail_incomplete':not reaches,'complete_through_cutoff':reaches,
        'complete_through_cutoff_scope':'Source-window endpoint only; no claim of every monthly observation or a complete unobserved career. No point is inferred beyond the last verified source record.'}


def compile_supplements(root,base,cache_dirs,historical_archive,*,canonical_ids=None,output_dir=None):
    root,base=Path(root).resolve(),Path(base).resolve()
    roster={p['canonical_id']:p for p in load_roster(root)[0]}
    candidates={p.stem:read_json(p) for p in sorted((base/'entries').glob('*.json'))}
    chosen={cid:e for cid,e in candidates.items() if eligible_entry(e) and (canonical_ids is None or cid in canonical_ids)}
    if canonical_ids is not None and set(chosen)!=set(canonical_ids):
        raise ValueError('Every requested person must have an explicit unresolved API window')
    if not chosen:
        return []
    people={cid:roster[cid] for cid in chosen}
    api={cid:api_evidence(base,people[cid],entry) for cid,entry in chosen.items()}
    needed={cid:expected_periods(proof['first_period']) for cid,(_,proof) in api.items()}
    for cid,periods in needed.items():
        if people[cid]['snapshot'] not in periods:
            raise ValueError('Frozen snapshot needs an independently downloaded original list witness')
    originals,original_ledger=original_rows(archive_index(cache_dirs),people,needed)
    older,older_ledger=historical_rows(historical_archive,people)
    out=Path(output_dir) if output_dir is not None else root/'studies/chess_peak_v1/supplements'
    out.mkdir(parents=True,exist_ok=True);written=[]
    for cid,person in people.items():
        retained,proof=api[cid];rows=sorted([*older[cid],*originals[cid],*retained],key=lambda r:(r['month'],r['source']))
        if len({r['month'] for r in rows})!=len(rows):
            raise ValueError('Bridge has overlapping or duplicate monthly observations')
        snapshot=next(r for r in originals[cid] if r['month']==person['snapshot'])
        if snapshot['standard_elo']!=person['snapshot_elo']:
            raise ValueError('Original-list frozen snapshot differs; no source substitution permitted')
        aliases=[]
        for name in sorted({r['source_name'] for r in originals[cid]}):
            witnesses=[r for r in originals[cid] if r['source_name']==name]
            if name!=person['name']:
                aliases.append({'canonical_id':cid,'frozen_name':person['name'],'source_name':name,
                    'frozen_dob':person['exact_dob_frozen'],'source_birth_year':int(person['exact_dob_frozen'][:4]),
                    'decision':'explicit_registered_name_variant_with_same_exact_FIDE_ID_and_original_list_birthyear',
                    'witness_points':witnesses[:1]})
        coverage={'mode':'api_window_gap_bridge','official_list_periods':needed[cid],
            'official_list_first':needed[cid][0],'official_list_last':needed[cid][-1],
            'official_list_period_count':len(needed[cid]),'historical_base_through':'2003-04',
            'historical_transcription_first':min((r['month'] for r in older[cid]),default=None),
            'historical_transcription_last':max((r['month'] for r in older[cid]),default=None),
            'historical_transcription_periods':sorted(r['month'] for r in older[cid]),
            'api_first_period':proof['first_period'],'api_last_available_period':proof['last_available_period'],
            'api_retained_through_cutoff_n':proof['retained_through_cutoff_n'],
            'api_excluded_future_point_n':proof['excluded_future_point_n'],
            'label_end_period':CUTOFF,'career_termination_not_assumed':True,
            'gap_identification':'Explicit unresolved preferred-API coverage; complete original-list publication periods bridge January2010 to the month preceding the first positive API observation. Earlier2003–2009 transcription rows append the independently audited pre-April2003 base.',
            'source_selection':'coverage_availability_not_rating_magnitude'}
        coverage.update(source_window_metadata(proof['last_available_period']))
        frozen={'month':person['snapshot'],'rating':person['snapshot_elo'],
            'archive_url':snapshot['source_url'],**{k:snapshot[k] for k in ('archive_sha256','archive_member','source_line_number','source_line')}}
        payload={'protocol_id':PROTOCOL,'canonical_id':cid,'name':person['name'],
            'frozen_snapshot':frozen,'standard_history':rows,
            'archive_ledger':sorted([*older_ledger[cid],*original_ledger[cid]],key=lambda r:r['period']),
            'coverage':coverage,'career_termination':None,'api_history_evidence':proof,
            'identity_aliases':aliases,'frozen_birth_features_unchanged':True,
            'compiler_provenance':{'source_file':'studies/chess_peak_v1/compile_gap_supplements.py','sha256':digest(Path(__file__).read_bytes()),'network_requests_performed':False},
            'source_selection':'Explicit unavailable API window only, independent of peak or any association result.'}
        path=out/f'gap_{cid}.json';path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');written.append(path)
    return written


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',type=Path,default=Path.cwd());p.add_argument('--acquisition-dir',type=Path,required=True)
    p.add_argument('--official-cache',type=Path,action='append',required=True)
    p.add_argument('--historical-archive',type=Path,required=True);p.add_argument('--canonical-id',action='append')
    p.add_argument('--output-dir',type=Path)
    a=p.parse_args();paths=compile_supplements(a.repo_root,a.acquisition_dir,a.official_cache,a.historical_archive,canonical_ids=a.canonical_id,output_dir=a.output_dir)
    print(json.dumps({'compiled':[{'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path.read_bytes())} for path in paths]}))


if __name__=='__main__':
    main()
