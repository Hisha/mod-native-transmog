# Phase 4A test results

Test date: 2026-11-04.

## Passed

- Focused Phase 4A suite: `python3 -m unittest tests.test_phase4a`
  - 21 tests passed for all 14 slots, shared filtering/compatibility, explicit hidden state, migration defaults,
    authorization, empty collections, state transitions, item-GUID persistence, weapon policy/config changes,
    pagination, collection isolation, physical-item invariants, preview, and transport restrictions.
- Full module suite: `python3 -m unittest discover -s tests -p 'test_phase*.py'`
  - 113 tests passed, including all Phase 1–3D regressions.
- Existing catalog fixture against the Playerbot `item_template.sql`:
  - `python3 tests/verify_catalog.py <PLAYERBOT>/data/sql/base/db_world/item_template.sql` passed.
- EPF deterministic build/check/rebuild:
  - Four members; repeated byte-for-byte rebuild passed.
  - SHA-256: `30785a577504d17eedbf09725b00ec7b7d92c1d5605a5eb61d6e46e4d5c9ca50`.
- FrameXML/Lua validation:
  - `NativeTransmogFrame.xml` parsed successfully.
  - `NativeTransmogFrame.lua` compiled with the available Lua 5.5 runtime; source-contract tests retain the
    Lua 5.1-compatible syntax/arithmetic checks. An exact Lua 5.1 runtime was not available.
- Playerbot AzerothCore Release compile/link:
  - Inspected Playerbot core revision `8a4e76eac`, GCC 15.2, C++20, `MODULES=static`, `SCRIPTS=none`.
  - All module translation units compiled, `libmodules.a` linked, and `worldserver` linked at 100%.
  - Binary exports `Addmod_native_transmogScripts` and no `Addmod_transmogScripts`.
  - Worldserver SHA-256: `98938fc4308a2a86f779a49fae898946480117b0272bd4c3eb9d0468dd8103b9`.
- `git diff --check` passed.

## Not run or not proven

No live MySQL updater/startup, build-12340 client, Content Manager activation, Portalkeeper distribution, PTR
deployment, NPC interaction, addon-channel delivery, observer synchronization, relog/restart, equipment swap,
ownership transfer, enchant rendering, mirror image, weapon gameplay, or rollback was exercised. Client rendering
is therefore not marked verified for any slot. Follow `PHASE4A_PTR_VALIDATION.md` and record evidence.

The Hide render path is grounded in the inspected core: `Player::SetVisibleItemSlot(nullptr)` represents an empty
visible slot with public entry `0`; the module writes that value only after the core writes the real item/enchant
fields, and the mirror-image display hook accepts `0`. This proves compile-time/core-protocol integration, not the
behavior of every WoW 3.3.5a client model/race/gender combination.

No deploy, database update, client publication, commit, push, Portalkeeper modification, standalone addon, custom
opcode, new external project dependency, or `mod-transmog` integration was performed.

Status: **Phase 4A implementation and local automated/build validation are complete; live PTR rendering and
deployment validation remain separate and unverified.**
