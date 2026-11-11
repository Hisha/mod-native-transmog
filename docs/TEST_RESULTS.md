# Test results

## Apply Outfit in Transmogrify

Test date: 2026-11-10.

### Passed

- Focused Apply Outfit coverage plus the full automated suite:
  `python3 -m unittest discover -s tests -p 'test_*.py'` — 357 tests passed. Coverage includes multi-slot apply,
  explicit hidden/empty slots, unspecified-slot preservation, grouped weapon compatibility, uncollected/incompatible
  rejection, NPC authorization, all-or-nothing persistence, duplicate requests, client pending/success/failure/timeout
  handling, and saved-preview preservation.
- Playerbot AzerothCore revision `e7e2e288e`, GCC 15.2, C++20, `MODULES=static`, `SCRIPTS=none`:
  all module translation units compiled, `libmodules.a` linked, and `worldserver` linked at 100%. The binary exports
  `Addmod_native_transmogScripts` and does not export `Addmod_transmogScripts`.
  Worldserver SHA-256: `0faae5b9063d3400f961fbecd1161fb94002d56ac06278f0d967565e9cf172b7`.
- Deterministic EPF build and `--check` passed with four members.
  EPF SHA-256: `3a9225574b7bbe085b8377a5bdf35c2a18876b28d06575ba9269b81bd84b40e4`.
- `git diff --check` passed. No core source, SQL schema, saved-set persistence format, standalone addon, commit, or push
  was introduced.

### Not run or not proven

No PTR deployment, live database startup, build-12340 client session, NPC interaction, `TempJudge` application, visual
inspection, equipped-item comparison, observer synchronization, or persistence/reopen acceptance was performed.
Follow [`APPLY_OUTFIT_PTR_VALIDATION.md`](APPLY_OUTFIT_PTR_VALIDATION.md); do not record PTR success from these local
results.

## Grouped weapon compatibility and saved-outfit preview routing

Test date: 2026-11-10.

### Passed

- Added focused executable/contracts for one-handed axe/mace/sword and two-handed axe/mace/sword/polearm grouping,
  strict handedness, ownership/proficiency rejection, full-group search-before-pagination, final application authority,
  saved mace-and-shield slot mapping, multi-slot restoration, response routing, failure reporting, and timeout cleanup.
- Full automated suite: `python3 -m unittest discover -s tests -p 'test_*.py'` — 342 tests passed.
- Playerbot AzerothCore revision `e7e2e288e`, GCC 15.2, C++20, `MODULES=static`, `SCRIPTS=none`:
  all module translation units compiled, `libmodules.a` linked, and `worldserver` linked at 100%.
  Build artifact SHA-256: `0293f8ba140fe155460e3dd290d947b76e653335ee310e2ba23ff6046977ce30`.
- Deterministic EPF verification: four members; two consecutive builds were byte-identical.
  SHA-256: `d1a8cfe9e34d38d5b4ddcecdc0eba54a7b06e748b471db74ab5b7aa0122aed44`.
- `git diff --check` passed. No SQL or saved-set persistence-format change was made.

### Not run or not proven

No PTR worldserver/client deployment or live character database was used. Actual paladin proficiency data, catalog
contents, rendering of `TempJudge`, live timeout behavior, application, Collections, and Head portrait acceptance must
follow [`WEAPON_COMPATIBILITY_SAVED_OUTFIT_PTR_VALIDATION.md`](WEAPON_COMPATIBILITY_SAVED_OUTFIT_PTR_VALIDATION.md).
No database mutation, deployment, commit, or push was performed.

## Wardrobe appearance-browser usability

Test date: 2026-11-10.

### Passed

- Removed the temporary three-model position probe, both probe slash commands, its EPF members/load entry, and the
  separate portrait debug command. The production XML retains only the existing full-character Wardrobe model, the
  single reusable Head portrait, and the separate unchanged Collections model.
- Appearance tiles now include a two-line, ellipsized item label. Cached item quality drives the label color, and
  `GET_ITEM_INFO_RECEIVED` refreshes labels when item data arrives asynchronously.
- Clicking an appearance resets and dresses the existing Wardrobe preview, then repeats only the dress operation
  during a generation-guarded 0.25-second window so asynchronous `SetUnit("player")` completion cannot restore stale
  equipment over the selected wrist, chest, or weapon appearance.
- Full suite: `python3 -m pytest -q` — 318 tests and 30 subtests passed.
- Deterministic EPF build/check passed with four members.

### Not run or not proven

No build-12340 client or PTR deployment is available in this workspace. Actual label readability at supported UI
scales, quality colors, Head portrait layering above labels, and wrist/chest/weapon geometry on the full-character
preview still require PTR verification.
No deployment, commit, or push was performed.

## Shared portrait camera fallback and weapon navigation

Test date: 2026-11-10.

### Passed

- Removed the unverified non-Head camera presets after PTR showed they all remained focused on the head. The one
  reusable model and PTR-accepted Head camera, facing, rotation, scale `1.30`, and position `(0,-0.13,0)` are
  unchanged. Every non-Head category now retains its normal item icon.
- Restored click access to Main Hand, Off Hand, and Ranged by putting equipment buttons above the overlapping
  mouse-enabled preview model. Existing wire IDs, slot mappings, catalog queries, and server support are unchanged.
- Preserved exact source-link verification, clear/`SetUnit`/`Undress`/`TryOn` order, bounded delayed reapplication,
  generation invalidation, item-specific icon fallback, the independent main character preview, Collections,
  Saved Sets, window/tile dimensions, purple selection accent, and all server/database/application behavior.
- Full Lua/XML/module suite: `python3 -m unittest discover -s tests -p 'test_*.py'`
  - 311 tests passed.
  - Coverage includes Head-only 3D framing, icon fallback for every other slot, exact source identity, rapid
    selection, stale callbacks, one XML model, weapon hit-test ordering and navigation mappings, and preview isolation.
- Deterministic EPF verification:
  - Four members; two consecutive builds were byte-for-byte identical and `python3 content/build_epf.py --check`
    passed.
  - SHA-256: `91231edbf3a4177c9ece5fbca9a0172ebe33da2431cffdb58cbaaa968b32141d`.

### Not run or not proven

No build-12340 client or PTR deployment is available in this workspace. Automated tests do not prove that the Head
crop remains visually correct or that native hit testing now reaches all three weapon buttons. Those checks remain
in [`EQUIPMENT_PORTRAITS_PTR_VALIDATION.md`](EQUIPMENT_PORTRAITS_PTR_VALIDATION.md). No deployment, commit, or push
was performed.

## Single-tile portrait framing correction

Test date: 2026-11-09.

### Passed

- Reduced the one-model portrait preset from scale `1.80` to `1.30`, retained camera 0 and centered X/Z offsets,
  and retained the verified `-0.13` camera depth. The preset remains reasserted during the bounded native-load
  window.
- Source contracts cover one XML-owned `84x111` model, icon fallback, `SetUnit`/`Undress`/`TryOn` isolation,
  clear-before-reuse lifecycle, camera reset, and three consecutive enable/disable lifecycle checks.
- Full suite: `python3 -m unittest discover -s tests`
  - 297 tests passed.
- Lua/FrameXML validation:
  - `NativeTransmogFrame.lua` parsed successfully through the installed LuaJIT 5.1-compatible runtime.
  - `NativeTransmogFrame.xml` parsed successfully with Python `xml.etree.ElementTree`.
- Deterministic EPF verification:
  - Four members; two consecutive builds were byte-for-byte identical and `python3 content/build_epf.py --check`
    passed.
  - SHA-256: `e3c836315d9721182b2ce7f6938a5fbcf23085ef1d79217413fcb6337b8ee618`.
- `git diff --check` passed.

### Not run or not proven

No build-12340 client or PTR deployment is available in this workspace. The Judgement helmet's final pixel margins,
three live enable/disable pairs, stale/floating-model absence, and the race/sex geometry matrix therefore remain
manual PTR checks. Build 12340 exposes no supported child-clipping control or model-bounds API; the observed overflow
shows that frame-edge clipping cannot be assumed. Tauren horns, Troll/Night Elf ears, Draenei horns/crests, hair, and
unusually tall or wide helm geosets can still require a more conservative shared scale. No Collections window,
Warpweaver, server protocol, or other Wardrobe behavior was changed. No deployment, commit, or push was performed.

## Native Warpweaver updater compatibility fix

Test date: 2026-11-09.

### Passed

- Inspected Playerbot AzerothCore revision `e7e2e288e`: `UpdateFetcher` delegates each file to `ApplyFile`, which launches the configured MySQL client, and `StartProcess` connects the file directly to client standard input. The updater does not parse SQL or add stored-routine/`DELIMITER` behavior, does not pass `--force`, and records the new update hash only after a successful client exit.
- Verified the immediate syntax failure against MySQL 8's restricted-label list: the procedure's unquoted `install: BEGIN` label is invalid. The replacement removes the procedure rather than relying on a label-only repair.
- Replaced the procedure installer in both byte-identical base/update files with ordinary batch statements. Regression coverage lexes the complete files under that real updater contract and rejects `DELIMITER`, procedure/function creation, and `CALL` statements.
- Full module suite: `python3 -m unittest discover -s tests -p 'test_*.py'`
  - 268 tests passed, including exact values for all nine maps/coordinates/orientations, the updater source/stream contract, one transactional marker gate, `creature.id`, display `19646`, 300-second respawn, auto-increment GUID allocation, and absence of entry `190010`.
- Base/update installers are byte-identical and `git diff --check` passed.

### Not run or not proven

No MySQL/MariaDB server or client is installed in this workspace, so the corrected file was not applied to a live database here. Fresh-schema execution, recovery from the PTR's DDL-only failed state, changed-hash replay, and live NPC loading remain PTR deployment gates.

## Native Warpweaver installation

Test date: 2026-11-09.

### Passed

- Full module suite: `python3 -m unittest discover -s tests -p 'test_*.py'`
  - 266 tests passed, including the existing Collections, saved/custom sets, acquisition, application, wardrobe,
    tooltip, set catalog, and protocol regressions plus the native-NPC installation contracts.
- Playerbot schema/source audit at revision `e7e2e288e`, superseded where noted by the verified PTR schema:
  - confirmed PTR `creature.id`, auto-increment `creature.guid`, `creature_template_model` keys/columns, display `19646`
    in `creature_model_info`, workspace reservations through `14999991`, and no inspected use of `14999992`;
  - the inspected checkout has no `mod-transmog` module directory.
- Changed C++ translation units passed `-fsyntax-only` with the inspected Playerbot C++20 definitions and complete
  generated script include set.
- Deterministic EPF build and `--check` passed with four members; SHA-256:
  `5ebe8e0bfbb6ae415a9efbcfff6d1b87ad6d3efc105f67ffd602a8c26274c0ec`.
- Base and update installers are byte-identical, use the verified `creature.id` column, contain all nine audited
  coordinates with consistent mask/respawn/health fields, omit explicit spawn GUIDs, join installed rows back to
  their staged defaults, and reserve a transactional one-time marker before mutation. `git diff --check` passed.

### Not run or not proven

No live MySQL/MariaDB server or PTR worldserver/client was available in this workspace. Therefore fresh-database and
existing-PTR updater execution, actual spawn loading/respawn, in-game appearance/scale, one-open gossip behavior,
restart/replay counts, administrator move/delete preservation, and verification of a previously deployed binary's
legacy-module set remain manual PTR gates. No database, server, client publication, commit, or push was performed.

Status: **implementation and local static/regression validation complete; live fresh-install and PTR upgrade
validation pending the documented deployment checklist.**

## Phase 5A pagination and acquisition-source corrections

Test date: 2026-11-05.

### Passed

- Full module suite: `python3 -m unittest discover -s tests -p 'test_*.py'`
  - 189 tests passed, including independent catalog/detail request state, selection without pagination mutation,
    intentional filter reset, delayed replies, rapid switching, bounded token chains, extended-cost currencies,
    quest availability, crafting markers, source ordering, and all prior Phase 1–5A regressions.
- Installed Playerbot schema/data audit at revision `8a4e76eac8c4`:
  - `npc_vendor`, creature/gameobject quest-starter, spawn, direct loot, and reference-loot queries match the installed
    schema. Extended cost 1200 requires Chestguard of the Fallen Champion 29754; reference 34047 connects that token
    to Magtheridon 17257. Redemption Handguards quest 9048 and its four required materials are present, but no current
    starter/source chain was established by the installed data.
- Lua/FrameXML validation:
  - `NativeTransmogFrame.lua` returned `0` from `luaL_loadbuffer` using the local x86_64 Lua 5.1 runtime.
  - `NativeTransmogFrame.xml` parsed successfully with Python `xml.etree.ElementTree`.
- Playerbot Release worldserver:
  - Changed module sources compiled, `libmodules.a` linked, and `worldserver` linked at 100%.
  - Build artifact SHA-256: `ab3f657fc281d5a6c0d92b1eb903bf95556f098ad95844256a7748f28a32fede`.
- Deterministic EPF verification:
  - Four members; two consecutive builds were byte-for-byte identical and `python3 content/build_epf.py --check`
    passed.
  - SHA-256: `e7fa6fb1dd515c456125901de5ef5c443b41049084beb1f2e38f8329c12c34eb`.
- AzerothCore C++ codestyle and `git diff --check` passed. Protocol version remains 3; no SQL/configuration change
  was added.

### Not run or not proven

No live PTR database startup/source-count audit, build-12340 client, Content Manager activation, Portalkeeper
publication, or deployment was performed. Script/event/mail/container acquisition, exact city/zone text beyond loaded
map names, profession recipe reachability, and live asynchronous/UI behavior remain PTR validation items. No database
mutation, deployment, commit, or push was performed.

## Phase 5A final polish and catalog completion

Test date: 2026-11-05.

### Passed

- Full module suite: `python3 -m unittest discover -s tests -p 'test_*.py'`
  - 181 tests passed, including explicit tier-family counts, class/faction visibility contracts, PvE/PvP metadata,
    specialization/faction variants, five/eight-piece progress, composite-appearance deduplication, legacy/unknown
    sources, tooltip formatting, bounded long-name rows, repeated set selection/pagination, and all existing
    Appearances regressions.
- Installed Playerbot base-data audits at revision `8a4e76eac8c4`:
  - Existing appearance fixture audit passed.
  - `tests/verify_set_catalog.py` verified 263 unique ItemSet identities, reviewed class masks, and expected five/eight
    visual slots: Classic PvE 36; TBC PvE 51/PvP 65; Wrath PvE 95/PvP 16.
  - The deterministic runtime model yields 540 distinct browser variants after composite-appearance deduplication.
- Lua/FrameXML validation:
  - `NativeTransmogFrame.lua` returned `0` from `luaL_loadbuffer` using the local x86_64 Lua 5.1 runtime.
  - `NativeTransmogFrame.xml` parsed successfully with Python `xml.etree.ElementTree`.
- Playerbot Release worldserver:
  - All module sources compiled, `libmodules.a` linked, and `worldserver` linked at 100%.
  - Build artifact SHA-256: `bcd67bd04ce042aebd0463e4ef80bfdf0ed27aa943fd2b315e4fb2aa8d5271cb`.
- AzerothCore C++ codestyle and `git diff --check` passed.
- Deterministic EPF verification:
  - Four members; two consecutive builds were byte-for-byte identical and `python3 content/build_epf.py --check`
    passed.
  - SHA-256: `5e60cb0d60c976d86f16a4d5d8e92d18a06ca626ce31f9a0833bf6a7c9df1c87`.

### Not run or not proven

No live realm database startup/source-count audit, build-12340 client, Content Manager activation, Portalkeeper
publication, or PTR deployment was performed. Native tooltip preservation/placement, every source string, UI-scale
row geometry, asynchronous switching, race/gender previews, and the realm's actual 263-identity/540-variant startup
count require the documented PTR validation. No deployment, database mutation, commit, or push was performed.

## Phase 5A stabilization

Test date: 2026-11-05.

### Passed

- Full module suite: `python3 -m unittest discover -s tests -p 'test_*.py'`
  - 179 tests passed, including response-lifecycle regressions for repeated page/detail messages, 32-piece details,
    rapid selection changes, page replacement, closure, and late messages; curated-catalog and server-name contracts;
    and all Phase 1–4C behavior.
- Lua/FrameXML validation:
  - `NativeTransmogFrame.lua` returned `0` from `luaL_loadbuffer` using the local x86_64 Lua 5.1 runtime.
  - `NativeTransmogFrame.xml` parsed successfully with Python `xml.etree.ElementTree`.
- Playerbot AzerothCore revision `8a4e76eac8c4` Release worldserver compiled and linked successfully with the
  stabilization module sources.
- AzerothCore C++ codestyle and `git diff --check` passed.
- Existing appearance catalog fixtures passed against the installed AzerothCore base `item_template.sql`.
- Deterministic EPF verification:
  - Four members; two builds were byte-for-byte identical and `python3 content/build_epf.py --check` passed.
  - SHA-256: `6e4c7daa8899b839a7e3da754ec3d25953f7b9b06203ca1373fa2baaae203536`.

### Not run or not proven

No build-12340 client, live realm database, Content Manager activation, Portalkeeper publication, or PTR deployment
was exercised. Actual asynchronous delivery timing, cleared item-cache behavior, class/faction catalog contents,
and protected FrameXML globals require the checks in `PHASE5A_PTR_VALIDATION.md`.

No deployment, database mutation, commit, or push was performed.

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
