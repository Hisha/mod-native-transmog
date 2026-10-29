# Phase 3B test results

Test date: 2026-10-29.

## Passed

- `python3 content/build_epf.py --check`
  - The Phase 1/2 protected-FrameXML EPF remains unchanged and deterministic.
  - SHA-256: `4951f0c61776f1ec00992805f77a4c674cea9d4d858d5f91ed60064ee0cf7b48`.
- `python3 -m unittest tests/test_phase1.py tests/test_phase2.py tests/test_phase3a.py tests/test_phase3b.py`
  - 50 tests passed.
  - Phase 3B coverage includes selectable, guaranteed, and mixed rewards; empty/invalid/missing rewards; cross-class independence; duplicate identities; already-owned first provenance; repeat idempotency; account and character scope; post-reward-only hook contracts; preview read-only behavior; execution/rerun behavior; current-definition semantics; reliable rewarded-history selection; RBAC; bounded 25-quest batches; multi-row batch persistence; and Phase 1–3A regression contracts.
- Real Playerbot compile and link against revision `8a4e76eac8c4` (`Playerbot`).
  - CMake detected `mod-native-transmog` as a static module and reported `phase-3b-quest-reward-collections`.
  - Release build used `MODULES=static`, `SCRIPTS=none`, GCC 15.2, and C++20.
  - `NativeTransmogCollection.cpp`, `NativeTransmogQuestCollection.cpp`, the Phase 1/2 sources, and the generated module loader compiled into `libmodules.a`.
  - `worldserver` linked successfully at 100%.
  - The host's MySQL runtime lacked development headers. `libmysqlclient-dev` and `libmysqlclient24` were downloaded and extracted under the disposable `/tmp` build tree only; no system package was installed.
- AzerothCore C++ codestyle checks passed for the repository changes.
- `git diff --check` passed.

## Scope of these results

The Python suite follows the repository's established static integration and executable SQLite persistence-model approach. It does not simulate a live worldserver or MySQL transaction. The Playerbot build proves the actual hook signatures, command table, quest structures, database API use, module linkage, and C++20 compatibility on the inspected target revision.

## Not performed

- No PTR migration, live MySQL write, worldserver startup, quest completion, backfill command, relog/restart, Playerbot population load, or in-game collection query was executed.
- No Windows client, Portalkeeper launch, MPQ publication, or EPF deployment was changed.
- No live `mod-transmog` coexistence/data comparison was performed.
- No production/PTR database, config, executable, or deployment was changed.
- The AzerothCore SQL codestyle tool could not complete because it unconditionally fetches `origin/master` and this managed repository exposes `.git/FETCH_HEAD` read-only. The migration has dedicated idempotency assertions, and `git diff --check` passed.

Status: **Phase 3B implementation, automated checks, and Playerbot compile/link are complete; PTR validation remains required.**
