#!/usr/bin/env python3
"""Additional fixed-batch p adjustments, without pooling trait observations."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = ['DE_Leopoldina', 'France', 'Japan']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def holm(pvalues):
    ordered = sorted(enumerate(pvalues), key=lambda x: (x[1], x[0]))
    adjusted = [0.] * len(pvalues)
    running = 0.
    for rank, (index, p) in enumerate(ordered):
        assert 0 <= p <= 1
        running = max(running, min(1., (len(ordered) - rank) * p))
        adjusted[index] = running
    return adjusted


def main(args):
    if args.synthetic_qa_only:
        assert holm([.01, .04, .03]) == [.03, .06, .06]
        assert holm([1., 0., 1.]) == [1., 0., 1.]
        print(json.dumps({'status': 'PASS', 'study_inputs_loaded': False, 'fixed_batch_sizes': [120, 90]}))
        return
    scope = json.loads(Path(args.scope).read_text())
    receipt = json.loads(Path(args.execution_receipt).read_text())
    assert scope['allowed_institutions'] == receipt['allowed_institutions'] == ALLOWED
    assert receipt['remote_plan_and_code_verified_before_summary'] is True
    assert receipt['scope_sha256'] == sha(args.scope)
    assert receipt['locked_file_manifest_sha256'] == sha(args.locked_files)
    for rel, digest in json.loads(Path(args.locked_files).read_text()).items():
        assert sha(ROOT / rel) == digest, rel
    out = Path(args.output)
    assert not out.exists(), 'No batch output overwrite'
    levels, trends, inputs = [], [], {}
    for institution in ALLOWED:
        path = Path(args.work) / 'outputs' / institution / 'tables_results.json'
        result = json.loads(path.read_text())
        assert result['country'] == institution
        group = result['groups']['strict']
        assert len(group['levels']) == 40 and len(group['trends']) == 30
        assert group['people'] == scope['populations'][institution]['strict']['people']
        assert group['person_ids_sha256'] == scope['populations'][institution]['strict']['person_ids_sha256']
        inputs[institution] = sha(path)
        for x in group['levels']:
            levels.append({'institution': institution, 'endpoint_id': x['endpoint_id'],
                           'p_nominal': x['p_two_sided'], 'p_Holm40': x['p_Holm40']})
        for x in group['trends']:
            trends.append({'institution': institution, 'endpoint_id': x['endpoint_id'],
                           'p_nominal': x['p_nominal_two_sided'], 'p_Holm30': x['p_Holm30']})
    for rows, count, key in [(levels, 120, 'p_Holm120'), (trends, 90, 'p_Holm90')]:
        assert len(rows) == count
        for row, p in zip(rows, holm([r['p_nominal'] for r in rows])):
            row[key] = p
            row['reject_0_05'] = p <= .05
    result = {'schema': 'DE_FR_JP_fixed_batch_p_adjustment_v1', 'allowed_institutions': ALLOWED,
              'levels': levels, 'trends': trends,
              'level_family_size': 120, 'trend_family_size': 90,
              'no_new_tests': True, 'trait_observations_pooled': False,
              'strict_primary_only': True, 'original36_and18_unchanged': True,
              'per_institution_Holm40_Holm30_retained': True,
              'input_result_sha256': inputs, 'code_sha256': sha(__file__),
              'execution_lock_commit': receipt['commit']}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'Holm120_rejections': sum(r['reject_0_05'] for r in levels),
                      'Holm90_rejections': sum(r['reject_0_05'] for r in trends)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--synthetic-qa-only', action='store_true')
    for k in ['scope', 'locked-files', 'execution-receipt', 'work', 'output']:
        p.add_argument('--' + k)
    main(p.parse_args())
