# Source inspection record

Inspection date: 2026-10-28. Revisions are the local checked-out commits used to design Phases 1 and 2.

| Project | Revision | Relevant locations and conclusion |
| --- | --- | --- |
| `mod-native-transmog` | `73745fedeabc95b623146244fd1db526f58a24e7` (pre-implementation) | Existing repository contained only MIT `LICENSE` and a one-line `README.md`. |
| `Hisha/mod-content-manager` | `e9927be2c2f0e262b8513a68f23805fc5f136191` | In addition to Schema 3/FrameXML composition, `ContentPackage.cpp`, `ContentBuildService.cpp`, `ContentManagedServer*`, and `ContentServerDeployment*` already implement symbolic managed creature templates, retained allocation, model-child ownership, guarded server apply, and parity. `ContentCapabilityProvider.cpp` and `src/api/ContentResourceApiV1.h` provide verified ACTIVE/APPLIED runtime resolution. |
| FrameForge | `1ccb522a23c31dba8626ca0b51220c86d63d9186` | `src/FrameForge.Core/Export/Wow335Export.cs` emits build-12340 manifest v2, `FrameForgeLayout.xml`, and asset manifests. `docs/WOW_335_EXPORT.md` documents the portable output. Phase 1's dynamic Lua is independently authored and carried as ordinary Schema 3 resources, so the exporter needs no extension. |
| AzerothCore Playerbot | `8a4e76eac8c4ccebf547113afe7b51d6c3e91641` (`Playerbot`) | `modules/CMakeLists.txt`, `ModulesLoader.cpp.in.cmake`, and `how_to_make_a_module.md` establish native module discovery/registration conventions. `data/sql/base/db_world/item_template.sql` was used to verify the test catalog IDs and inventory types. |
| `mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` | Installed alongside the core; no Phase 1 integration point or modification is needed. |
| Portalkeeper | `09703e8c8ad4680bafee865312c0615d3bb51c89` | `Models/RealmInfo.cs`, `Services/RealmConfigurationService.cs`, `RealmExecutableService.cs`, and `docs/isolated-runtime-checkpoint6.md` implement the established `protected-framexml` requirement, generation-2 selection, and isolated runtime preparation. No change is needed or made. The checkout had an unrelated untracked `scripts/__pycache__/`, which was not touched. |

The installed `azerothcore/mod-transmog` checkout was not present under the inspected AzerothCore `modules/` directory or the available local repositories. Consequently, no behavior or source was borrowed from it. Phase 1 has no SQL, hooks, opcodes, NPC service, or persistent state and therefore coexists by isolation; PTR validation must still confirm the separately installed realm module remains operational.

## Pipeline findings

1. Schema 3 is parsed by `ContentPackage`; older schemas and Schema 3 packages without optional FrameXML fields remain supported.
2. Raw XML/Lua resources are declared in `content[]` and staged at canonical `Interface/FrameXML/...` targets.
3. `clientFrameXml.loadEntries[]` adds a managed XML file after a unique verified stock entry. Phase 1 anchors after `DressUpFrame.xml` so the stock model support is loaded first.
4. The verified 2,820-byte build-12340 `FrameXML.toc` is an EPF input, not a raw MPQ target. The composer owns the cumulative output.
5. Target ownership and path folding make collisions case-insensitive; raw ownership of `FrameXML.toc`, duplicate targets, missing anchors, ambiguous anchors, and cycles fail validation/build.
6. Staged content flows into deterministic cumulative MPQ assembly, whole-MPQ/parity hashes, build activation, publication, and rollback through existing content-manager services.
7. A non-empty FrameXML declaration automatically records `protected-framexml`; Portalkeeper consumes the matching realm requirement and distributes/prepares the isolated client as already implemented.

No `mod-content-manager`, FrameForge, Portalkeeper, or AzerothCore core change is necessary for Phase 1.

## Phase 2 Playerbot hook and protocol findings

The Phase 2 implementation was checked against Playerbot revision `8a4e76eac` in `/home/smithkt/aicode_folder/azerothcore-wotlk`:

- `NPCHandler.cpp::HandleGossipHelloOpcode` resolves the packet GUID with `Player::GetNPCIfCanInteractWith` before calling `ScriptMgr::OnGossipHello`. `QuestHandler.cpp::HandleQuestgiverHelloOpcode` performs the same server-side resolution and calls the same script hook.
- `CreatureScript.cpp::OnGossipHello` invokes every `AllCreatureScript::CanCreatureGossipHello` before clearing the gossip menu and dispatching the creature's assigned `CreatureScript`. Returning `false` preserves that dispatch, but anything added to the menu by the global hook would be cleared. Returning `true` consumes the interaction and suppresses existing behavior. Therefore an additive universal gossip option is not safe on this branch.
- `PLAYERHOOK_ON_SEND_LIST_INVENTORY` observes vendor-only interaction. The hook fires before core vendor validation, so Phase 2 independently calls `GetNPCIfCanInteractWith` and trusts the resolved `Creature*`, never a client entry/spawn value. `PLAYERHOOK_ON_BEFORE_RECEIVE_SPELL_LIST_FROM_TRAINER` provides the corresponding validated trainer object.
- The persistent database identifier is `Creature::GetSpawnId()`. Runtime `ObjectGuid` counters are not used for registration. Dynamic creatures report spawn ID zero and remain eligible through entry registration.
- `Player::Whisper(payload, LANG_ADDON, player)` produces the stock self-whisper addon-message path. Protected build-12340 FrameXML can register `CHAT_MSG_ADDON` and `RegisterAddonMessagePrefix` without a standalone addon. Existing native modules in this workspace use the same channel.
- Player hooks for update, map change, and logout support session cleanup. Re-running `GetNPCIfCanInteractWith` covers disappearance, distance, map, life/reaction, and control-state changes; Phase 2 adds combat and vehicle-passenger guards.
- No generic hook was found for every possible direct NPC service opcode. Phase 2 covers gossip/quest hello, vendor list, and trainer list without altering flags. NPC types that bypass those paths are documented rather than silently rewritten.

## Phase 2 Content Manager findings

- Schema 2 and 3 already accept optional `creatureTemplates[]`; older EPFs and native modules retain their existing behavior.
- `creature-template.id` is allocated by the generic retained allocator and guarded against baseline/live/owned collisions.
- A creature declaration copies a bounded set of stock template fields and all one-to-four `creature_template_model` children. Model rows share the allocated template identity and are checked/applied transactionally; no separate model ID API is needed.
- Stock template `28699` (`Charles Worth`) owns the desired single display row `25615`, so it is a suitable donor. EPF overrides replace the visible/service fields and remove its SmartAI assignment.
- Runtime consumers vendor the V1 header, discover the provider through `ScriptRegistry<WorldScript>`, and call `ResolveResource(package, symbol, "creature-template.id", ...)`. A retained lease alone is deliberately not sufficient: the resource must belong to the current ACTIVE build, be server APPLIED/parity-verified, and be loaded after restart.
- `creatureSpawns[]` is also supported, but the module intentionally does not declare a fixed dedicated spawn. Administrators retain the existing ability to create any number of spawns, while the module's generic registration table continues to support arbitrary creature entries and persistent spawn IDs.

No core, Content Manager, FrameForge, Portalkeeper, or `mod-transmog` code change is required. Deployment does require Content Manager Milestone 2 and its existing `2026_09_25_06_content_managed_server_resources.sql` schema migration. The previous fixed entry `900100` is no longer declared, inserted, or referenced by module SQL/C++; a row created by an earlier unreleased migration is inert legacy data and is not deleted automatically because the module cannot prove ownership of a world row it did not allocate.

## Phase 3B Playerbot quest findings

Phase 3B was inspected against the same Playerbot revision `8a4e76eac8c4`:

- `QuestDef.h` defines six `RewardChoiceItemId` entries and four `RewardItemId` entries. No newer-version reward item fields exist in this branch.
- `Player::RewardQuest` grants only the chosen choice, grants every guaranteed reward, applies the remaining quest rewards, calls `SetRewardedQuest`, then `SaveToDB`, and finally invokes `OnPlayerCompleteQuest`. The module therefore uses `PLAYERHOOK_ON_PLAYER_COMPLETE_QUEST` as the safest available post-reward hook.
- `CompleteQuest` changes objective state and can precede actual turn-in; `OnPlayerBeforeQuestComplete`, quest acceptance, abandonment, gossip, and item-reward hooks do not establish the required successful all-reward transaction and are not used for enumeration.
- The character schema stores durable rewarded evidence in `character_queststatus_rewarded(guid, quest, active)` with primary key `(guid, quest)`. Core loads only active rows. `character_queststatus` is active-log state and can contain complete-but-not-rewarded quests, so Phase 3B excludes it.
- Rewarded storage proves at least one persisted reward. It does not preserve which choice was selected, the reward definition at completion time, or repeat count. Backfill consequently uses current loaded quest definitions and reports missing definitions without inference.
- The backfill command uses online `Player*` targets selected through the established command handler, checks command RBAC and target security, derives collection ownership from the authenticated session, and exposes no owner-ID or global scan input.
