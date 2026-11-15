#!/usr/bin/env python3
"""Independent conditional-on-total daymaster decade audit.

Pure synthetic mode never loads cohort data. Real execution requires a verified
remote lock receipt. This auditor never imports the main implementation.
"""
import argparse
from collections import Counter
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

ROOT = Path(__file__).resolve().parents[2]
BINS = list(range(1830, 1990, 10))
TARGETS = ['CAS_xin', 'NAS_water']
SOURCES = ['strict', 'expanded']
QA_R = 15000
QA_SEED = 202611250000
PRIMARY_R = 99999
V4_SHA = '53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9'
POOL_SHA = 'd150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b'


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(a, b, message, atol=1e-9):
    require(np.allclose(a, b, rtol=1e-9, atol=atol), message)


def norm_conv(a, b, cap=None):
    values = convolve(np.asarray(a, float), np.asarray(b, float), method='direct')
    if cap is not None:
        values = values[:cap + 1]
    require(np.isfinite(values).all() and np.all(values >= 0), 'Invalid independent polynomial')
    total = math.fsum(float(x) for x in values)
    require(total > 0, 'Independent polynomial has zero mass')
    return values / total


def power_pmf(p, count, cap):
    result, factor = np.array([1.]), np.asarray(p, float)
    n = int(count)
    while n:
        if n & 1:
            result = norm_conv(result, factor, cap)
        n //= 2
        if n:
            factor = norm_conv(factor, factor, cap)
    return result


def product_pmfs(pmfs, cap):
    work = [np.asarray(p, float) for p in pmfs]
    if not work:
        return np.array([1.])
    while len(work) > 1:
        work = [norm_conv(work[i], work[i + 1], cap) if i + 1 < len(work) else work[i]
                for i in range(0, len(work), 2)]
    return work[0]


def independent_margins(p_by_bin, total):
    """Different grouped-power algorithm, rebuilding other bins from scratch."""
    bin_pmfs = []
    for terms in p_by_bin:
        factors = [power_pmf([1 - p, p], n, total) for n, p in terms]
        bin_pmfs.append(product_pmfs(factors, total))
    answer = []
    for j, own in enumerate(bin_pmfs):
        other = product_pmfs([x for i, x in enumerate(bin_pmfs) if i != j], total)
        values = np.zeros(min(total, len(own) - 1) + 1)
        for k in range(len(values)):
            remaining = total - k
            if 0 <= remaining < len(other):
                values[k] = own[k] * other[remaining]
        mass = math.fsum(float(x) for x in values)
        require(mass > 0, 'Impossible conditioning total')
        answer.append(values / mass)
    means = np.array([np.dot(np.arange(len(p)), p) for p in answer])
    variances = np.array([np.dot((np.arange(len(p)) - m) ** 2, p) for p, m in zip(answer, means)])
    return answer, means, variances


def independent_person_sampler(probabilities, bin_indexes, total, replicates, seed, number_bins=None):
    """Person-level backward conditioning, unlike the primary bin sampler."""
    p = np.asarray(probabilities, float)
    b = np.asarray(bin_indexes, int)
    n = len(p)
    suffix = np.zeros((n + 1, total + 1), dtype=float)
    suffix[n, 0] = 1.
    for i in range(n - 1, -1, -1):
        suffix[i] = (1 - p[i]) * suffix[i + 1]
        suffix[i, 1:] += p[i] * suffix[i + 1, :-1]
    require(suffix[0, total] > 0, 'Person sampler impossible K')
    rng = np.random.Generator(np.random.PCG64(seed))
    remaining = np.full(replicates, total, dtype=np.int64)
    width = int(b.max()) + 1 if number_bins is None else int(number_bins)
    counts = np.zeros((replicates, width), dtype=np.int64)
    for i in range(n):
        chance = np.zeros(replicates)
        forced = remaining == n - i
        chance[forced] = 1.
        active = (remaining > 0) & ~forced
        k = remaining[active]
        denom = suffix[i, k]
        require(np.all(denom > 0), 'Person sampler visited impossible state')
        chance[active] = p[i] * suffix[i + 1, k - 1] / denom
        require(np.all((chance >= -1e-12) & (chance <= 1 + 1e-12)), 'Invalid conditional chance')
        selected = rng.random(replicates) < np.clip(chance, 0, 1)
        counts[:, b[i]] += selected
        remaining -= selected
    require(np.all(remaining == 0) and np.all(counts.sum(axis=1) == total), 'Person sampler did not fix K')
    return counts


def exact_linear_moments(successes, failures, weights, total):
    """Integer generating-function coefficients, normalization cancels givenK."""
    c, m, second = [1] + [0] * total, [0] * (total + 1), [0] * (total + 1)
    used = 0
    for s, f, w in zip(successes, failures, weights):
        used += 1
        for k in range(min(total, used), -1, -1):
            previous_c = c[k - 1] if k else 0
            previous_m = m[k - 1] if k else 0
            previous_second = second[k - 1] if k else 0
            second[k] = int(f) * second[k] + int(s) * (previous_second + 2 * int(w) * previous_m + int(w) ** 2 * previous_c)
            m[k] = int(f) * m[k] + int(s) * (previous_m + int(w) * previous_c)
            c[k] = int(f) * c[k] + int(s) * previous_c
    require(c[total] > 0, 'Exact linear mean conditioning impossible')
    mean = Fraction(m[total], c[total])
    return mean, Fraction(second[total], c[total]) - mean ** 2


def exact_linear_mean(successes, failures, weights, total):
    return exact_linear_moments(successes, failures, weights, total)[0]


def inclusive_linear_tails(observed, expectation):
    if observed == expectation:
        return observed, observed
    reflected = 2 * expectation - observed
    if observed > expectation:
        return reflected.numerator // reflected.denominator, observed
    return observed, -((-reflected.numerator) // reflected.denominator)


def holm(pvalues):
    result, running = [0.] * len(pvalues), 0.
    for rank, (index, p) in enumerate(sorted(enumerate(pvalues), key=lambda x: (x[1], x[0]))):
        running = max(running, min(1., (len(pvalues) - rank) * p))
        result[index] = running
    return result


def synthetic_qa():
    probs = [Fraction(1, 5), Fraction(2, 5), Fraction(1, 3), Fraction(3, 5), Fraction(1, 2)]
    bins = [0, 0, 1, 1, 2]
    weights = [-1, -1, 0, 0, 2]
    total = 2
    joint = []
    norm = Fraction()
    for bits in itertools.product([0, 1], repeat=len(probs)):
        if sum(bits) != total:
            continue
        probability = math.prod(p if bit else 1 - p for p, bit in zip(probs, bits))
        norm += probability
        row = [sum(bit for bit, b in zip(bits, bins) if b == j) for j in range(3)]
        joint.append((bits, row, probability))
    exact_margins = [np.zeros(bins.count(j) + 1) for j in range(3)]
    exact_l = Fraction()
    exact_second = Fraction()
    for bits, row, probability in joint:
        probability /= norm
        for j, count in enumerate(row):
            exact_margins[j][count] += float(probability)
        value = sum(w * bit for w, bit in zip(weights, bits))
        exact_l += probability * value
        exact_second += probability * value ** 2
    grouped = [[(1, float(p)) for p, b in zip(probs, bins) if b == j] for j in range(3)]
    margins, means, variances = independent_margins(grouped, total)
    for a, b in zip(margins, exact_margins):
        close(a, b[:len(a)], 'Toy margins vs full enumeration', atol=1e-13)
    got_l = exact_linear_mean([p.numerator for p in probs], [p.denominator - p.numerator for p in probs], weights, total)
    require(got_l == exact_l, 'Integer linear expectation vs exhaustive enumeration')
    _, exact_variance = exact_linear_moments([p.numerator for p in probs], [p.denominator - p.numerator for p in probs], weights, total)
    require(exact_variance == exact_second - exact_l ** 2, 'Integer second moment vs exhaustive enumeration')
    # A common odds multiplier cancels after conditioning on the total.
    tilted = [3 * p / (1 - p + 3 * p) for p in probs]
    tilted_grouped = [[(1, float(p)) for p, b in zip(tilted, bins) if b == j] for j in range(3)]
    tilted_margins, _, _ = independent_margins(tilted_grouped, total)
    for a, b in zip(margins, tilted_margins):
        close(a, b, 'Common odds multiplier must cancel', atol=1e-13)
    samples = independent_person_sampler([float(p) for p in probs], bins, total, 20000, QA_SEED)
    close(samples.mean(axis=0), means, 'Toy conditioned person sampling means', atol=.025)
    exact_vectors = {}
    for _, row, probability in joint:
        key = tuple(row)
        exact_vectors[key] = exact_vectors.get(key, Fraction()) + probability / norm
    for vector, probability in exact_vectors.items():
        empirical = np.mean(np.all(samples == np.asarray(vector), axis=1))
        p = float(probability)
        require(abs(empirical - p) <= 6 * math.sqrt(p * (1 - p) / len(samples)) + 2 / len(samples),
                'Toy sampler joint-vector probability differs')
    zero = independent_person_sampler([float(p) for p in probs], bins, 0, 10, QA_SEED)
    full = independent_person_sampler([float(p) for p in probs], bins, len(probs), 10, QA_SEED)
    require(np.all(zero == 0) and np.all(full == np.asarray([2, 2, 1])), 'Conditioning boundary K cases failed')
    for observed in range(-2, 5):
        lo, hi = inclusive_linear_tails(observed, exact_l)
        require(all((v <= lo or v >= hi) == (abs(Fraction(v) - exact_l) >= abs(Fraction(observed) - exact_l))
                    for v in range(-2, 5)), 'Exact reflected cutoff membership')
    close(holm([.01, .04, .03]), [.03, .06, .06], 'Holm example')
    return {'schema': 'DM_decades_independent_synthetic_QA_v1', 'status': 'PASS',
            'study_inputs_loaded': False, 'enumerated_binary_assignments': 32,
            'conditional_margins_and_exact_linear_mean': True,
            'integer_second_moment_and_joint_sampling': True,
            'common_odds_multiplier_cancellation': True,
            'independent_person_sampler': True, 'Fraction_inclusive_ties': True}


def read_rows(z, path):
    return [json.loads(line) for line in gzip.decompress(z.read('scientist_north_data_freeze_v4/outputs/' + path)).splitlines()]


def selected_people(v4_zip, institution, source):
    with zipfile.ZipFile(v4_zip) as z:
        members = read_rows(z, source + '/by_institution/' + institution + '.jsonl.gz')
        nonnobel = {p['person_id'] for p in read_rows(z, source + '/academy_excluding_official_Nobel.jsonl.gz')}
    rows = [p for p in members if p['person_id'] in nonnobel]
    rows.sort(key=lambda p: p['person_id'])
    require(len({p['person_id'] for p in rows}) == len(rows), 'Selected person repeated')
    require(all(p['hemisphere'] == 'north' and not p['person_level_DOB_analysis_hold'] for p in rows), 'Source eligibility changed')
    return rows


def id_hash(rows):
    raw = json.dumps(sorted(p['person_id'] for p in rows), ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
    return hashlib.sha256(raw.encode()).hexdigest()


def mc_tolerance(p, q):
    pooled = (p * PRIMARY_R + q * QA_R) / (PRIMARY_R + QA_R)
    return 5 * math.sqrt(max(0., pooled * (1 - pooled)) * (1 / PRIMARY_R + 1 / QA_R)) + 2 / QA_R


def audit(args):
    scope = json.loads(Path(args.scope).read_text())
    result = json.loads(Path(args.results).read_text())
    require(scope['target_order'] == TARGETS and scope['source_order'] == SOURCES, 'Frozen target/source order differs')
    require(set(result['groups']) == set(TARGETS), 'Wrong output target set')
    readback_path = ROOT / 'dm_decade_work/EXISTING_DECADE_TABLES.json'
    prior = json.loads(readback_path.read_text())
    prior_keys = {'CAS_xin': 'CAS_辛', 'NAS_water': 'NAS_壬癸水'}
    local_expected = {'CAS_xin': list(range(1890, 1970, 10)), 'NAS_water': list(range(1890, 1960, 10))}
    with np.load(args.calendar_npz, allow_pickle=False) as z:
        dates = z['dates'].tolist()
        years = z['year'].astype(np.int64)
        dm = z['DM_index'].astype(np.int64)
        day_text = z['day_pillar'].tolist()
    require(len(dates) == len(set(dates)) == 55152, 'Calendar coverage differs')
    stems = '甲乙丙丁戊己庚辛壬癸'
    require(np.array_equal(dm, np.array([stems.index(str(p)[0]) for p in day_text])), 'DayStem cache versus frozen pillar text differs')
    date_lookup = {d: i for i, d in enumerate(dates)}
    audit_groups = []
    expected_tests = {s: [] for s in SOURCES}
    for target_index, target in enumerate(TARGETS):
        definition = scope['targets'][target]
        require(definition['institution'] == ('CAS' if target_index == 0 else 'NAS'), 'Wrong target institution')
        wanted_indices = [7] if target_index == 0 else [8, 9]
        require(definition['day_stem_indices'] == wanted_indices and definition['local_decades'] == local_expected[target], 'Target or local-decade choice differs')
        indicator = np.isin(dm, wanted_indices).astype(np.int64)
        yearly = {int(y): (int(indicator[years == y].sum()), int(np.count_nonzero(years == y))) for y in np.unique(years)}
        for source_index, source in enumerate(SOURCES):
            group = result['groups'][target][source]
            rows = selected_people(args.v4_zip, definition['institution'], source)
            pinned_population = definition['populations'][source]
            require(len(rows) == pinned_population['people'] == group['people'], 'Selected source N differs')
            require(id_hash(rows) == pinned_population['person_ids_sha256'] == group['person_ids_sha256'], 'Selected source person IDs differ')
            index = np.array([date_lookup[p['analysis_DOB']] for p in rows], dtype=np.intp)
            birthyears = years[index]
            y_counts = Counter(int(y) for y in birthyears)
            observed_binary = indicator[index]
            total = int(observed_binary.sum())
            n = len(rows)
            require(total == group['target_people'], 'Observed target K differs')
            close(group['overall_observed_share'], total / n, 'Overall target rate')
            expectation = sum((number * Fraction(yearly[y][0], yearly[y][1]) for y, number in y_counts.items()), Fraction())
            close(group['calendar_expected_target_people'], float(expectation), 'Unconditional expected total')
            close(group['calendar_expected_share'], float(expectation) / n, 'Unconditional expected share')
            expected_year_counts = {str(y): {'people': count, 'success_dates': yearly[y][0], 'total_dates': yearly[y][1]}
                                    for y, count in sorted(y_counts.items())}
            require(expected_year_counts == group['calendar_year_counts'], 'Observed birthyear composition or calendar probabilities differ')
            terms_by_bin = [[] for _ in BINS]
            p_person, success_person, failure_person, b_person, weights_person = [], [], [], [], []
            for y, count in sorted(y_counts.items()):
                s, days = yearly[y]
                b = BINS.index(y // 10 * 10)
                terms_by_bin[b].append((count, s / days))
                p_person += [s / days] * count
                success_person += [s] * count
                failure_person += [days - s] * count
                b_person += [b] * count
                weights_person += [(BINS[b] - 1900) // 10] * count
            margins, mu, variance = independent_margins(terms_by_bin, total)
            close(mu.sum(), total, 'Conditional means sum to K')
            observed_counts = np.bincount((birthyears // 10 * 10 - 1830) // 10, weights=observed_binary, minlength=len(BINS)).astype(np.int64)
            bin_n = np.bincount((birthyears // 10 * 10 - 1830) // 10, minlength=len(BINS))
            require(len(group['bins']) == len(BINS), 'All16bins must be retained')
            old_bins = {x['decade']: x for x in prior['targets'][prior_keys[target]]['sources'][source]['bins']}
            for j, row in enumerate(group['bins']):
                decade = BINS[j]
                require(row['decade'] == decade and row['n'] == int(bin_n[j]) and row['observed_target_people'] == int(observed_counts[j]), 'Bin observed data differs')
                original = old_bins[decade]
                require(original['n'] == row['n'] and original['observed_count'] == row['observed_target_people'], 'Previous disclosed bin count changed')
                close(row['calendar_expected_target_people'], original['calendar_expected_count'], 'Previous bin calendar E changed')
                close(row['conditional_expected_target_people'], mu[j], 'Independent conditional bin mean')
                close(row['conditional_variance_target_people'], variance[j], 'Independent conditional bin variance')
                if row['n']:
                    close(row['observed_share'], observed_counts[j] / bin_n[j], 'Bin observed share')
                    close(row['calendar_expected_share'], original['calendar_expected_share'], 'Bin calendar share')
                    close(row['conditional_expected_share'], mu[j] / bin_n[j], 'Bin conditional share')
                else:
                    require(row['observed_share'] is None and row['calendar_expected_share'] is None and row['conditional_expected_share'] is None, 'Empty bin shares must be undefined')
                eligible = decade in definition['local_decades']
                require(row['local_test_eligible'] is eligible, 'Local eligibility differs')
                if eligible:
                    p = float(margins[j][int(observed_counts[j]):].sum())
                    close(row['conditional_upper_p'], p, 'Independent conditional local upper tail', atol=2e-10)
                    expected_tests[source].append({'target': target, 'kind': 'local', 'decade': decade, 'p': row['conditional_upper_p']})
                else:
                    require(row['conditional_upper_p'] is None, 'Small/nonselected bin cannot be a local test')
            valid = variance > 1e-12
            q_observed = float(np.sum((observed_counts[valid] - mu[valid]) ** 2 / variance[valid]))
            hetero = group['global_tests']['heterogeneity']
            close(hetero['observed_statistic'], q_observed, 'Conditional heterogeneity statistic', atol=2e-8)
            linear = group['global_tests']['linear']
            x_bin = np.array([(d - 1900) // 10 for d in BINS], dtype=np.int64)
            observed_l = int(x_bin @ observed_counts)
            exact_mean, exact_variance = exact_linear_moments(success_person, failure_person, weights_person, total)
            require(linear['observed_integer_L'] == observed_l, 'Observed integer linear total differs')
            require(linear['exact_expected_L_numerator'] == str(exact_mean.numerator) and linear['exact_expected_L_denominator'] == str(exact_mean.denominator), 'Exact conditional linear expectation differs')
            close(linear['conditional_expected_L'], float(exact_mean), 'Conditional linear expected L')
            close(linear['conditional_variance_L'], float(exact_variance), 'Conditional linear variance')
            lower, upper = inclusive_linear_tails(observed_l, exact_mean)
            require(linear['lower_inclusive'] == lower and linear['upper_inclusive'] == upper, 'Exact linear tail cutoff differs')
            person_x = (birthyears // 10 * 10 - 1900) // 10
            xbar = float(person_x.mean())
            sxx = float(np.sum((person_x - xbar) ** 2))
            raw_slope = 100 * (observed_l - xbar * total) / sxx
            calendar_l = sum(((y // 10 * 10 - 1900) // 10) * number * yearly[y][0] / yearly[y][1] for y, number in y_counts.items())
            calendar_slope = 100 * (calendar_l - xbar * float(expectation)) / sxx
            conditional_slope = 100 * (observed_l - float(exact_mean)) / sxx
            close(linear['raw_slope_pp_per_decade'], raw_slope, 'Raw slope')
            close(linear['calendar_expected_slope_pp_per_decade'], calendar_slope, 'Calendar expected slope')
            close(linear['calendar_excess_slope_pp_per_decade'], raw_slope - calendar_slope, 'Calendar excess slope')
            close(linear['conditional_excess_slope_pp_per_decade'], conditional_slope, 'Conditional excess slope')
            for label, stat in [('heterogeneity', hetero), ('linear', linear)]:
                require(stat['replicates'] == PRIMARY_R and stat['seed'] == 202611240000 + target_index * 1000 + source_index * 100, 'Primary MC configuration differs')
                close(stat['p_nominal'], (1 + stat['extreme_replicates']) / (PRIMARY_R + 1), 'Primary inclusive plus-one p', atol=1e-14)
                expected_tests[source].append({'target': target, 'kind': 'global_' + label, 'p': stat['p_nominal']})
            checks = []
            if source == 'strict':
                draws = independent_person_sampler(p_person, b_person, total, QA_R, QA_SEED + target_index * 1000, len(BINS))
                require(np.all(draws <= bin_n), 'QA draws exceed bin population')
                means_tolerance = 6 * np.sqrt(variance / QA_R) + 1e-8
                require(np.all(np.abs(draws.mean(axis=0) - mu) <= means_tolerance), 'QA sampler conditional moments differ')
                q = np.sum((draws[:, valid] - mu[valid]) ** 2 / variance[valid], axis=1)
                qp = (1 + np.count_nonzero(q >= q_observed - 1e-12 * max(1., abs(q_observed)))) / (QA_R + 1)
                simulated_l = draws @ x_bin
                lp = (1 + np.count_nonzero((simulated_l <= lower) | (simulated_l >= upper))) / (QA_R + 1)
                require(abs(float(simulated_l.mean()) - float(exact_mean)) <= 6 * math.sqrt(float(exact_variance) / QA_R) + 1e-8, 'QA sampler exact linear mean differs')
                for name, p, primary in [('heterogeneity', float(qp), hetero['p_nominal']), ('linear', float(lp), linear['p_nominal'])]:
                    tolerance = mc_tolerance(primary, p)
                    require(abs(primary - p) <= tolerance, 'Independent conditional MC p outside tolerance: ' + name)
                    checks.append({'statistic': name, 'primary_p': primary, 'independent_QA_p': p, 'replicates': QA_R, 'tolerance': tolerance})
            audit_groups.append({'target': target, 'source': source, 'people': n, 'target_people': total,
                                 'all16bin_counts_calendarE_conditional_moments_and_local_tails_checked': True,
                                 'exact_linear_expectation_and_tail_cutoffs_checked': True,
                                 'independent_person_level_MC_crosschecks': checks})
    for source in SOURCES:
        expected = expected_tests[source]
        reported = result['tests_by_source'][source]
        require(len(expected) == len(reported) == 19, 'Fixed19 test family differs')
        for e, row in zip(expected, reported):
            require(e['target'] == row['target'] and e['kind'] == row['kind'], 'Flat test order differs')
            if e['kind'] == 'local':
                require(e['decade'] == row['decade'], 'Flat local decade differs')
            close(e['p'], row['p_nominal'], 'Flat p differs')
        adjusted = holm([e['p'] for e in expected])
        close([row['p_Holm19'] for row in reported], adjusted, 'Independent Holm19 differs')
        require(all(row['reject_Holm19_0_05'] == (p <= .05) for row, p in zip(reported, adjusted)), 'Holm19 decisions differ')
    summary = {'schema': 'DM_decades_independent_QA_v1', 'status': 'PASS', 'groups': audit_groups,
               'conditional_marginal_method': 'year_grouped_binary_polynomial_powers_balanced_convolution_rebuild_others',
               'independent_sampler': 'person_level_conditional_Bernoulli_suffix',
               'strict_MC_QA_replicates': QA_R, 'strict_MC_QA_seed_base': QA_SEED,
               'fixed_Holm19_each_source_checked': True, 'old_tests_not_replaced': True,
               'hashes': {'results': sha(args.results), 'auditor': sha(__file__), 'V4': sha(args.v4_zip),
                          'calendar_pool': sha(args.calendar_npz), 'execution_receipt': sha(args.execution_receipt)}}
    Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'output': args.output, 'target_sources_checked': len(audit_groups)}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--synthetic-qa-only', action='store_true')
    for k in ['scope', 'locked-files', 'execution-receipt', 'v4-zip', 'calendar-npz', 'results', 'output']:
        p.add_argument('--' + k)
    args = p.parse_args()
    if args.synthetic_qa_only:
        result = synthetic_qa()
        if args.output:
            require(not Path(args.output).exists(), 'Synthetic output exists')
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    scope = json.loads(Path(args.scope).read_text())
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(receipt['remote_plan_and_code_verified_before_summary'] is True, 'Missing verified execution receipt')
    require(receipt['scope_sha256'] == sha(args.scope) and receipt['locked_file_manifest_sha256'] == sha(args.locked_files), 'Execution receipt pin differs')
    for path, digest in json.loads(Path(args.locked_files).read_text()).items():
        require(sha(ROOT / path) == digest, 'Locked source differs: ' + path)
    require(sha(args.v4_zip) == V4_SHA and sha(args.calendar_npz) == POOL_SHA, 'Frozen input pins differ')
    require(not Path(args.output).exists(), 'No overwrite of audit')
    audit(args)


if __name__ == '__main__':
    main()
