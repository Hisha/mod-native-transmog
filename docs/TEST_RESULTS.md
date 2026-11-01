# Phase 3C test results

Test date: 2026-11-01.

## Passed

- `python3 content/build_epf.py --check`
  - The existing protected-FrameXML EPF remains unchanged and deterministic.
  - SHA-256: `4951f0c61776f1ec00992805f77a4c674cea9d4d858d5f91ed60064ee0cf7b48`.
- `python3 -m unittest tests/test_phase1.py tests/test_phase2.py tests/test_phase3a.py tests/test_phase3b.py tests/test_phase3c.py`
  - 62 tests passed.
  - Phase 3C coverage includes authenticated authority, collection entitlement, class/race/skill/spell and proficiency policy, armor and weapon compatibility, independent handedness settings, item-instance upsert/removal, lifecycle hook contracts, persistence-before-render ordering, visible-field and mirror-image integration, RBAC diagnostics, sole-table ownership, and all Phase 1-3B regressions.
- `python3 tests/verify_catalog.py /home/smithkt/aicode_folder/azerothcore-wotlk/data/sql/base/db_world/item_template.sql`
  - All 16 deterministic preview-catalog entries resolved with the expected inventory types.
- Actual Playerbot worldserver compile/link against branch `Playerbot`, revision `8a4e76eac8c4`.
  - An isolated source/build tree under `/tmp` contained only `mod-native-transmog`; `mod-transmog` was absent.
  - Release build used `MODULES=static`, `SCRIPTS=none`, GCC 15.2, and C++20.
  - CMake reported `phase-3c-appearance-application`; every module translation unit compiled into `libmodules.a` and `worldserver` linked at 100%.
  - Generated `ModulesLoader.cpp`, archive symbols, and the isolated module tree contain `Addmod_native_transmogScripts` and no `Addmod_transmogScripts`.
  - Final worldserver SHA-256: `065fbc8cfb1083f7a9e1d2660e0163f6bc6561b86400e5422a87983fb8719a5a`.
  - The host runtime lacked system MySQL development headers. CMake used an existing local MySQL development snapshot only; no package, core checkout, PTR, or system installation was changed.
- AzerothCore C++ codestyle checks passed.
- `git diff --check` passed.

## Scope and limitations

The Python suite uses the repository's established static integration and executable SQLite model approach. The compile proves the real Playerbot hook signatures, field/constants, database transaction API, command parser signatures, module loader, C++20 compilation, and final worldserver linkage.

No live MySQL server, worldserver startup, client, observer, mirror image, item transfer, relog, Playerbot population, or PTR environment was exercised. Those remain mandatory in [the Phase 3C PTR validation plan](PHASE3C_PTR_VALIDATION.md). The core hooks needed by Phase 3C were present; no core modification was required. The documented live-config refresh limitation remains: disabling application does not proactively rewrite every online player's already-published visible fields until restart/relog/equipment refresh.

No PTR or production deployment, database migration, Portalkeeper change, commit, or push was performed.

Status: **Phase 3C implementation, automated checks, sole-writer isolation inspection, and Playerbot worldserver compile/link are complete; authorized PTR validation remains required.**
