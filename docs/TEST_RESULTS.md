# Phase 3D test results

Test date: 2026-11-03.

## Passed

- `python3 -m unittest discover -s tests -p 'test_phase*.py'`
  - 88 tests passed across Phase 1–3C regressions and Phase 3D transport, catalog identity, canonical
    resolution, shared compatibility, authorization, bounded pagination, stale snapshots, UI state,
    feedback, and deferred Playerbot loading.
- `python3 content/build_epf.py --check`
  - Deterministic Phase 3D EPF SHA-256:
    `bccf236b5330ee579a070e377879a91843c423e90ec505414c7799da2e4820d7`.
- Playerbot AzerothCore module compile and worldserver link.
  - Temporary source/build tree, Release, GCC 15.2, C++20, `MODULES=static`, `SCRIPTS=none`, warnings enabled.
  - A retained local MySQL development snapshot supplied headers/library; no system package was changed.
  - All module translation units compiled, `libmodules.a` linked, and `worldserver` linked at 100%.
  - Generated loader/archive contain `Addmod_native_transmogScripts` and no `Addmod_transmogScripts`.
  - Final temporary worldserver SHA-256:
    `303ff61ac056e594ec31469f7d2c9c68f33aa31c21c85c8557c39f7eb9b55d8a`.
- XML parsing and `git diff --check` passed.

## Not run or not proven

No live MySQL startup, build-12340 client, Portalkeeper distribution, PTR deployment, NPC interaction,
addon-channel delivery, observer synchronization, relog/restart, equipment swap, ownership transfer,
weapon edge case, high-playerbot load, or rollback was exercised. These remain manual tasks in
`PHASE3D_PTR_VALIDATION.md`; none are reported as passed.

The suite is primarily source-contract and executable model coverage. Compile/link proves the inspected
core hook signatures and C++ integration, not client runtime or network delivery. Weapon compatibility and
ownership-transfer behavior remain implemented but incompletely validated on PTR.

No commit, push, database/client activation, PTR/production deployment, Portalkeeper or Content Manager
change, standalone addon, custom opcode, or `mod-transmog` integration was performed.

Status: **Phase 3D implementation and local automated/build validation are complete; manual PTR validation
is a separate milestone.**
