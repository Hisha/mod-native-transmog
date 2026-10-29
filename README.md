# mod-native-transmog

`mod-native-transmog` is an independently authored, MIT-licensed native AzerothCore module and protected-FrameXML package for WoW 3.3.5a build 12340. It does not use a standalone addon and does not modify `azerothcore/mod-transmog`.

Phase 1's in-game validated preview wardrobe, Phase 2's server-authorized NPC service, and Phase 3A's persistent collection are preserved. Phase 3B unlocks every eligible appearance offered by a successfully rewarded quest and adds an explicit, bounded historical backfill. It does **not** grant unselected items, apply appearances, change the wardrobe catalog, migrate existing `mod-transmog` records, or save outfits.

## Phase 3B quest reward collection

After a successful quest reward transaction, all eligible appearances in the quest's six selectable and four guaranteed WotLK reward fields are collected. The character still receives only the selected choice plus normal guaranteed items. Collection ignores class, race, armor/weapon proficiency, skills, and equip requirements; the Phase 3A resolver still excludes non-visible/non-equipment categories, missing templates, invalid display data, rings, trinkets, and other ineligible items.

The Playerbot `PLAYERHOOK_ON_PLAYER_COMPLETE_QUEST` hook is post-reward on the inspected branch: item delivery, rewarded-state mutation, and `SaveToDB` precede the hook. Accepting, previewing, objective-completing, abandoning, or failing to turn in a quest does not collect offered rewards. Duplicate item entries, shared composite appearances, repeated quests, and appearances already acquired normally are idempotent and preserve first provenance.

Quest unlocks use the same authenticated account/character owner, appearance key, cache, persistence table, and query APIs as Phase 3A. Acquisition categories `4` and `5` distinguish live all-offered-reward enumeration and historical backfill. The additive `source_quest` column records the current quest definition responsible for a new quest-derived row; existing rows remain unchanged with zero. A selected or guaranteed item may already have been recorded by Phase 3A's earlier physical-item hook, in which case its original item-storage provenance remains authoritative.

Historical backfill is never automatic. An authorized in-game GM starts preview or execution for one selected online character (or the GM character), and status reports progress. Only active `character_queststatus_rewarded` rows are accepted as reliable evidence; active quest-log state and achievements are ignored. Processing uses monotonic indexed queries of at most 25 quests every 100 ms. Account-wide execution contributes that one character's history to the shared collection without claiming sibling characters were scanned. Current server quest definitions are authoritative; deleted definitions, unretained history, old reward choices, repeat counts, and historical definition changes cannot be reconstructed. See [Phase 3B architecture](docs/PHASE3B_ARCHITECTURE.md).

## Phase 3A persistent collection

Eligible visible armor and weapon appearances unlock when an item is newly stored or moved into a character's inventory. Collection ignores class, race, armor proficiency, weapon proficiency, and required skills: a mage can collect plate and a rogue can collect a two-handed sword. Future Phase 3C application must independently enforce all compatibility rules.

Ownership lives in the character-database table `native_transmog_collection`. Account ownership uses the authenticated `WorldSession` account ID; character ownership uses the server-side character GUID. Both namespaces coexist. Switching scope never merges, copies, or deletes rows, and switching back restores the earlier namespace.

The appearance identity is `(DisplayInfoID, item class, item subclass, inventory type)`. This deduplicates item entries that safely share complete client/category identity while keeping shared display IDs separate where armor/weapon/slot semantics differ. Original source item, acquiring character, timestamp, and acquisition hook category remain attached to the first unlock.

Supported central acquisition paths include ordinary loot storage, quest rewards actually received, crafted items, most vendor purchases, mail retrieval, and trades. A focused hook covers vendor purchases equipped directly. There is no startup/login inventory scan; Phase 3B's separate historical command is explicit and selected-character-only. See [Phase 3A architecture](docs/PHASE3A_ARCHITECTURE.md) for exact eligibility, acquisition limitations, schema semantics, performance, Playerbot, and cross-realm details.

## Phase 2 architecture

The service registry resolves an interacted creature in this order:

1. dedicated Transmogrifier template resolved from Content Manager symbol `dedicated-transmogrifier`;
2. enabled creature-entry registration;
3. enabled persistent spawn-ID registration.

Entry registration also works for dynamically created creatures. Spawn registration requires AzerothCore's persistent `Creature::GetSpawnId()` and rejects temporary creatures whose spawn ID is zero. Registrations live in the module-owned world table `native_transmog_npc_registration`; `(scope, target_id)` is the primary key, scope `1` means creature entry, scope `2` means spawn ID, and `enabled` retains disabled registrations for audit/re-enablement.

The Schema 3 EPF declares `creatureTemplates[]` symbol `dedicated-transmogrifier`. Content Manager retains and collision-checks its realm-local `creature-template.id`, applies the template and its model children transactionally, and exposes the active value through `ContentResourceApiV1`. The declaration copies stock entry `28699` (whose single model is display `25615`) and overrides the service-facing fields to produce the neutral, gossip-enabled **Transmogrifier — Wardrobe Specialist**. Module SQL owns only the registration table and contains no creature entry or model insert.

At startup the module discovers the optional Content Manager provider through the established `WorldScript` RTTI pattern and resolves `(mod-native-transmog, dedicated-transmogrifier, creature-template.id)`. Dedicated resolution is enabled only when the declaring build is ACTIVE, its server bundle is APPLIED and verified, and the allocated template is loaded with the expected name. Missing/inactive Content Manager disables only the dedicated NPC; existing entry and persistent-spawn registrations remain available. Use `.content allocations` or `.nativetransmog npc list` to obtain the allocated entry before creating ordinary persistent spawns with `.npc add <allocated-entry>`.

### Existing NPC services

The module does not change `ScriptName`, gossip rows, or the `npcflag` of existing NPCs. The global creature gossip hook observes a core-validated interaction, sends authorization, and returns control for registered existing creatures, allowing their original gossip/script path to continue. It consumes only the dedicated template's intentionally empty gossip. Vendor-only interactions are covered by `OnPlayerSendListInventory`, and trainer interaction by the corresponding pre-list hook; both independently repeat AzerothCore interaction validation. Quest-giver hello also passes through the creature gossip hook on the inspected branch.

The inspected hook order cannot safely append a new gossip option to every scripted NPC: the global hook runs before AzerothCore clears the menu, while consuming it would suppress the existing creature script. Phase 2 therefore opens the wardrobe immediately on a registered supported interaction instead of replacing or rewriting the NPC's menu. NPCs with no client-interactable service flag cannot initiate an interaction, and the module deliberately does not add one.

## Server-to-client authorization

The server sends a self-whisper with `LANG_ADDON` using prefix `NTRANSMOG`. Stock build-12340 FrameXML receives it as `CHAT_MSG_ADDON`; the protected Lua accepts only protocol version 1, `WHISPER`, the exact prefix, and the player's own sender name. `OPEN` carries an opaque server session token; `CLOSE` carries the same token.

This uses the stock addon-message wire protocol without installing an addon, inventing an opcode, or exposing normal chat text. It is also a pattern already supported by the inspected Playerbot branch and other native FrameXML modules in this environment.

The server creates a session only after resolving the actual server-side `Creature*`, confirming it is registered, and calling `GetNPCIfCanInteractWith` for proximity, map, reaction, life-state, control-state, and existence checks. Combat is rejected. Every 500 ms the session is revalidated and is closed when the player moves away, enters combat, the creature disappears, eligibility is removed, or the map changes; logout removes it without sending a packet. The client never supplies an entry or spawn ID.

Addon messages are not cryptographic: arbitrary client Lua could imitate an `OPEN` display message. That only reveals the local preview window. It cannot create a server session, and Phase 2 exposes no appearance-application request. Every future gameplay request must carry the token and independently revalidate the live server session, NPC, item, slot, and policy; the client token alone must never grant permission.

## Configuration

```ini
NativeTransmog.Enable = 1
NativeTransmog.DefaultNPC.Enable = 1
NativeTransmog.CustomNPC.Enable = 1
NativeTransmog.CustomNPC.AllowSpawnRegistration = 1
NativeTransmog.Collection.Enable = 1
NativeTransmog.Collection.AccountWide = 1
NativeTransmog.Collection.UnlockOnAcquire = 1
NativeTransmog.Collection.UnlockAllQuestRewards = 1
NativeTransmog.Collection.QuestBackfill.Enable = 1
NativeTransmog.AllowTwoHandAppearanceOnOneHand = 0
NativeTransmog.AllowOneHandAppearanceOnTwoHand = 0
```

Collection is account-wide by default. Disabling account-wide mode selects existing/per-character rows without touching account rows. The weapon settings remain reserved and unenforced because appearance application is out of scope.

## GM commands

Select a creature before using selection-based commands:

```text
.nativetransmog npc add entry
.nativetransmog npc add spawn
.nativetransmog npc remove entry
.nativetransmog npc remove spawn
.nativetransmog npc info
.nativetransmog npc list
.nativetransmog collection info
.nativetransmog collection count
.nativetransmog collection list
.nativetransmog collection backfill preview
.nativetransmog collection backfill run
.nativetransmog collection backfill status
```

Add and quest-backfill execution use AzerothCore's existing NPC-add RBAC permission, remove uses NPC-delete, and read-only NPC/collection diagnostics and backfill preview/status use NPC-info. Ordinary players therefore cannot invoke these GM commands. Collection list output is bounded to 50 rows; backfill has no global/account/realm mode and requires an online character target.

## Installation and PTR deployment

1. Install this repository as `modules/mod-native-transmog` in the Playerbot core and leave `mod-transmog` installed and configured normally.
2. Apply the normal AzerothCore module SQL updater. Phase 3A adds `2026_10_28_00_native_transmog_collection.sql`; Phase 3B conditionally adds `source_quest` and its index through `2026_10_29_00_native_transmog_quest_provenance.sql`. Existing ownership/provenance is not rewritten, and no `mod-transmog` table is touched.
3. Install `conf/mod_native_transmog.conf.dist` through the normal module config flow and build worldserver.
4. Rebuild/verify the EPF:

   ```bash
   python3 content/build_epf.py
   python3 content/build_epf.py --check
   ```

5. Feed `content/mod-native-transmog.epf` through the existing FrameForge → EPF → mod-content-manager → Portalkeeper pipeline. Build and activate it so the managed server bundle is APPLIED before the validation restart. No content-manager or Portalkeeper code change is required. The existing `protected-framexml` realm requirement remains mandatory.
6. Restart PTR so AzerothCore loads the applied template, find the allocated `creature-template.id` with `.content allocations` (also shown by `.nativetransmog npc list` after startup), run `.npc add <allocated-entry>` as a GM, and interact with the spawned creature.

The checked-in EPF is deterministic Schema 3 content. It adds the XML immediately after stock `DressUpFrame.xml`; it contains no addon directory, addon manifest, raw FrameXML TOC replacement, custom opcode, or executable transformation.

## Development command

`/wardrobe` and `/nativetransmog` remain temporary local preview toggles. They explicitly clear the client authorization token, send no request, and create no server session. They cannot authorize a future application operation.

## Automated checks

```bash
python3 content/build_epf.py --check
python3 -m unittest tests/test_phase1.py tests/test_phase2.py tests/test_phase3a.py tests/test_phase3b.py
python3 tests/verify_catalog.py \
  /path/to/azerothcore-wotlk/data/sql/base/db_world/item_template.sql
```

The checks cover Phase 1/2 regressions, Phase 3A ownership/persistence, and Phase 3B reward enumeration, cross-class behavior, provenance, post-reward integration, backfill evidence, preview/run idempotency, permissions, and batching. See [test results](docs/TEST_RESULTS.md), the [Phase 2 PTR checklist](docs/PTR_VALIDATION.md), the [Phase 3A PTR plan](docs/PHASE3A_PTR_VALIDATION.md), and the [Phase 3B PTR plan](docs/PHASE3B_PTR_VALIDATION.md).

## Known limitations and future mobile NPCs

- Phase 3B PTR validation has not been performed; automated checks and a Playerbot module build do not prove in-game behavior.
- Phase 2 opens immediately on supported gossip/quest, vendor, and trainer interactions; it cannot safely inject an option into arbitrary scripted gossip on this branch.
- Client service types that bypass all inspected hooks are not covered. Registration never changes their flags to manufacture an interaction path.
- Vehicle-passenger creatures are explicitly rejected in Phase 2. Entry resolution itself is location- and spawn-independent, so the registry is suitable for a future mobile Transmogrifier, but passenger interaction and moving-distance/session semantics require dedicated validation before removing this guard.
- The preview catalog remains a deterministic fixture and is not yet filtered by the persisted collection.
- Backfill can prove only active persisted rewarded rows and uses current quest definitions; it cannot reconstruct missing repeat history, old choices, or historical reward definitions. Offline targets are intentionally unsupported.
- No saved outfit, appearance application, client collection filtering, or migration from `mod-transmog` exists.

No code change outside this repository is required. The target Content Manager must already include managed server resources and `ContentResourceApiV1` (Milestone 2), and its `2026_09_25_06_content_managed_server_resources.sql` migration must be present before building/activating this EPF.

## License

All module implementation is independently authored under the [MIT License](LICENSE). No AGPL implementation from `mod-transmog` was copied or adapted.
