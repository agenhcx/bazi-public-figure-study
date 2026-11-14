#!/usr/bin/env python3
"""Independent literal-feature audit for three newly authorized institutions.

Only synthetic QA may run before the parent confirms a verified remote lock.
No production analysis function is imported by this auditor.
"""
import argparse
from collections import Counter
import datetime as dt
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import zipfile

import numpy as np
from scipy.signal import convolve

STEMS = list('甲乙丙丁戊己庚辛壬癸')
BRANCHES = list('子丑寅卯辰巳午未申酉戌亥')
GODS = '比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印'.split()
ELEMENTS = list('金木水火土')
ELEMENT_OF = dict(zip(STEMS, '木木火火土土金金水水'))
LITERAL_ROWS = {
    '甲': '比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印',
    '乙': '劫财 比肩 伤官 食神 正财 偏财 正官 七杀 正印 偏印',
    '丙': '偏印 正印 比肩 劫财 食神 伤官 偏财 正财 七杀 正官',
    '丁': '正印 偏印 劫财 比肩 伤官 食神 正财 偏财 正官 七杀',
    '戊': '七杀 正官 偏印 正印 比肩 劫财 食神 伤官 偏财 正财',
    '己': '正官 七杀 正印 偏印 劫财 比肩 伤官 食神 正财 偏财',
    '庚': '偏财 正财 七杀 正官 偏印 正印 比肩 劫财 食神 伤官',
    '辛': '正财 偏财 正官 七杀 正印 偏印 劫财 比肩 伤官 食神',
    '壬': '食神 伤官 偏财 正财 七杀 正官 偏印 正印 比肩 劫财',
    '癸': '伤官 食神 正财 偏财 正官 七杀 正印 偏印 劫财 比肩',
}
TG = {day: dict(zip(STEMS, [GODS.index(v) for v in row.split()])) for day, row in LITERAL_ROWS.items()}
HIDDEN = {'子': '癸', '丑': '己癸辛', '寅': '甲丙戊', '卯': '乙', '辰': '戊乙癸',
          '巳': '丙戊庚', '午': '丁己', '未': '己丁乙', '申': '庚壬戊', '酉': '辛', '戌': '戊辛丁', '亥': '壬甲'}
BINS = list(range(1830, 1990, 10))
L = 365 * 366
PRIMARY_R = 99999
QA_R = 15000
QA_SEED = 202611290000
COUNTRY_INDEX = {'DE_Leopoldina': 2, 'France': 3, 'Japan': 4}
ALLOWED_INSTITUTIONS = list(COUNTRY_INDEX)
ROOT = Path(__file__).resolve().parents[2]
PINNED = {'v4_zip': '53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9',
          'calendar_npz': 'd150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b'}
LEVEL_CROSSCHECKS = ['DM_壬', 'M0_偏印', 'M0_element_水']
TREND_CROSSCHECKS = ['DM_甲', 'M0_偏印', 'M1_偏印']


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def close(a, b, message, atol=1e-8):
    require(np.allclose(a, b, rtol=1e-9, atol=atol), f'{message}: {a!r} versus {b!r}')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def literal_encode(yp, mp, dp):
    features = np.zeros((len(dp), 40), dtype=np.int16)
    for i, (year, month, day) in enumerate(zip(yp, mp, dp)):
        year, month, day = str(year), str(month), str(day)
        features[i, STEMS.index(day[0])] = 1
        visible = {year[0], month[0]}
        for model in range(2):
            targets = [year[0], month[0]]
            for branch in [year[1], month[1], day[1]]:
                exposed = [s for s in HIDDEN[branch] if s in visible]
                targets.append(exposed[0] if model and exposed else HIDDEN[branch][0])
            for target in targets:
                features[i, 10 + model * 10 + TG[day[0]][target]] += 1
                features[i, 30 + model * 5 + ELEMENTS.index(ELEMENT_OF[target])] += 1
    for start, count, total in [(0, 10, 1), (10, 10, 5), (20, 10, 5), (30, 5, 5), (35, 5, 5)]:
        require(np.all(features[:, start:start + count].sum(axis=1) == total), 'Literal partition total differs')
    return features


def ids():
    return ['DM_' + s for s in STEMS] + ['M0_' + g for g in GODS] + ['M1_' + g for g in GODS] + \
           ['M0_element_' + e for e in ELEMENTS] + ['M1_element_' + e for e in ELEMENTS]


def holm(pvalues):
    order = sorted(range(len(pvalues)), key=lambda i: (pvalues[i], i))
    out, last = [0.] * len(pvalues), 0.
    for rank, i in enumerate(order):
        last = max(last, min(1., (len(pvalues) - rank) * pvalues[i]))
        out[i] = last
    return out


def normalized_convolve(a, b):
    result = convolve(a, b, mode='full', method='direct')
    require(np.all(result >= 0) and np.isfinite(result).all(), 'Invalid independent PMF')
    total = math.fsum(float(x) for x in result)
    require(total > 0, 'Zero independent probability mass')
    return result / total


def polynomial_power(p, n):
    result, factor = np.array([1.]), np.asarray(p, dtype=float)
    while n:
        if n & 1:
            result = normalized_convolve(result, factor)
        n //= 2
        if n:
            factor = normalized_convolve(factor, factor)
    return result


def grouped_exact_test(terms, observed):
    expectation, dist = Fraction(0), np.array([1.])
    for n, histogram in terms:
        days = sum(int(x) for x in histogram)
        expectation += n * Fraction(sum(i * int(x) for i, x in enumerate(histogram)), days)
        dist = normalized_convolve(dist, polynomial_power(np.asarray(histogram) / days, n))
    distance = abs(Fraction(observed) - expectation)
    p = math.fsum(float(dist[i]) for i in range(len(dist)) if abs(Fraction(i) - expectation) >= distance)
    return expectation, min(1., p)


def synthetic_qa():
    require(all(sorted(TG[ds].values()) == list(range(10)) for ds in STEMS), 'Literal TG bijection')
    yp, mp, dp = [], [], []
    for ds, ys, ms, j in itertools.product(STEMS, STEMS, STEMS, range(12)):
        yp.append(ys + BRANCHES[j])
        mp.append(ms + BRANCHES[(j + 4) % 12])
        dp.append(ds + BRANCHES[(j + 7) % 12])
    features = literal_encode(yp, mp, dp)
    # Validate absolute-element reconstruction without importing production code.
    element_cycle = list('木火土金水')
    for i, d in enumerate(dp):
        for m in range(2):
            recovered = np.zeros(5, dtype=int)
            for g in range(10):
                e = element_cycle[(element_cycle.index(ELEMENT_OF[d[0]]) + g // 2) % 5]
                recovered[ELEMENTS.index(e)] += int(features[i, 10 + m * 10 + g])
            require(np.array_equal(recovered, features[i, 30 + m * 5:35 + m * 5]), 'Absolute element recovery')
    # Exact discrete probability comparison against enumeration.
    terms = [(2, [1, 1]), (1, [2, 1])]
    for observed in range(4):
        p = Fraction(0)
        for a, b, c in itertools.product([0, 1], repeat=3):
            if abs(Fraction(a + b + c) - Fraction(4, 3)) >= abs(Fraction(observed) - Fraction(4, 3)):
                p += Fraction(1, 4) * (Fraction(1, 3) if c else Fraction(2, 3))
        e, tested = grouped_exact_test(terms, observed)
        require(e == Fraction(4, 3), 'Synthetic exact expected value')
        close(tested, float(p), 'Synthetic exact p', atol=1e-14)
    # Independent centered OLS and calendar centering on a synthetic design.
    x = np.array([0., 0., 1., 2.]); y = np.array([0., 1., 2., 3.]); expected = y.copy()
    z = x - x.mean()
    slope = float(z @ y / (z @ z))
    n = len(x); a = n * x.astype(int) - int(x.sum()); denominator = n * int(x @ x) - int(x.sum()) ** 2
    close(slope, float(a @ y / denominator), 'Synthetic OLS identity')
    close(float(z @ (y - expected) / (z @ z)), 0., 'Synthetic calendar centered slope')
    close(holm([.01, .04, .03]), [.03, .06, .06], 'Synthetic Holm')
    return {'status': 'PASS', 'study_data_loaded': False, 'literal_pillar_cases': len(dp),
            'literal_TenGod_table_and_element_recovery': True, 'grouped_polynomial_exact_tail': True,
            'centered_OLS_and_calendar_excess': True, 'Holm': True}


def read_rows(z, name):
    return [json.loads(x) for x in gzip.decompress(z.read('scientist_north_data_freeze_v4/outputs/' + name)).splitlines()]


def id_hash(person_ids):
    raw = json.dumps(sorted(person_ids), ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
    return hashlib.sha256(raw.encode()).hexdigest()


def selected_people(v4_zip, institution, population_pins):
    with zipfile.ZipFile(v4_zip) as z:
        selected, ordered = {}, {}
        for quality in ['strict', 'expanded']:
            institution_rows = read_rows(z, quality + '/by_institution/' + institution + '.jsonl.gz')
            membership = {p['person_id']: p for p in institution_rows}
            nonnobel = {p['person_id'] for p in read_rows(z, quality + '/academy_excluding_official_Nobel.jsonl.gz')}
            selected[quality] = set(membership) & nonnobel
            people = {p['person_id']: p for p in read_rows(z, quality + '/people.jsonl.gz')
                      if p['person_id'] in selected[quality]}
            require(set(people) == selected[quality], 'Selected institution people missing')
            pins = population_pins[quality]
            require(len(people) == pins['people'], 'Institution source population N differs')
            require(id_hash(people) == pins['person_ids_sha256'], 'Institution source person-ID hash differs')
            ordered[quality] = [people[pid] for pid in sorted(people)]
            for p in ordered[quality]:
                require(p['hemisphere'] == 'north' and not p['person_level_DOB_analysis_hold'],
                        'Institution source hold or hemisphere differs')
                require(dt.date(1835, 1, 1) <= dt.date.fromisoformat(p['analysis_DOB']) <= dt.date(1985, 12, 31),
                        'Institution DOB window differs')
                require(p['analysis_DOB'] == membership[p['person_id']]['analysis_DOB'],
                        'Source-specific institution DOB differs from its own people row')
    require(selected['strict'] <= selected['expanded'], 'Strict source is not a subset of expanded')
    same = [(p['person_id'], p['analysis_DOB']) for p in ordered['strict']] == \
           [(p['person_id'], p['analysis_DOB']) for p in ordered['expanded']]
    return ordered, same


def independent_mc(j, year_counts, year_coefficients, year_features, expected_scaled, observed_centered, institution):
    rng = np.random.Generator(np.random.PCG64(QA_SEED + COUNTRY_INDEX[institution] * 10000 + j))
    simulations = np.zeros(QA_R, dtype=np.int64)
    for year, count in sorted(year_counts.items()):
        values, a = year_features[year][:, j], year_coefficients[year]
        if j < 10:
            totals = rng.binomial(count, float(np.mean(values)), size=QA_R)
        else:
            p = np.bincount(values, minlength=6).astype(float) / len(values)
            totals = rng.multinomial(count, p, size=QA_R) @ np.arange(6, dtype=np.int64)
        simulations += a * totals
    centered = simulations * L - expected_scaled
    count = int(np.count_nonzero(np.abs(centered) >= abs(observed_centered)))
    return (1 + count) / (QA_R + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-qa-only', action='store_true')
    parser.add_argument('--institution', choices=ALLOWED_INSTITUTIONS)
    for name in ['v4-zip', 'calendar-npz', 'scope', 'locked-files', 'results', 'execution-receipt', 'output']:
        parser.add_argument('--' + name)
    args = parser.parse_args()
    if args.synthetic_qa_only:
        result = synthetic_qa()
        if args.output:
            require(not Path(args.output).exists(), 'Synthetic output exists')
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    require(all(getattr(args, k) for k in ['institution', 'v4_zip', 'calendar_npz', 'scope', 'locked_files',
                                         'results', 'execution_receipt', 'output']), 'Study audit input missing')
    require(not Path(args.output).exists(), 'Study audit output exists')
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get('remote_plan_and_code_verified_before_summary') is True, 'Verified remote execution receipt missing')
    require(args.institution in receipt.get('allowed_institutions', []), 'Institution not authorized by receipt')
    scope = json.loads(Path(args.scope).read_text())
    require(args.institution in scope['allowed_institutions'], 'Institution not authorized by scope')
    require(receipt['scope_sha256'] == sha(args.scope), 'Scope hash does not match verified receipt')
    require(receipt['locked_file_manifest_sha256'] == sha(args.locked_files), 'Locked-file manifest hash differs')
    manifest = json.loads(Path(args.locked_files).read_text())
    own = str(Path(__file__).resolve().relative_to(ROOT))
    require(own in manifest and manifest[own] == sha(__file__), 'Auditor absent from locked manifest')
    for rel, digest in manifest.items():
        require(sha(ROOT / rel) == digest, 'Pre-run locked file changed: ' + rel)
    for name, digest in PINNED.items():
        require(sha(getattr(args, name)) == digest, 'Input hash pin differs: ' + name)
    audit(args, scope)


def audit(args, scope):
    result = json.loads(Path(args.results).read_text())
    require(result['country'] == args.institution, 'Wrong revealed institution')
    require(result['institution'] == args.institution, 'Institution label differs')
    require(result['original18_or_country36_modified'] is False, 'Original inference families were modified')
    require(result['CAS_or_Nobel_subgroups_aggregated'] is False and
            result['cross_institution_totals_or_comparisons_computed'] is False,
            'Results exceed the authorized per-institution reveal scope')
    populations, identical = selected_people(args.v4_zip, args.institution, scope['populations'][args.institution])
    require(result['source_groups_identical'] == identical and result['expanded_equals_strict'] == identical,
            'Source membership identity status differs')
    require(result['computed_source_cases'] == (['strict'] if identical else ['strict', 'expanded']),
            'Computed source cases differ from source-specific populations')
    if identical:
        group, expanded = result['groups']['strict'], result['groups']['expanded']
        require(result['expanded_results_reused_from'] == 'strict', 'Identical source not labelled reused')
        require(all(expanded[k] == v for k, v in group.items()) and expanded['reused_from'] == 'strict',
                'Expanded display is not exact strict reuse')
    with np.load(args.calendar_npz, allow_pickle=False) as data:
        dates, years = data['dates'].tolist(), data['year'].astype(np.int64)
        yp, mp, dp = (data[k].tolist() for k in ['year_pillar', 'month_pillar', 'day_pillar'])
    lookup = {d: i for i, d in enumerate(dates)}
    require(len(dates) == len(lookup) == 55152, 'Calendar coverage differs')
    features = literal_encode(yp, mp, dp).astype(np.int64)
    endpoint_ids = ids()
    require([e['id'] for e in result['endpoint_order']] == endpoint_ids, 'Level endpoint order differs')
    require([e['id'] for e in result['trend_endpoint_order']] == endpoint_ids[:30], 'Trend endpoint order differs')
    require(result['decade_bins'] == BINS, 'Decade boundaries differ')
    require(result['trends_MC']['replicates'] == PRIMARY_R, 'Primary trend MC repetition count differs')
    require(result['trends_MC']['country_index'] == COUNTRY_INDEX[args.institution], 'Trend country index differs')
    decade_counts = {source: Counter(int(p['analysis_DOB'][:4]) // 10 * 10 for p in rows)
                     for source, rows in populations.items()}
    common_decades = [d for d in BINS if all(decade_counts[source][d] >= 20 for source in populations)]
    require(result['common_adequate_decades'] == common_decades, 'Common adequate bins differ from metadata count rule')
    require(scope['common_adequate_decades'][args.institution] == common_decades, 'Scope common adequate bins differ')
    year_features = {int(y): features[years == y] for y in set(years.tolist())}
    means = {y: f.mean(axis=0) for y, f in year_features.items()}
    variances = {y: f.var(axis=0) for y, f in year_features.items()}
    fourth_cumulants = {y: ((f - means[y]) ** 4).mean(axis=0) - 3 * variances[y] ** 2 for y, f in year_features.items()}
    groups = {}
    for source_index, source in enumerate(['strict', 'expanded']):
        require(result['trends_MC']['source_seed_bases'][source] == result['groups'][source]['trend_seed_base'],
                'Top-level source seed metadata differs from its group')
        if identical and source == 'expanded':
            groups[source] = {'people': len(populations[source]), 'reused_from': 'strict',
                              'exact_strict_result_reuse_verified': True}
            continue
        groups[source] = audit_group(args, source, source_index, populations[source], result['groups'][source],
                                     features, lookup, year_features, means, variances, fourth_cumulants,
                                     endpoint_ids, common_decades, (yp, mp, dp), years)
    output = {'schema': 'institution_independent_literal_level_and_decade_QA_v1', 'status': 'PASS',
              'country': args.institution, 'synthetic_QA': synthetic_qa(),
              'source_groups_identical': identical, 'groups': groups, 'literal_calendar_rows_encoded': len(dates),
              'all40_level_counts_expectations_denominators_and_Holm_checked': True,
              'all16_by40_decade_cells_checked': True, 'all30_linear_slopes_integer_statistics_and_Holm_checked': True,
              'QA_p_values_do_not_replace_primary_p_values': True,
              'CAS_or_other_unopened_cohort_or_Nobel_subgroup_outcomes_opened': False,
              'hashes': {'results': sha(args.results), 'auditor': sha(__file__), 'v4_zip': sha(args.v4_zip),
                         'calendar_npz': sha(args.calendar_npz), 'execution_receipt': sha(args.execution_receipt),
                         'scope': sha(args.scope)}}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': 'PASS', 'country': args.institution,
                      'people': {k: len(v) for k, v in populations.items()}, 'levels': 40, 'trends': 30,
                      'output': args.output}, ensure_ascii=False))


def audit_group(args, source, source_index, people, group, features, lookup, year_features, means, variances,
                fourth_cumulants, endpoint_ids, common_decades, pillars, calendar_years):
    yp, mp, dp = pillars
    indexes = np.asarray([lookup[p['analysis_DOB']] for p in people], dtype=np.intp)
    birthyears = np.asarray([int(p['analysis_DOB'][:4]) for p in people], dtype=np.int64)
    observed = features[indexes]
    counts = Counter(int(y) for y in birthyears)
    expected = np.asarray([means[int(y)] for y in birthyears])
    n = len(people)
    require(group['people'] == n and group['five_position_denominator'] == 5 * n,
            'People or five-position denominator differs')
    require(group['person_ids_sha256'] == id_hash(p['person_id'] for p in people), 'Reported person-ID hash differs')
    require(group['birth_year_min'] == int(birthyears.min()) and group['birth_year_max'] == int(birthyears.max()),
            'DOB-year range differs')
    require(len(group['levels']) == 40 and len(group['bins']) == 16 and len(group['trends']) == 30,
            'Level, bin or trend cardinality differs')
    level_crosschecks = []
    for j, row in enumerate(group['levels']):
        require(row['endpoint_id'] == endpoint_ids[j], 'Level endpoint identity differs')
        obs = int(observed[:, j].sum())
        denominator = n if j < 10 else 5 * n
        expectation = Fraction(0)
        terms, variance = [], 0.
        for year, count in sorted(counts.items()):
            values = year_features[year][:, j]
            histogram = np.bincount(values, minlength=(2 if j < 10 else 6))
            days = len(values)
            expectation += count * Fraction(int(values.sum()), days)
            terms.append((count, histogram))
            variance += count * float(values.var())
        require(row['observed_total'] == obs and row['position_denominator'] == denominator, 'Level numerator/denominator differs')
        close(row['calendar_expected_total'], float(expectation), 'Level expected total')
        close(row['observed_share'], obs / denominator, 'Level observed share')
        close(row['calendar_expected_share'], float(expectation) / denominator, 'Level expected share')
        close(row['observed_mean_per_person'], obs / n, 'Level observed person mean')
        close(row['calendar_expected_mean_per_person'], float(expectation) / n, 'Level expected person mean')
        close(row['excess_percentage_points'], (obs - float(expectation)) / denominator * 100, 'Level excess pp')
        close(row['null_SD_total'], math.sqrt(variance), 'Level null SD')
        require(row['observed_people_with_at_least_one'] == int((observed[:, j] > 0).sum()), 'Level presence differs')
        require(row['exact_expected_numerator'] == str(expectation.numerator) and row['exact_expected_denominator'] == str(expectation.denominator),
                'Level exact rational expectation differs')
        close(row['enrichment_ratio'], obs / float(expectation), 'Level enrichment ratio')
        distance = abs(obs * expectation.denominator - expectation.numerator)
        lower, upper = row['two_sided_lower_inclusive'], row['two_sided_upper_inclusive']
        require(all((k <= lower or k >= upper) == (abs(k * expectation.denominator - expectation.numerator) >= distance)
                    for k in range(denominator + 1)), 'Level exact centered tail membership differs')
        require(0 <= row['p_two_sided'] <= 1, 'Level p outside unit interval')
        if source == 'strict' and row['endpoint_id'] in LEVEL_CROSSCHECKS:
            tested_expected, p = grouped_exact_test(terms, obs)
            require(tested_expected == expectation, 'Level preselected exact mean differs')
            close(p, row['p_two_sided'], 'Independent preselected level p', atol=2e-10)
            level_crosschecks.append({'endpoint': row['endpoint_id'], 'analysis_p': row['p_two_sided'], 'independent_p': p})
    level_adjusted = holm([r['p_two_sided'] for r in group['levels']])
    close([r['p_Holm40'] for r in group['levels']], level_adjusted, 'Level Holm40')
    require(all(r['reject_Holm40_0_05'] == (p <= .05) for r, p in zip(group['levels'], level_adjusted)), 'Level Holm decisions differ')
    require(len(level_crosschecks) == (len(LEVEL_CROSSCHECKS) if source == 'strict' else 0),
            'Preselected level p checks missing')
    decade = birthyears // 10 * 10
    sum_obs, sum_exp = np.zeros(40), np.zeros(40)
    for cell in group['bins']:
        mask = decade == cell['decade']; number = int(mask.sum())
        require(cell['n'] == number, 'Decade N differs')
        require(list(cell['endpoints']) == endpoint_ids, 'Decade endpoint order differs')
        for j, endpoint in enumerate(endpoint_ids):
            r = cell['endpoints'][endpoint]
            obs, exp = int(observed[mask, j].sum()), float(expected[mask, j].sum())
            require(r['observed_total'] == obs, 'Decade observed total differs')
            close(r['calendar_expected_total'], exp, 'Decade expected total')
            denominator = number if j < 10 else 5 * number
            if not number:
                require(all(r[k] is None for k in ['observed_share', 'calendar_expected_share', 'excess_percentage_points']), 'Empty bin shares not None')
            else:
                close(r['observed_share'], obs / denominator, 'Decade observed share')
                close(r['calendar_expected_share'], exp / denominator, 'Decade expected share')
                close(r['excess_percentage_points'], 100 * (obs - exp) / denominator, 'Decade excess pp')
            sum_obs[j] += obs; sum_exp[j] += exp
        for start, width, units in [(0, 10, 1), (10, 10, 5), (20, 10, 5), (30, 5, 5), (35, 5, 5)]:
            close(sum(cell['endpoints'][endpoint_ids[j]]['observed_total'] for j in range(start, start + width)), units * number,
                  'Decade partition total')
    close(sum_obs, [r['observed_total'] for r in group['levels']], 'Decade totals reproduce full levels')
    close(sum_exp, [r['calendar_expected_total'] for r in group['levels']], 'Decade expected totals reproduce full levels')
    x = birthyears // 10
    sx = int(x.sum()); denominator = n * int(np.sum(x * x)) - sx ** 2
    require(denominator > 0, 'No birth-decade variance')
    a = n * x - sx
    obs_w = (a[:, None] * observed[:, :30]).sum(axis=0).astype(np.int64)
    coefficients = {y: n * (y // 10) - sx for y in counts}
    exp_w_scaled = sum(coefficients[y] * count * (L // len(year_features[y])) * year_features[y][:, :30].sum(axis=0)
                       for y, count in counts.items()).astype(np.int64)
    centered_w = obs_w * L - exp_w_scaled
    cx = x - x.mean(); sxx = float(cx @ cx)
    scale = np.array([100.] * 10 + [20.] * 20)
    raw_slope = (cx[:, None] * observed[:, :30]).sum(axis=0) / sxx * scale
    cal_slope = (cx[:, None] * expected[:, :30]).sum(axis=0) / sxx * scale
    excess_slope = raw_slope - cal_slope
    close(raw_slope, obs_w / denominator * scale, 'Centered and integer OLS raw slope')
    close(cal_slope, exp_w_scaled / L / denominator * scale, 'Centered and rational expected OLS slope')
    variance_w = sum(count * float(coefficients[y]) ** 2 * variances[y][:30] for y, count in counts.items())
    fourth_w = sum(count * float(coefficients[y]) ** 4 * fourth_cumulants[y][:30] for y, count in counts.items())
    analytic_sd = np.sqrt(variance_w) / denominator * scale
    relative_sd_error = np.sqrt(np.maximum(0, 2 * variance_w ** 2 + fourth_w) / PRIMARY_R) / (2 * variance_w)
    seed_base = 202611180000 + COUNTRY_INDEX[args.institution] * 10000 + source_index * 1000
    require(group['trend_seed_base'] == seed_base, 'Source-specific primary MC seed base differs')
    trend_crosschecks = []
    for j, t in enumerate(group['trends']):
        require(t['endpoint_id'] == endpoint_ids[j] and t['replicates'] == PRIMARY_R and t['LCM'] == L, 'Trend identity or R differs')
        require(t['seed'] == seed_base + j and t['generator'] == 'PCG64', 'Trend MC stream differs')
        require(t['OLS_integer_denominator'] == denominator and t['observed_integer_raw_numerator'] == int(obs_w[j]), 'Trend integer OLS differs')
        require(t['exact_expected_numerator_times_LCM'] == int(exp_w_scaled[j]) and
                t['observed_centered_numerator_times_LCM'] == int(centered_w[j]), 'Trend rational centered numerator differs')
        for field, array in [('raw_slope_pp_per_decade', raw_slope), ('calendar_expected_slope_pp_per_decade', cal_slope),
                             ('calendar_excess_slope_pp_per_decade', excess_slope), ('analytic_null_slope_SD_pp_per_decade', analytic_sd)]:
            close(t[field], array[j], 'Trend ' + field)
        close(t['p_nominal_two_sided'], (1 + t['extreme_replicates_including_ties']) / (PRIMARY_R + 1), 'Trend inclusive MC p formula', atol=1e-14)
        require(0 <= t['extreme_replicates_including_ties'] <= PRIMARY_R, 'Invalid trend MC extreme count')
        require(abs(t['MC_excess_slope_mean_pp_per_decade']) <= 6 * analytic_sd[j] / math.sqrt(PRIMARY_R) + 1e-10,
                'MC centered mean differs from analytic null')
        require(abs(t['MC_excess_slope_SD_pp_per_decade'] - analytic_sd[j]) <= 6 * relative_sd_error[j] * analytic_sd[j] + 1e-10,
                'MC SD differs from analytic null')
        if source == 'strict' and endpoint_ids[j] in TREND_CROSSCHECKS:
            q = independent_mc(j, counts, coefficients, year_features, int(exp_w_scaled[j]), int(centered_w[j]), args.institution)
            p = t['p_nominal_two_sided']; pooled = (p * PRIMARY_R + q * QA_R) / (PRIMARY_R + QA_R)
            tolerance = 5 * math.sqrt(max(0, pooled * (1 - pooled)) * (1 / PRIMARY_R + 1 / QA_R)) + 2 / QA_R
            require(abs(p - q) <= tolerance, 'Independent trend p differs beyond MC tolerance')
            trend_crosschecks.append({'endpoint': endpoint_ids[j], 'analysis_p': p, 'independent_QA_p': q,
                                       'QA_replicates': QA_R, 'tolerance': tolerance})
    require(len(trend_crosschecks) == (len(TREND_CROSSCHECKS) if source == 'strict' else 0),
            'Preselected trend p checks missing')
    trend_adjusted = holm([t['p_nominal_two_sided'] for t in group['trends']])
    close([t['p_Holm30'] for t in group['trends']], trend_adjusted, 'Trend Holm30')
    require(all(t['reject_Holm30_0_05'] == (p <= .05) for t, p in zip(group['trends'], trend_adjusted)), 'Trend Holm decisions differ')
    common = group['common_adequate_bins_desc']; keep = np.isin(decade, common_decades)
    require(common['people'] == int(keep.sum()) and common['decades'] == common_decades and
            common['hypothesis_tests_performed'] is False, 'Adequate-bin sensitivity metadata differs')
    z = x[keep] - x[keep].mean(); zz = float(z @ z)
    require(zz > 0, 'Common adequate-bin descriptive trend has no variance')
    common_raw = (z[:, None] * observed[keep, :30]).sum(axis=0) / zz * scale
    common_cal = (z[:, None] * expected[keep, :30]).sum(axis=0) / zz * scale
    for j, t in enumerate(common['trends']):
        require(t['endpoint_id'] == endpoint_ids[j], 'Common-window endpoint differs')
        close(t['raw_slope_pp_per_decade'], common_raw[j], 'Common-window raw OLS')
        close(t['calendar_expected_slope_pp_per_decade'], common_cal[j], 'Common-window calendar OLS')
        close(t['calendar_excess_slope_pp_per_decade'], common_raw[j] - common_cal[j], 'Common-window excess OLS')
        require(t.get('p_nominal_two_sided') is None and t.get('p_Holm30') is None, 'Common-window sensitivity must not add tests')
    for name, pillars in [('year_stem', yp), ('month_stem', mp), ('day_stem', dp)]:
        stem_values = np.array([STEMS.index(p[0]) for p in pillars], dtype=int)
        obs = np.bincount(stem_values[indexes], minlength=10)
        exp = sum(count * np.bincount(stem_values[calendar_years == year], minlength=10) / int((calendar_years == year).sum())
                  for year, count in counts.items())
        for j, r in enumerate(group['HeavenlyStem_positions'][name]):
            require(r['stem'] == STEMS[j] and r['observed_people'] == int(obs[j]), 'Other stem observed count differs')
            close(r['calendar_expected_people'], exp[j], 'Other stem expected count')
            close(r['observed_share'], obs[j] / n, 'Other stem observed share')
            close(r['calendar_expected_share'], exp[j] / n, 'Other stem expected share')
            require(r['hypothesis_test_performed_in_this_table'] is False, 'Other stem descriptive table must not add tests')
            require(r['same_as_level_DM_endpoint'] == (name == 'day_stem'), 'DayStem table must identify reused tested endpoint')
    return {'status': 'PASS', 'people': n, 'person_ids_sha256': group['person_ids_sha256'],
            'all40_level_counts_expectations_denominators_and_Holm_checked': True,
            'all16_by40_decade_cells_checked': True,
            'all30_linear_slopes_integer_statistics_and_Holm_checked': True,
            'common_window_people': int(keep.sum()), 'common_window_decades': common_decades,
            'preselected_exact_level_p_crosschecks': level_crosschecks,
            'preselected_independent_trend_MC_crosschecks': trend_crosschecks,
            'trend_seed_base': seed_base}


if __name__ == '__main__':
    main()
