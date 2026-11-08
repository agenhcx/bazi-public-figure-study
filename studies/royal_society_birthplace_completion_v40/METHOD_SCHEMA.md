# V40 unchanged V36 method: structural fact schema

This document clarifies the structure used to carry the separately preregistered `uk-geography-canonical-community-reference-pilot-v1` evidence. It does not relax the preregistration's actual-source, person-binding, exact-DOB, place-binding, conflict, whole-region or retrieval requirements. It does not apply retrospectively to previous contexts or clear prior holds.

A current accepted fact includes the ordinary record/native-DOB/authority/frozen-place identity fields, `source_grade: S3`, `method_id`, `proof_mode`, `observed_source_full_name`, `source_birthdate` equal to the unchanged native ISO DOB, an actual exact-day `source_birthdate_precision` description, `identity_review`, `place_binding_review`, `geographic_basis`, source URL/locator and a nonempty `proof_chain`. The ISO date field expresses agreement with an actually displayed source DOB for identity only. It does not validate or upgrade native DOB evidence; actual formatted dates and available rank/calendar/precision metadata must be retained without invented completeness claims.

Allowed proof modes are exactly:

- `direct_born_region_in_actual_canonical_person_body`
- `explicit_person_born_place_hyperlink_then_actual_target_place_region`
- `actual_person_P19_entity_then_actual_P131_admin_chain_to_whole_region`

Each proof-chain observation carries:

| Field | Meaning |
|---|---|
| `source_url` | Actually acquired source node URI |
| `source_node_label` | Observed node label |
| `edge_property` | Actual born-place, hyperlink, direct-region or structured property assertion |
| `tool_ref` | Actual acquisition reference |
| `locator` | Field/line locator for the edge |
| `acquisition_role` | Worker/root source-acquisition role, with limits |
| `target_kind` | `entity` or `literal` |
| `target_label` | Nonempty observed target label |
| `target_uri` | Actually observed entity URI; null for a literal region |

The proof chain contains geographic edges only. Name, DOB and distinctive career evidence stays in separate fact fields. Nonterminal chain targets must be actual entities, and the next acquired source must identify the preceding target; source QA checks the actual identity and any observed redirects. A linked-place proof has at least two observations and an actual first born-place entity URI. Its final place-body country/region statement may be a literal such as England with null URI if no country hyperlink was observed. No URI is invented to fill that terminal field. A P19/P131 proof requires actual entity targets throughout, an observed P19 edge and at least one observed P131 administrative edge. All intermediate links must actually be acquired and recorded.

Source QA verifies that place targets are geographic settlements or administrative regions and that the path establishes the subject's birthplace rather than an employer, photo, family or other location. It also verifies that the terminal whole region meets the existing hemisphere-extent rule. Generic UK P17 alone does not substitute for the required constituent-region evidence, and no coordinate centroid substitutes for a whole region. The runtime guards structural completeness; documentary QA establishes actual source semantics, compatible lifespan, exact native-name/date binding, geographic path continuity, granular street uncertainty and absence of observed contradictions. No source or entity IDs are written into native country/QID/coordinate fields.

V37 reuses the byte-exact V36 method preregistration; audit/method_application_scope.json separately freezes its six-record application, baseline, budgets and unchanged rules before retrieval. Every current fact must carry the exact base method SHA256 and the current scope SHA256. The new runtime checks both files against their frozen hashes, the scope metadata and the fact bindings. V36’s original six IDs remain historical; they are not rewritten to the V37 six IDs. This application is not a new admission-method exception.

V38 application and historical file boundary: audit/method_application_scope.json remains the byte-exact V37 legacy application file (ae080b06f8abad9ed7575783486795c977e44ce5e5024bfa2096e16816a44d94), required by unchanged apply_v37_geography during reconstruction. The current scope is separately frozen at audit/method_application_scope_v38.json (bd7540715a6b4649ffe79371e38ee2b650bd0176013fbb5418efa02b8995fad0). Every V38 fact carries method_application_scope_sha256 plus the unchanged base method_preregistration_sha256. apply_v38_geography verifies the actual base file, current scope bytes/metadata and fact hashes. No ROOT monkeypatch or old gate relaxation is used; historical functions and constants stay literal. This is the unchanged V36 method, with a V38 scope extension only.

V39 application and historical file boundary: audit/method_application_scope.json remains the byte-exact V37 legacy scope (ae080b06f8abad9ed7575783486795c977e44ce5e5024bfa2096e16816a44d94); audit/method_application_scope_v38.json remains the byte-exact V38 scope (bd7540715a6b4649ffe79371e38ee2b650bd0176013fbb5418efa02b8995fad0). Unchanged apply_v37_geography and apply_v38_geography read those respective runtime paths during reconstruction. The current scope is separately frozen at audit/method_application_scope_v39.json (cc12b3159a035064dbde6a35e0778642fdb25d988e9e399617b216062127b17e). Every V39 fact carries method_application_scope_sha256 plus the unchanged base method_preregistration_sha256. apply_v39_geography verifies actual base file bytes, current scope bytes and metadata, and both fact hashes. All historical functions, constants and scopes remain literal; main_v39 and write_csv_v39 are additive V39 entry points. No ROOT monkeypatch or old gate relaxation is used. The V36 admission method is reused without amendment or new admission exception.

V40 application and historical file boundary: audit/method_application_scope.json remains the byte-exact V37 legacy scope (ae080b06f8abad9ed7575783486795c977e44ce5e5024bfa2096e16816a44d94); audit/method_application_scope_v38.json remains the byte-exact V38 scope (bd7540715a6b4649ffe79371e38ee2b650bd0176013fbb5418efa02b8995fad0); audit/method_application_scope_v39.json remains the byte-exact V39 scope (cc12b3159a035064dbde6a35e0778642fdb25d988e9e399617b216062127b17e). Unchanged apply_v37_geography, apply_v38_geography and apply_v39_geography read those respective runtime paths during reconstruction. The current scope is separately frozen at audit/method_application_scope_v40.json (b44c66bc0d7883aeef9650578d0b339a65b563942da3fe72976b05c0094cc1fc). Every V40 fact carries method_application_scope_sha256 plus the unchanged base method_preregistration_sha256. apply_v40_geography verifies actual base file bytes, current scope bytes and metadata, and both fact hashes. All 53 historical functions, 112 assignments and old scopes remain literal; load_v39, main_v40 and write_csv_v40 are additive V40 entry points. No ROOT monkeypatch or old gate relaxation is used. The V36 admission method is reused without amendment or new admission exception.
