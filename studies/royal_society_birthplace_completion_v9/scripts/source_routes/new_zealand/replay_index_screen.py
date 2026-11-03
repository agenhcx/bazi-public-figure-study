"""Replay a bounded official NZ obituary index projection screen; no network."""
import hashlib
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent


def normalize(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', value.lower()).split())


def source_variants(name):
    # Parenthetical nickname may be absent from the native full name.
    name = re.sub(r'^(?:Sir|Dame|Professor|Dr)\s+', '', name, flags=re.I)
    return {normalize(name), normalize(re.sub(r'\([^)]*\)', '', name))}


def native_full_name(row):
    authorized = row.get('source_authorised_full_name', '')
    if not authorized:
        return row['name']
    parts = [part.strip() for part in authorized.split(';')]
    # Native authority format is normally "Surname; [Title;] Givens (life)".
    # Extract givens from the authority itself, because row['name'] often holds
    # given names alone. Royal names may already be complete in the first part.
    if '(' in parts[0]:
        return re.sub(r'\s*\([^)]*\).*$', '', parts[0]).strip()
    surname = parts[0]
    given_parts = [part.split('(', 1)[0].strip() for part in parts[1:] if '(' in part]
    if len(given_parts) == 1 and given_parts[0]:
        return given_parts[0] + ' ' + surname
    raise ValueError('Unparsed native authorized full name: ' + authorized)


def main():
    projection = json.loads((ROOT / 'web_retrieval_projections.json').read_text())
    text = projection['discovery']['content'][0]['text']
    section = text.split('Obituaries of Fellows (', 1)[1].split('--------------------------------------------------------------------------------', 1)[0]
    entries = [
        {'source_name': name.strip(), 'source_lifespan': years.strip()}
        for name, years in re.findall(r'  \* ## ([^\n]+)\n\n([^\n]+)', section)
    ]
    unknowns = json.loads((ROOT / 'frozen_unknowns.json').read_text())
    name_matches = []
    name_birth_year_matches = []
    surname_birth_year_matches = []
    for entry in entries:
        source_years = re.findall(r'\d{4}', entry['source_lifespan'])
        source_birth_year = source_years[0] if source_years else None
        for row in unknowns:
            target = native_full_name(row)
            exact_name = normalize(target) in source_variants(entry['source_name'])
            native_year = row['dob'][:4]
            item = {'source': entry, 'target': row, 'native_full_name': target}
            if exact_name:
                name_matches.append(item)
                if source_birth_year == native_year:
                    name_birth_year_matches.append(item)
            surname = row['source_authorised_full_name'].split(';')[0] if row['source_authorised_full_name'] else row['name'].split()[-1]
            if normalize(surname) in normalize(entry['source_name']).split() and source_birth_year == native_year:
                surname_birth_year_matches.append(item)
    report = {
        'source_directory_entries': len(entries),
        'frozen_unknown_rows': len(unknowns),
        'window_unknown_rows': sum(1835 <= int(row['dob'][:4]) <= 1985 for row in unknowns),
        'exact_normalized_full_name_matches': name_matches,
        'exact_normalized_full_name_plus_native_birth_year_matches': name_birth_year_matches,
        'surname_plus_native_birth_year_possible_matches': surname_birth_year_matches,
        'identity_acceptances': 0,
        'canonical_name_method': 'Past rows use source_authorised_full_name surname plus authority givens; complete royal names remain intact. Current rows lacking that field use their frozen full name.',
        'canonical_names_from_native_authority': sum(bool(row.get('source_authorised_full_name')) for row in unknowns),
        'canonical_names_from_current_frozen_name': sum(not bool(row.get('source_authorised_full_name')) for row in unknowns),
        'note': 'Index screening only. No biography body identity was accepted, no DOB or other formal identity field was modified.',
        'projection_capture_kind': 'web-retrieval-text projection; not original HTTP bytes',
        'projection_sha256': hashlib.sha256((ROOT / 'web_retrieval_projections.json').read_bytes()).hexdigest(),
    }
    (ROOT / 'replay_screen_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
