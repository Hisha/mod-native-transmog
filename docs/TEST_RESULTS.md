# Phase 2 test results

Test date: 2026-10-28.

## Passed

- `python3 content/build_epf.py --check`
  - Deterministic four-member EPF verified.
  - SHA-256: `4951f0c61776f1ec00992805f77a4c674cea9d4d858d5f91ed60064ee0cf7b48`.
- `python3 -m unittest tests/test_phase1.py tests/test_phase2.py`
  - 17 tests passed.
  - Phase 1 coverage: Schema 3/TOC ordering, no-addon contract, XML/load contract, preview markers, catalog fixture, configuration/loader, and byte-for-byte EPF rebuilding.
  - Phase 2 coverage: registration-only SQL ownership, managed creature declaration, symbolic V1 runtime resolution, absence of fixed entry `900100` in SQL/C++, entry/spawn scopes and resolution order, persistence paths, loaded template/model guards, RBAC, interaction checks, additive hooks, transport, debug separation, cleanup hooks, and config defaults.
- Production `mod-content-manager` `ContentPackage` parser against the regenerated EPF.
  - Passed as Schema 3 with one `dedicated-transmogrifier` managed creature copied from stock template `28699`.
- `python3 tests/verify_catalog.py /home/smithkt/aicode_folder/azerothcore-wotlk/data/sql/base/db_world/item_template.sql`
  - All 16 catalog items exist and match allowed inventory types.
- `git diff --check`
  - Passed.

## Scope of these results

The Python Phase 2 tests are static integration-contract tests consistent with this repository's existing test conventions; they do not replace a running world database, packet capture, or WoW client test. The production parser check validates the EPF schema contract, not allocation/apply against a realm database.

## Not performed

- No PTR world migration, worldserver startup, NPC spawn, gossip/vendor/quest interaction, packet observation, or restart-persistence test.
- No full Playerbot CMake compile was rerun after the Content Manager allocation correction.
- No Windows client, Portalkeeper launch, cumulative PTR MPQ publication, or in-game Phase 2 validation.
- No live `mod-transmog` coexistence/data comparison.
- No production server, database, configuration, executable, or patch channel was touched.

Status: **Phase 2 architectural correction implemented and package-validated; full server build and PTR validation remain required.**
