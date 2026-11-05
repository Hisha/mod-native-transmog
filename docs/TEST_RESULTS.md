# Test results

## Phase 5A

Test date: 2026-11-05.

### Passed

- Focused set-catalog suite: `python3 -m unittest tests.test_phase5a`
  - 17 tests passed for authoritative discovery, verified Judgement/Tier 9 fixtures, class/race filtering, variant
    slot grouping, composite-identity progress, source resolution/unknown fallback, recursion bounds, pagination,
    protocol validation, missing-piece presentation, native tooltips, full-set preview, and application separation.
- Full module suite: `python3 -m unittest discover -s tests -p 'test_*.py'`
  - 166 tests passed, including all Phase 1–4C regressions.
- Installed AzerothCore base-data audit:
  - 390 explicitly class-backed gameplay-set candidates; 102 paladin-visible candidates.
  - Source coverage at visual-slot grouping: 312 complete, 5 partial, 73 unresolved.
  - ItemSet 217 resolves to eight Judgement slots; ItemSet 875 collapses twenty Tier 9 item variants to five slots.
- Lua/FrameXML validation:
  - `NativeTransmogFrame.lua` returned `0` from `luaL_loadbuffer` using the local x86_64 Lua 5.1 runtime.
  - `NativeTransmogFrame.xml` parsed successfully with Python `xml.etree.ElementTree`.
- Playerbot AzerothCore revision `8a4e76eac8c4` Release worldserver compiled and linked successfully with the
  Phase 5A module sources.
- Deterministic EPF verification:
  - Four members; `python3 content/build_epf.py --check` passed.
  - SHA-256: `14b2f0a953447bca38f2550b5181059aca9ddb6ed530968b2d3c618997eefe19`.
- `git diff --check` passed.

### Not run or not proven

No build-12340 client, live world/character database, Content Manager activation, Portalkeeper publication, PTR
deployment, race/faction matrix, tooltip cache behavior, every multi-source item, or live DressUpModel combination
was exercised. Startup counts must be confirmed from the deployed realm log because the live DBC may differ from
the installed base-data audit. No deployment, database mutation, commit, or push was performed.

Status: **Phase 5A implementation and local automated/build validation are complete; live PTR behavior remains
separate and unverified.**

## Phase 4C

Test date: 2026-11-05.

### Passed

- Focused collection-notification suite: `python3 -m unittest tests.test_phase4c.PhaseFourCNotificationTests`
  - 5 tests passed for first unlock, duplicate/re-equip suppression, disabled collection, failed persistence,
    historical backfill suppression, account/character namespaces, centralized notification placement, and batch
    quest collection.
- Focused tooltip/synchronization suite: `python3 -m unittest tests.test_phase4c.PhaseFourCTooltipTests`
  plus `tests.test_phase4c.PhaseFourCTooltipLifecycleRegressionTests`
  - 16 tests passed for canonical source-name resolution, original/applied/hidden text, initial construction, native
    tooltip rebuilds, idempotent append behavior, recursion protection, exact CharacterFrame-owner filtering,
    equipment swaps, relog/`/reload` synchronization, unrelated tooltips, changed-slot pushes, and relic wording.
- Full module suite: `python3 -m unittest discover -s tests -p 'test_phase*.py'`
  - 149 tests passed, including all Phase 1–4B regressions.
- Existing catalog fixtures passed against Playerbot `item_template.sql` for all head, shoulder, chest, main-hand,
  and off-hand cases.
- Lua/FrameXML validation:
  - `NativeTransmogFrame.lua` parsed successfully through the local x86_64 Lua 5.1 shared runtime using
    `luaL_loadbuffer`.
  - `NativeTransmogFrame.xml` parsed successfully with Python `xml.etree.ElementTree`.
- Worldserver was not rebuilt for the 2026-11-05 fix because no C++ or server transport changed. The earlier Phase 4C
  Playerbot Release compile/link result remains historical evidence, not a new validation result for this fix.
- Deterministic EPF verification:
  - Four members; two builds were byte-for-byte identical and `python3 content/build_epf.py --check` passed.
  - SHA-256: `14cf2ca1044ac434134dbe9fad0fb5699db1af13ba66e1ca1d0551ca749a06fe`.
- `git diff --check` passed.

### Not run or not proven

No build-12340 client, live MySQL persistence failure, live account-wide concurrent characters, Content Manager
activation, Portalkeeper publication, PTR deployment, NPC interaction, chat delivery, or actual GameTooltip refresh
was exercised. In particular, the filtered `OnTooltipSetItem` post-script, read-only `SYNC` timing, comparison
tooltips, no-duplicate lines, relic wording, relog/restart restoration, and preserved item-tooltip content require
the manual evidence in `PHASE4C_PTR_VALIDATION.md`.

No deployment, database mutation, client publication, commit, or push was performed.

Status: **Phase 4C implementation and local automated/build validation are complete; build-12340/PTR behavior
remains separate and unverified.**

## Phase 4B

Test date: 2026-11-04.

### Passed

- Full module suite: `python3 -m unittest discover -s tests -p 'test_phase*.py'`
  - 128 tests passed, including 15 Phase 4B contracts for FrameXML parsing, native equipment templates,
    paper-doll placement, all fourteen slot mappings, actual/empty icon APIs, class-inapplicable ranged/relic
    presentation, catalog requests, tooltips, confirmed applied/hidden indicators, pagination/Hide placement,
    Apply/Remove/Reset, preview fallback, frame bounds, and Lua 5.1 syntax restrictions.
- Lua validation:
  - `NativeTransmogFrame.lua` parsed successfully through the local x86_64 Lua 5.1 shared runtime using
    `luaL_loadbuffer`.
- FrameXML validation:
  - `NativeTransmogFrame.xml` parsed successfully with Python `xml.etree.ElementTree`.
- Existing catalog fixture against Playerbot `item_template.sql` passed for all head, shoulder, chest, main-hand,
  and off-hand fixtures.
- AzerothCore C++ codestyle checks passed.
- Playerbot AzerothCore Release compile/link:
  - Playerbot revision `8a4e76eac8c4`, GCC 15.2, C++20, `MODULES=static`, `SCRIPTS=none`.
  - All seven module translation units compiled, `libmodules.a` linked, and `worldserver` linked at 100%.
  - Generated loader and final binary contain `Addmod_native_transmogScripts`; final binary contains
    `WardrobeService::SendEquipmentState`.
  - Worldserver SHA-256: `9c56e1b1470f7d5c9c7c9babc4b092e6dd826fa87541f89c49df40d052ba766e`.
- EPF deterministic build/check/rebuild:
  - Four members; two consecutive builds were byte-for-byte identical and `--check` passed.
  - SHA-256: `005c2bd90ed32157b570d01bf1277416fe6d3fa2d75565759573f7ac8bed7ede`.
- `git diff --check` passed.

### Not run or not proven

No build-12340 WoW client, live MySQL updater/startup, Content Manager activation, Portalkeeper publication, PTR
deployment, NPC interaction, addon-message delivery, observer synchronization, or pixel/layout inspection was
performed. The UI has not been visually validated. In particular, actual-client availability of
`DressUpModel:UndressSlot`, layout at supported UI scales, the guarded hidden-preview fallback, race/gender model
geometry, enchants, mirror images, relog/restart, and weapon gameplay remain PTR validation items in
`PHASE4B_PTR_VALIDATION.md`.

No deployment, database mutation, client publication, commit, or push was performed.

Status: **Phase 4B implementation and local automated/build validation are complete; actual-client visual and PTR
validation remain separate and unverified.**

## Phase 4A

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
