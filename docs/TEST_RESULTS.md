# Phase 3D test results

Test date: 2026-11-04.

## Passed

- `python3 -m unittest discover -s tests -p 'test_phase*.py'`
  - 92 tests passed across Phase 1–3C regressions and Phase 3D transport, equipment-triggered collection,
    catalog identity, canonical resolution, shared compatibility, authorization, bounded pagination,
    stale snapshots, Lua 5.1 remainder compatibility, UI state, feedback, and deferred Playerbot loading.
- `python3 content/build_epf.py --check`
  - Deterministic Phase 3D EPF SHA-256:
    `b3076389bd7b524b5b043bc89e130a307cbe5f2fff82620efcbc43a0bf5acca9`.
- FrameXML compatibility checks.
  - `NativeTransmogFrame.xml` parsed successfully.
  - `NativeTransmogFrame.lua` compiled with the available Lua 5.5 runtime; source-contract tests confirm
    Lua 5.1-compatible `%` positioning arithmetic and reject `math.mod`. An exact Lua 5.1 binary was not
    available in this environment.
- Playerbot AzerothCore module compile and worldserver link.
  - Retained temporary source/build tree, Release, GCC 15.2, C++20, `MODULES=static`, `SCRIPTS=none`.
  - A retained local MySQL development snapshot supplied headers/library; no system package was changed.
  - All module translation units compiled, `libmodules.a` linked, and `worldserver` linked at 100%.
  - Generated loader/archive contain `Addmod_native_transmogScripts` and no `Addmod_transmogScripts`.
  - Final temporary worldserver SHA-256:
    `760c2c5e2608a690342f49830af972cb0e12cc93052b3fbb0f33d92633d90c15`.
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
