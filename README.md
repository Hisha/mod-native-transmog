# mod-native-transmog

`mod-native-transmog` is an independently authored, MIT-licensed native AzerothCore module and protected-FrameXML package for WoW 3.3.5a build 12340. It does not use a standalone addon and does not modify `azerothcore/mod-transmog`.

Phases 1–3C provide the preview UI, NPC authorization, persistent collection, quest collection/backfill, and server-side appearance engine. Phase 3D connects them. Phase 4A adds every visually relevant slot and Hide Appearance; Phase 4B presents them as a native paper doll. Phase 4C adds persisted-unlock chat notifications and authoritative appearance details to wardrobe and CharacterFrame tooltips. Phase 5A adds read-only browsing and preview for authentic gameplay equipment sets. It does **not** grant items, apply whole sets, add saved outfits, price ordinary applications, migrate legacy `mod-transmog` records, or introduce a second transmog engine.

## Phase 5A equipment sets

The wardrobe has `Appearances` and `Sets` modes. The explicit reviewed catalog now contains 263 Blizzard class-tier and PvP ItemSet identities covering Classic Tiers 1–3, TBC Tiers 4–6 plus level-70 honor/arena sets, and Wrath Tiers 7–10 plus arena sets. Distinct installed appearance variants remain distinct while identical composite appearances are deduplicated. Loaded DBC/templates remain authoritative for membership, names, and race/faction eligibility. Acquisition details are appended to native item tooltips instead of crowding piece rows; the startup index uses vendor, direct/reference loot, raid-map, and quest metadata and labels unresolved paths honestly. Browsing and preview require no NPC session; every mutation retains the existing Transmogrifier authorization. See [Phase 5A data design](docs/PHASE5A_DATA_DESIGN.md).

## Phase 4C notifications and tooltips

`CollectionService` emits `Appearance saved: <item name>` through AzerothCore's normal system-message chat path only after a previously absent appearance identity is synchronously inserted and read back from `native_transmog_collection`. The same centralized rule covers item storage, inventory transfer, successful first equip, and live quest reward collection. Cache/unique-key checks suppress duplicates and repeated equips in either account-wide or character-specific scope. Collection-disabled paths, failed persistence, application/removal/hiding, and explicit historical quest backfills emit nothing. There is no notification configuration or acquisition-specific notification hook.

Equipped-item tooltips show no extra line for original state, `Appearance: Hidden` for effective hidden state, or `Transmogrified to: <name>` for an applied override. The name comes from the persisted override's canonical `appearance_item`, not the physical item or display ID. The server adds that entry and its item-template name to the existing version-2 `STATE` response; no appearance table or database migration is added.

The protected FrameXML installs a narrow post-hook on `PaperDollItemSlotButton_OnEnter`, leaving Blizzard's normal item tooltip construction and comparison tooltips intact. It also uses the same helper for wardrobe slots and checks existing tooltip lines before appending. On `PLAYER_ENTERING_WORLD` (including `/reload`) the client sends the authenticated-self, read-only `SYNC` request, which requires no Transmogrifier session and returns token-zero state for all supported equipped slots. Equipment changes push a token-zero update for the affected slot. Apply, Hide, Remove, and catalogs retain their NPC-session and snapshot authorization. This makes persisted state available to CharacterFrame before the wardrobe is opened.

## Phase 4B native paper doll

The wardrobe uses a local equipment-slot template built on Blizzard's `ItemButtonTemplate`, stock inventory-slot textures returned by `GetInventorySlotInfo`, live equipped icons from `GetInventoryItemTexture`, `GameTooltip:SetInventoryItem`, dialog/tooltip borders, rotation button art, and `DressUpModel`. It does not inherit `PaperDollItemSlotButtonTemplate`: that template's handlers own CharacterFrame equip, drag, event, and gear-flyout state. The local template retains the native icon treatment while making every click wardrobe-only. See [Phase 4B architecture](docs/PHASE4B_ARCHITECTURE.md).

The fourteen visual slots form left and right columns around the model; main hand, off hand, and ranged form the familiar bottom row. Empty usable slots show Blizzard's native empty-slot texture and explain that an item must be equipped. They never request a catalog or enable Apply/Remove. The client uses WotLK's `UnitHasRelicSlot("player")` convention to render the non-dressable ranged/relic position inactive without a class-name exception list and explains that relic appearances cannot be customized. Server compatibility remains authoritative for every item and appearance.

The server sends additive version-2 `STATE` replies for equipped item instances at read-only world-entry synchronization, equipment changes, and authorized wardrobe open. The paper doll shows a small stock ready-check marker for an applied appearance and stock pass marker for hidden state; original items have no marker. Catalog `PAGE` replies refresh the selected marker after Apply, Hide, or Remove. These indicators never follow a local preview selection.

## Phase 4A full slots and Hide Appearance

The supported AzerothCore equipment slots are Head, Shoulders, Shirt (`EQUIPMENT_SLOT_BODY`), Chest, Waist, Legs, Feet, Wrists, Hands, Back, Main Hand, Off Hand, Ranged, and Tabard. Neck, fingers, and trinkets are excluded. Catalog filtering and application continue through the Phase 3C compatibility validator, including exact armor subclass rules, chest/robe interchange, weapon families, handedness settings, and player eligibility.

Every supported catalog begins with a special **Hide Appearance** tile when hiding is permitted. It is independent of collection ownership, remains available for an empty collection, and does not consume a collected-appearance page position. Hide is a separate authenticated `HIDE` request using the same NPC session and item-GUID-bound snapshot as Apply and Remove. Hide and Restore Original are free; ordinary application pricing remains unchanged for this phase.

`native_transmog_item_override.override_state` distinguishes a collected appearance (`0`) from explicit hidden state (`1`). Existing rows migrate as state `0`. A hidden row retains the real item-instance GUID and owner but stores no fake appearance identity. Rendering writes zero only to the public visible-item entry field after the core has populated the real item and enchant fields; the item template, inventory record, stats, enchantments, durability, and combat behavior are untouched. The mirror-image hook returns display `0` for hidden armor. Removing the row and refreshing the slot restores the physical item's entry.

Weapon-slot hiding—including shields and held-in-off-hand items because they occupy `EQUIPMENT_SLOT_OFFHAND`—is controlled by the single default-off `NativeTransmog.HideWeapons` setting. When disabled, the tile is omitted for main hand, off hand, and ranged; the server independently rejects `HIDE`; and retained hidden-weapon rows render as the real item. Configuration reload refreshes online visible equipment but never deletes those rows.

## Phase 3D native wardrobe integration

Protected FrameXML and the server exchange version-2 `NTRANSMOG` addon messages over a stock `LANG_ADDON` self-whisper. The client uses build-12340 `SendAddonMessage`; the Playerbot core exposes the authenticated message through `PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT`, where the module consumes only its exact protocol. Replies arrive through `CHAT_MSG_ADDON`. This requires no standalone addon, custom opcode, chat command, core patch, Content Manager change, or Portalkeeper change. See the [transport decision](docs/PHASE3D_TRANSPORT_DESIGN.md).

Catalog pages come from `CollectionService` using the configured account or character scope. The composite identity remains `(display ID, item class, item subclass, inventory type)`. A startup-built item-template index selects the lowest-entry representative that passes the shared Phase 3C validator for the current player and equipped target, so the original physical item is not required and a restricted duplicate cannot hide a legitimate representative.

Each bounded page is tied to a server-issued nonce, NPC session, equipment slot, and item-instance GUID. Apply and Remove revalidate that snapshot and then call the existing Phase 3C `ApplicationService`; equipment changes invalidate it. The UI separately displays equipped, applied, and previewed states. Reset Preview and Close send no mutation request. `/wardrobe` and `/nativetransmog` remain preview-only because they have no server token.

## Phase 3C appearance application

The application service resolves the equipped target and source template entirely on the server. It requires either an immediately revalidated Phase 2 NPC session or an RBAC-protected GM diagnostic operation, verifies ownership in the authenticated account/character collection, and checks class, race, required skill/spell, armor/weapon proficiency, subclass, and inventory-slot compatibility before writing anything.

Armor requires the same subclass and visual slot, with chest/robe interchange. Weapons require the same weapon family and valid main/off-hand or ranged placement. One-hand/two-hand axe, mace, and sword family crossings are controlled by two independent, default-off settings. Persistence is keyed to the real item-instance GUID in `native_transmog_item_override`; the item's stats and gameplay identity never change.

Login restoration, ordinary visible-slot refreshes, ownership transfers, permanent item deletion, removal, nearby object-field synchronization, and mirror images use existing Playerbot hooks. No core patch was needed. See [Phase 3C architecture](docs/PHASE3C_ARCHITECTURE.md).

## Phase 3B quest reward collection

After a successful quest reward transaction, all eligible appearances in the quest's six selectable and four guaranteed WotLK reward fields are collected. The character still receives only the selected choice plus normal guaranteed items. Collection ignores class, race, armor/weapon proficiency, skills, and equip requirements; the Phase 3A resolver still excludes non-visible/non-equipment categories, missing templates, invalid display data, rings, trinkets, and other ineligible items.

The Playerbot `PLAYERHOOK_ON_PLAYER_COMPLETE_QUEST` hook is post-reward on the inspected branch: item delivery, rewarded-state mutation, and `SaveToDB` precede the hook. Accepting, previewing, objective-completing, abandoning, or failing to turn in a quest does not collect offered rewards. Duplicate item entries, shared composite appearances, repeated quests, and appearances already acquired normally are idempotent and preserve first provenance.

Quest unlocks use the same authenticated account/character owner, appearance key, cache, persistence table, and query APIs as Phase 3A. Acquisition categories `4` and `5` distinguish live all-offered-reward enumeration and historical backfill. The additive `source_quest` column records the current quest definition responsible for a new quest-derived row; existing rows remain unchanged with zero. A selected or guaranteed item may already have been recorded by Phase 3A's earlier physical-item hook, in which case its original item-storage provenance remains authoritative.

Historical backfill is never automatic. An authorized in-game GM starts preview or execution for one selected online character (or the GM character), and status reports progress. Only active `character_queststatus_rewarded` rows are accepted as reliable evidence; active quest-log state and achievements are ignored. Processing uses monotonic indexed queries of at most 25 quests every 100 ms. Account-wide execution contributes that one character's history to the shared collection without claiming sibling characters were scanned. Current server quest definitions are authoritative; deleted definitions, unretained history, old reward choices, repeat counts, and historical definition changes cannot be reconstructed. See [Phase 3B architecture](docs/PHASE3B_ARCHITECTURE.md).

## Phase 3A persistent collection

Eligible visible armor and weapon appearances unlock when an item is newly stored, moved into a character's inventory, or successfully equipped. The equipment path resolves the item actually occupying the server-side equipment slot and is idempotent, so an item already collected through loot, storage, or a quest creates no duplicate. Collection ignores class, race, armor proficiency, weapon proficiency, and required skills: a mage can collect plate and a rogue can collect a two-handed sword. Phase 3C independently enforces compatibility whenever an appearance is applied.

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

## Wardrobe transport and authorization

The server sends a self-whisper with `LANG_ADDON` using prefix `NTRANSMOG`. Stock build-12340 FrameXML receives it as `CHAT_MSG_ADDON`; the protected Lua accepts only protocol version 2, `WHISPER`, the exact prefix, and the player's own sender name. `OPEN` carries an opaque server session token; `CLOSE` carries the same token. Additive `STATE` replies carry server-confirmed per-slot original/applied/hidden state plus the canonical source entry/name. Read-only `SYNC` uses token zero and needs no NPC session. Client catalog/apply/hide/remove messages use the same prefix and still require the live server-authorized session.

This uses the stock addon-message wire protocol without installing an addon, inventing an opcode, or exposing normal chat text. It is also a pattern already supported by the inspected Playerbot branch and other native FrameXML modules in this environment.

The server creates a session only after resolving the actual server-side `Creature*`, confirming it is registered, and calling `GetNPCIfCanInteractWith` for proximity, map, reaction, life-state, control-state, and existence checks. Combat is rejected. Every 500 ms the session is revalidated and is closed when the player moves away, enters combat, the creature disappears, eligibility is removed, the five-minute lifetime ends, or the map changes; logout removes it without sending a packet. The client never supplies an entry or spawn ID.

Addon messages are not cryptographic: arbitrary client Lua can imitate UI traffic. This grants no authority. Every request is associated with the hook-provided authenticated player, requires the live server token, and independently resolves collection ownership, equipped item, canonical source, and compatibility. Snapshot nonces are short-lived, replay-bound, rate-limited, and invalidated by equipment changes.

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
NativeTransmog.Application.Enable = 1
NativeTransmog.AllowTwoHandAppearanceOnOneHand = 0
NativeTransmog.AllowOneHandAppearanceOnTwoHand = 0
NativeTransmog.HideWeapons = 0
NativeTransmog.Wardrobe.PageSize = 24
NativeTransmog.Wardrobe.RequestCooldownMs = 250
NativeTransmog.Wardrobe.SnapshotLifetimeMs = 30000
```

Collection is account-wide by default. Disabling account-wide mode selects existing/per-character rows without touching account rows. Application can be disabled independently for rendering rollback. The two weapon-direction settings and weapon hiding are independent and default to the conservative disabled policy.

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
.nativetransmog appearance apply <equipment-slot> <appearance-item-entry>
.nativetransmog appearance remove <equipment-slot>
.nativetransmog appearance info <equipment-slot>
```

Add, appearance apply, and quest-backfill execution use AzerothCore's existing NPC-add RBAC permission; removal uses NPC-delete; read-only diagnostics and backfill preview/status use NPC-info. Appearance commands target the selected online player or the executing GM. Ordinary players cannot invoke them. Equipment slots use AzerothCore's zero-based slot values (for example head `0`, main hand `15`, off hand `16`, ranged `17`).

## Installation and PTR deployment

1. Install this repository as `modules/mod-native-transmog` in the isolated Playerbot PTR build. Confirm `mod-transmog` is excluded from that build/load; production remains unchanged.
2. Apply the normal AzerothCore module SQL updater. Phase 3C adds `2026_11_01_00_native_transmog_item_override.sql`; Phase 4A adds `2026_11_04_00_native_transmog_hidden_state.sql`. Phases 4C and 5A add no migration. Existing override rows become collected-appearance state `0`; ownership/provenance and all legacy tables remain untouched.
3. Install `conf/mod_native_transmog.conf.dist` through the normal module config flow. Ensure AzerothCore's `worldserver.conf` contains:

   ```ini
   AddonChannel = 1
   ```

   The protected native FrameXML wardrobe uses AzerothCore's existing addon-message transport; it does not install or require a standalone addon. Then build worldserver.
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
python3 -m unittest discover -s tests -p 'test_phase*.py'
```

The checks cover all earlier regressions plus gameplay-set discovery, class/race filtering, appearance-identity grouping, source resolution, read-only pagination/detail validation, full-set preview contracts, notifications, tooltips, the 14-slot paper doll, hidden state, authorization, and EPF determinism. See [test results](docs/TEST_RESULTS.md) and the [Phase 5A data design](docs/PHASE5A_DATA_DESIGN.md).

## Known limitations and future mobile NPCs

- Phase 4C build-12340 client behavior requires PTR validation. Automated contracts and a Playerbot compile/link do not prove live chat delivery, GameTooltip refresh behavior, comparison-tooltip interaction, pixel layout, local/observer models, every race/gender geometry, enchant visuals, relog/restart, or mirror-image behavior.
- Read-only state covers the player's equipped items in the wardrobe and CharacterFrame only. Bag items, item/chat links, inspection, other players, and arbitrary tooltip sources are intentionally unsupported. If addon channels are disabled, neither wardrobe transport nor CharacterFrame appearance lines can synchronize.
- Hidden preview uses `DressUpModel:UndressSlot` when the build exposes it. A guarded fallback reconstructs the model from physical item links; on clients without the slot API, that fallback can temporarily show other overridden slots' original appearances until Reset Preview.
- Phase 2 opens immediately on supported gossip/quest, vendor, and trainer interactions; it cannot safely inject an option into arbitrary scripted gossip on this branch.
- Client service types that bypass all inspected hooks are not covered. Registration never changes their flags to manufacture an interaction path.
- Vehicle-passenger creatures are explicitly rejected in Phase 2. Entry resolution itself is location- and spawn-independent, so the registry is suitable for a future mobile Transmogrifier, but passenger interaction and moving-distance/session semantics require dedicated validation before removing this guard.
- Addon transport requires AzerothCore's addon channel to be enabled and has build-12340's 255-byte message limit; pages are therefore multipart.
- Backfill can prove only active persisted rewarded rows and uses current quest definitions; it cannot reconstruct missing repeat history, old choices, or historical reward definitions. Offline targets are intentionally unsupported.
- No saved outfit, search, favorites, cost system, legacy integration, or migration from `mod-transmog` exists.

No code change outside this repository is required. The target Content Manager must already include managed server resources and `ContentResourceApiV1` (Milestone 2), and its `2026_09_25_06_content_managed_server_resources.sql` migration must be present before building/activating this EPF.

## License

All module implementation is independently authored under the [MIT License](LICENSE). No AGPL implementation from `mod-transmog` was copied or adapted. `mod-native-transmog` is the sole appearance writer intended for PTR; production remains unchanged.
