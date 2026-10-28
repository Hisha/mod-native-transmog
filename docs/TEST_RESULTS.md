# Phase 1 test results

Test date: 2026-10-28.

## Passed automated checks

- `python3 content/build_epf.py --check`
  - Deterministic package verified.
  - Current SHA-256: `f524171537a6021610ccb1e3c16f240d679c70abbee6bd052d90b9cdf5170eb3`.
- `python3 -m unittest tests/test_phase1.py`
  - 7 tests passed.
  - Covers Schema 3 declaration, pinned stock TOC, load ordering, no-addon/no-raw-TOC rules, XML parsing, preview behavior markers, catalog determinism, configuration, module registration, exact EPF members, timestamps, and byte-for-byte rebuild repeatability.
- `python3 tests/verify_catalog.py /home/smithkt/aicode_folder/azerothcore-wotlk/data/sql/base/db_world/item_template.sql`
  - All 16 catalog entries exist in the inspected build-12340 baseline and have an allowed inventory type for their declared browser slot.
- `python3 /home/smithkt/aicode_folder/azerothcore-wotlk/apps/codestyle/codestyle-cpp.py`
  - All AzerothCore C++ codestyle checks passed.
- Isolated Playerbot CMake/module build probe:
  - Configured against Playerbot core revision `8a4e76eac8c4ccebf547113afe7b51d6c3e91641` with `SCRIPTS=none`, `MODULES=static`, and the environment's existing MySQL development files.
  - CMake discovered `mod-native-transmog`, registered `mod_native_transmog.conf`, generated its static loader, compiled both module source files, and linked `libmodules.a` successfully.
  - The probe used a temporary symlinked source view and did not modify or install into the core checkout.

`git diff --check` also passed.

## Not performed

- No cumulative PTR MPQ was built or published because the task environment did not identify the PTR's configured content-manager command, baseline inputs, or publication target.
- No Windows client, Portalkeeper launch, in-game rendering, or existing `mod-transmog` coexistence test was performed.
- No production server, database, configuration, executable, or patch channel was touched.

Status: **implemented and awaiting PTR validation**, not fully completed in-game.
