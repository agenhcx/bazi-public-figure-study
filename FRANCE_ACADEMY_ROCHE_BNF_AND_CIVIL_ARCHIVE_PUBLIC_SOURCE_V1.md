# France Academy: Roche civil birth register and BnF authority audit

Checkpoint: 2026-10-18 UTC. PUBLIC SOURCES ONLY, prior to the study freeze; no accepted DOB, full French Academy membership, or BaZi variables.

## Jean Roche (CTHS 2067): birth date remains unresolved

| Explicit date | Publication | URL |
|---|---|---|
| 1901-01-14 | Bibliothèque nationale de France, person authority | https://catalogue.bnf.fr/ark:/12148/cb12252855s |
| 1901-01-14 | École pratique des hautes études, biographical record | https://prosopo.ephe.psl.eu/jean-roche |
| 1901-01-14 | Contemporary Le Monde appointment article, 1961-09-07 | https://www.lemonde.fr/archives/article/1961/09/07/m-jean-roche-nouveau-recteur-de-l-academie-de-paris_2275367_1819218.html |
| 1901-01-14 | INSEE deceased persons as indexed by matchID (source claim) | https://deces.matchid.io/id/odZACBNto8ct |
| 1901-02-14 | Collège de France original institutional biography | https://www.college-de-france.fr/fr/personne/jean-roche |
| 1901-02-14 | CTHS frozen biographical source | https://cths.fr/an/savant.php?id=2067 |

The original full name is Jean Casimir Henri Hilaire Roche. The BnF catalogue expressly cautions not to confuse him with Jean Roche (1908–1979), also a doctor. The BnF notice cites CTHS, matchID, Le Monde and Who's Who, so BnF and its referenced sources are not four independent observations. The 1961 Le Monde report is a useful historically earlier birth-date statement. Do NOT change the frozen February date by majority vote.

**Precise new reference**: EPHE lists the French Academy of Sciences 1989 member-only biographical directory, pp. 210–211, in Jean Roche's bibliography. It also references a 1963 original "Exposé de titres et travaux de J. Roche" in the Academy's archives. These are high-priority first-party *research leads*, not opened original Academy sources. French full-member election evidence remains outside accepted primary-cohort counts.

The official Vaucluse archive says births before 1922 for Sorgues are digitized: https://memento.vaucluse.fr/aide-a-la-recherche/genealogie/je-cherche-un-acte-de-bapteme-naissance-mariage-sepulture-deces-ou-divorce . Its linked catalogue https://earchives.vaucluse.fr/archives/classification-scheme returned HTTP 403 to automated web access on 2026-10-18. No original birth-register page, shelfmark or act number was obtained. Avoid access-control circumvention. A lawful normal-browser inspection should locate Sorgues / État civil / Naissances / 1901 and verify January 14 against February 14 with name, parents and archival page identifier; do not invent a direct link. Sorgues local historians also mention his father Dr. Gaston Roche (https://etudessorguaises.fr/index.php/scolaires/181-pierre-gavaudan-jeune-chercheur) but give no exact DOB.

## Systematic source-only BnF pilot

Program: scripts/france_academy_bnf_authority_pilot_v1.py.

Inputs are ONLY the pinned CTHS 562 DOB candidates, strict CTHS-Wikidata identity crosswalk, and 17-person 1989 member-only directory bibliography subset. For each uniquely proposed Wikidata QID, inspect its P268 BnF identifier before fetching the exact BnF person authority. Source-preserving SHA-256 of the original authority HTML is retained locally. Date claims are only compared against the original CTHS claim and not accepted. A BnF person authority does NOT prove an Academy membership election. Bibliography flags record potential CTHS/matchID dependence. Requests are spaced at least 1.1 seconds; access errors are explicit, and a blocked authority endpoint terminates that sample.

Expected primary outputs under gitignored local_runs/france_academy_bnf_authority_pilot_v1: summary.json; person_source_audit_v1.csv; bnf_authority_source_leads_v1.csv.

Windows PowerShell single-line commands from C:\chenxi\bazi_project\1986wiki:

    git pull --ff-only

    python .\scripts\france_academy_bnf_authority_pilot_v1.py --fixture-check

    python .\scripts\france_academy_bnf_authority_pilot_v1.py --dry-run --limit 5

After confirming the bounded first live pilot and legal public endpoint, and only then:

    python .\scripts\france_academy_bnf_authority_pilot_v1.py --limit 5

Do not extrapolate pilot DOB coverage to the entire French Academy. No historical CTHS source snapshots overwritten. No BaZi-derived outcomes or hypothesis modifications. final_exact_dob_accepted=0, final_full_member_accepted=0, bazi_variables_computed=0.
