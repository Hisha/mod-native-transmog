# Phase 3A test results

Test date: 2026-10-28.

## Passed

- `python3 content/build_epf.py --check`
  - The unchanged Phase 1/2 protected-FrameXML EPF remains deterministic.
  - SHA-256: `4951f0c61776f1ec00992805f77a4c674cea9d4d858d5f91ed60064ee0cf7b48`.
- `python3 -m unittest tests/test_phase1.py tests/test_phase2.py tests/test_phase3a.py`
  - 29 tests passed.
  - Phase 1/2 regression contracts remain covered.
  - Phase 3A covers idempotent schema/constraints, authenticated ownership, account and character scope behavior, scope switching without deletion/merge, repeated acquisitions, first-provenance preservation, shared visuals, incompatible categories, cross-class independence, eligibility/missing data, acquisition hooks, synchronous persistence, reopen/relogin behavior, query filtering/order, bounded RBAC diagnostics, and an indexed 10,000-row collection model.
- Playerbot compile and link against revision `8a4e76eac8c4`.
  - CMake detected `mod-native-transmog` as a static module.
  - Release build used `MODULES=static`, `SCRIPTS=none`, GCC 15.2, and C++20.
  - `NativeTransmogCollection.cpp`, the Phase 1/2 module sources, and the generated module loader compiled into `libmodules.a`.
  - `worldserver` linked successfully at 100%.
  - The host lacked installed MySQL development files, so `libmysqlclient-dev` and `libmysqlclient24` were downloaded and extracted under `/tmp` only; no system package was installed.
- AzerothCore C++ codestyle checks passed for the module changes.
- `git diff --check` passed.

## Scope of these results

The Python tests combine the repository's established static integration contracts with an executable SQLite persistence model. The model validates ownership and database semantics but is not a live MySQL/worldserver integration test. The worldserver result proves Playerbot compile/link compatibility with modules enabled; scripts were disabled to keep the verification build bounded and do not change module hook interfaces or linkage.

## Not performed

- No PTR migration, live MySQL write, worldserver startup, item acquisition, relog/restart persistence, or GM command execution.
- No Windows client, Portalkeeper launch, MPQ publication, or in-game Phase 3A validation.
- No live `mod-transmog` coexistence/data comparison.
- No production/PTR database, configuration, executable, or deployment was changed.
- The AzerothCore SQL linter could not complete because it requires fetching `origin/master` and this managed workspace exposes `.git/FETCH_HEAD` read-only. Schema-specific automated checks and `git diff --check` passed.

Status: **Phase 3A implementation, automated checks, and Playerbot compile/link are complete; PTR validation remains required.**
