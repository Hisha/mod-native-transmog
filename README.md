# mod-native-transmog

`mod-native-transmog` is an independently authored, MIT-licensed native AzerothCore module and protected-FrameXML package for WoW 3.3.5a build 12340. It does not use a standalone addon and does not modify `azerothcore/mod-transmog`.

Phase 1's in-game validated preview wardrobe is preserved: character model and rotation, slot browser, icons/tooltips, simultaneous previews, reset, and the temporary `/wardrobe` command. Phase 2 adds a reusable, server-authorized NPC service. It still does **not** apply or persist appearances, manage collections, migrate existing transmogrification data, or save outfits.

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
NativeTransmog.AllowTwoHandAppearanceOnOneHand = 0
NativeTransmog.AllowOneHandAppearanceOnTwoHand = 0
```

The first four settings control the module and registry scopes. The weapon settings remain reserved and unenforced because appearance application is out of scope.

## GM commands

Select a creature before using selection-based commands:

```text
.nativetransmog npc add entry
.nativetransmog npc add spawn
.nativetransmog npc remove entry
.nativetransmog npc remove spawn
.nativetransmog npc info
.nativetransmog npc list
```

Add uses AzerothCore's existing NPC-add RBAC permission, remove uses NPC-delete, and list/info use NPC-info. Ordinary players therefore cannot manage registrations. Adds, removals, and re-enables update the in-memory registry immediately and synchronously persist to the world database; a restart reloads all rows.

## Installation and PTR deployment

1. Install this repository as `modules/mod-native-transmog` in the Playerbot core and leave `mod-transmog` installed and configured normally.
2. Apply the normal AzerothCore module SQL updater. Existing Phase 1 realms receive `data/sql/db-world/updates/2026_10_28_00_native_transmog_npc_service.sql`; clean databases also have the equivalent base SQL.
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
python3 -m unittest tests/test_phase1.py tests/test_phase2.py
python3 tests/verify_catalog.py \
  /path/to/azerothcore-wotlk/data/sql/base/db_world/item_template.sql
```

The checks cover Phase 1 UI regressions, deterministic EPF output, schema/config/registry contracts, registration resolution and persistence paths, duplicate/re-enable/removal behavior, RBAC command declarations, interaction validation, additive hooks, transport handling, debug separation, and session cleanup hooks. See [test results](docs/TEST_RESULTS.md) and the [PTR checklist](docs/PTR_VALIDATION.md).

## Known limitations and future mobile NPCs

- PTR validation for Phase 2 has not been performed; automated checks and a Playerbot module build do not prove in-game behavior.
- Phase 2 opens immediately on supported gossip/quest, vendor, and trainer interactions; it cannot safely inject an option into arbitrary scripted gossip on this branch.
- Client service types that bypass all inspected hooks are not covered. Registration never changes their flags to manufacture an interaction path.
- Vehicle-passenger creatures are explicitly rejected in Phase 2. Entry resolution itself is location- and spawn-independent, so the registry is suitable for a future mobile Transmogrifier, but passenger interaction and moving-distance/session semantics require dedicated validation before removing this guard.
- The preview catalog remains a deterministic fixture, not an unlock collection or usability filter.
- No persistent appearance, collection, saved outfit, item application, or migration from `mod-transmog` exists.

No code change outside this repository is required. The target Content Manager must already include managed server resources and `ContentResourceApiV1` (Milestone 2), and its `2026_09_25_06_content_managed_server_resources.sql` migration must be present before building/activating this EPF.

## License

All module implementation is independently authored under the [MIT License](LICENSE). No AGPL implementation from `mod-transmog` was copied or adapted.
