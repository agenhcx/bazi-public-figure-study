from pathlib import Path
import gzip
import json
import tempfile
import unittest
import zipfile

from compile_gap_supplements import (api_evidence,digest,eligible_entry,expected_periods,parse_original_line,original_rows,source_dob_discrepancy,source_window_metadata)
from collect_fide import parse_provider


class GapCompilerTests(unittest.TestCase):
    def person(self):
        return {'canonical_id':'3901211','name':'Iturrizaga, Eduardo','role':'development',
                'exact_dob_frozen':'1989-11-01','snapshot':'2013-01','snapshot_elo':2650,
                'wikidata_person_qids':['Q123']}

    def test_expected_published_periods_respect_schedule_and_boundary(self):
        p=expected_periods('2015-02')
        self.assertEqual(len(p),46);self.assertEqual(p[-1],'2015-01')
        self.assertNotIn('2011-02',p);self.assertNotIn('2012-06',p)
        self.assertIn('2012-08',p)
        self.assertEqual(len(expected_periods('2017-01')),69)

    def test_eligibility_does_not_treat_conflicts_as_unavailable_windows(self):
        e={'status':'history_acquired_requires_snapshot_audit','source_provider':'lichess_fide_history',
           'source_coverage_audit':{'unresolved':True}}
        self.assertTrue(eligible_entry(e))
        self.assertFalse(eligible_entry({**e,'status':'failed','error_type':'SourceIntegrityError'}))
        self.assertFalse(eligible_entry({**e,'snapshot_disagreement':{'difference':1}}))
        self.assertFalse(eligible_entry({**e,'source_coverage_audit':{'unresolved':False}}))

    def fixture_line(self,name='Iturrizaga Bonelli, Eduardo',year=1989):
        header='ID Number'.ljust(15)+'Name'.ljust(60)+'Fed Sex Tit WTit OTit jan14 Gms K B-day Flag'
        line='3901211'.ljust(15)+name.ljust(60)+f'VEN M GM              2645 0 10 {year}      '
        return header,line

    def test_original_alias_requires_identity_and_preserves_trailing_spaces(self):
        header,line=self.fixture_line()
        row,ledger=parse_original_line(self.person(),line+'\r\n',header,'2014-01','standard_jan14frl.txt',42,
            {'source_url':'https://ratings.fide.com/download/standard_jan14frl.zip','sha256':'a'*64,'bytes':100})
        self.assertEqual(row['standard_elo'],2645);self.assertEqual(row['source_line'],line)
        self.assertEqual(row['source_name'],'Iturrizaga Bonelli, Eduardo')
        self.assertEqual(row['source_birth_year'],1989)
        self.assertEqual(ledger['source_line'],line)
        self.assertFalse(row['source_header_period_mismatch'])
        with self.assertRaises(ValueError):
            bad_header,bad_line=self.fixture_line(name='Other, Person')
            parse_original_line(self.person(),bad_line,bad_header,'2014-01','standard_jan14frl.txt',42,
                {'source_url':'x','sha256':'a'*64,'bytes':100})

    def test_original_birthyear_disagreement_stops_compilation(self):
        header,line=self.fixture_line(year=1990)
        with self.assertRaises(ValueError):
            parse_original_line(self.person(),line,header,'2014-01','standard_jan14frl.txt',42,
                {'source_url':'x','sha256':'a'*64,'bytes':100})

    def test_unlisted_player_is_negative_evidence_not_an_invented_score(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'standard_jan14frl.zip'
            header,line=self.fixture_line(name='Other, Person')
            line=line.replace('3901211','3909999',1)
            with zipfile.ZipFile(path,'w') as z:z.writestr('standard_jan14frl.txt',header+'\n'+line+'\n')
            rows,ledger=original_rows({'2014-01':{'path':path,'source_url':'https://ratings.fide.com/download/standard_jan14frl.zip','sha256':digest(path.read_bytes()),'bytes':path.stat().st_size}},
                {'3901211':self.person()},{'3901211':['2014-01']})
            self.assertEqual(rows['3901211'],[])
            self.assertTrue(ledger['3901211'][0]['player_unlisted'])
            self.assertIsNone(ledger['3901211'][0]['source_line'])

    def test_exact_name_under_another_id_requires_adjudication(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'standard_jan14frl.zip'
            header,line=self.fixture_line();line=line.replace('3901211','3909999',1)
            with zipfile.ZipFile(path,'w') as z:z.writestr('standard_jan14frl.txt',header+'\n'+line+'\n')
            with self.assertRaises(ValueError):
                original_rows({'2014-01':{'path':path,'source_url':'https://ratings.fide.com/download/standard_jan14frl.zip','sha256':digest(path.read_bytes()),'bytes':path.stat().st_size}},
                    {'3901211':self.person()},{'3901211':['2014-01']})

    def test_unknown_source_dob_is_not_mislabeled_as_a_disagreement(self):
        self.assertFalse(source_dob_discrepancy('', '1989-11-01'))
        self.assertFalse(source_dob_discrepancy('1989', '1989-11-01'))
        self.assertFalse(source_dob_discrepancy('1989.11.01', '1989-11-01'))
        self.assertTrue(source_dob_discrepancy('1989.11.02', '1989-11-01'))
        self.assertTrue(source_dob_discrepancy('1990', '1989-11-01'))

    def test_tail_flags_report_observed_end_without_extrapolation(self):
        early=source_window_metadata('2022-10')
        self.assertEqual(early['verified_source_window_end'],'2022-10')
        self.assertTrue(early['source_tail_incomplete'])
        self.assertFalse(early['source_window_reaches_cutoff'])
        self.assertFalse(early['complete_through_cutoff'])
        for end in ['2023-12','2026-10']:
            exact=source_window_metadata(end)
            self.assertTrue(exact['source_window_reaches_cutoff'])
            self.assertFalse(exact['source_tail_incomplete'])
        with self.assertRaises(ValueError):source_window_metadata('2023-13')

    def api_fixture(self,base):
        person=self.person();cid=person['canonical_id'];url=f'https://lichess.org/api/fide/player/{cid}/ratings'
        raw=json.dumps({'standard':[2017012652,2017022650,2024012700],'rapid':[],'blitz':[]}).encode()
        compressed=gzip.compress(raw,mtime=0)
        metadata={'canonical_id':cid,'source_provider':'lichess_fide_history','source_url':url,'raw_sha256':digest(raw)}
        meta_bytes=json.dumps(metadata).encode()
        e={'source_provider':'lichess_fide_history','raw_file':'coverage-evidence/api.json.gz','raw_sha256':digest(raw),
           'gzip_sha256':digest(compressed),'metadata_file':'coverage-evidence/api.metadata.json','metadata_sha256':digest(meta_bytes)}
        for name,data in [(e['raw_file'],compressed),(e['metadata_file'],meta_bytes)]:
            p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        history=parse_provider(raw,cid,'lichess_fide_history',snapshot=person['snapshot'])['all_standard_history']
        normalized={'canonical_id':cid,'source_provider':'lichess_fide_history','source_raw_sha256':digest(raw),'standard_history':history}
        normalized_bytes=json.dumps(normalized).encode();path=base/f'normalized/{cid}.json';path.parent.mkdir();path.write_bytes(normalized_bytes)
        entry={**person,'status':'history_acquired_requires_snapshot_audit','source_provider':'lichess_fide_history',
               'source_url':url,'raw_sha256':digest(raw),'normalized_history_file':f'normalized/{cid}.json',
               'normalized_history_sha256':digest(normalized_bytes),'source_coverage_audit':{'unresolved':True,'sources':[e]}}
        path=base/f'entries/{cid}.json';path.parent.mkdir();path.write_text(json.dumps(entry))
        return person,entry

    def test_api_proof_preserves_exact_indices_and_excludes_future(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);person,entry=self.api_fixture(base)
            rows,evidence=api_evidence(base,person,entry)
            self.assertEqual(len(rows),2);self.assertEqual(evidence['excluded_future_point_n'],1)
            self.assertEqual([r['api_history_point_index'] for r in rows],[0,1])
            self.assertEqual([r['api_raw_point_index'] for r in rows],[0,1])
            self.assertEqual(rows[0]['api_raw_packed_value'],2017012652)
            self.assertEqual(rows[0]['source'],'lichess_fide_history')
            self.assertNotIn('archive_sha256',rows[0])
            self.assertEqual(evidence['normalized_file'],'list-supplements/evidence/3901211.api-normalized.json')

    def test_api_evidence_tampering_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);person,entry=self.api_fixture(base)
            (base/'coverage-evidence/api.metadata.json').write_text('{}')
            with self.assertRaises(ValueError):api_evidence(base,person,entry)


if __name__=='__main__':unittest.main()
