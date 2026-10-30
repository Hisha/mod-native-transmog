# Phase 3C compatibility audit

## Decision

`mod-native-transmog` Phase 3C and the audited `azerothcore/mod-transmog` implementation **cannot safely render applied appearances at the same time**. Both implementations would be independent writers of the same player visible-item entry fields, with independent item-instance persistence and no ownership/arbitration API between them.

Phase 3C appearance application must therefore be tested on PTR with `mod-transmog` excluded from the PTR worldserver build/load. Its source checkout, configuration, and database records must remain intact. Setting only `Transmogrification.Enable = 0` is not sufficient isolation.

This is the mandatory compatibility gate from the Phase 3C requirements. No Phase 3C application service, renderer, persistence table, application command, or removal command was introduced after finding this conflict.

## Audit scope and source identity

The following source was inspected:

- `mod-native-transmog` in this repository, including `src/NativeTransmogModule.cpp`, `src/NativeTransmogService.cpp`, `src/NativeTransmogCollection.cpp`, `src/mod_native_transmog_loader.cpp`, `CMakeLists.txt`, and the existing character/world migrations.
- Playerbot AzerothCore checkout `/home/smithkt/aicode_folder/azerothcore-wotlk`, branch `Playerbot`, commit `8a4e76eac8c4ccebf547113afe7b51d6c3e91641`.
- Official `azerothcore/mod-transmog` source at commit `327753a05b9024f2a90738bb08e9b8afc2fc9a21` (2026-10-10), inspected from `/tmp/mod-native-transmog-audit-mod-transmog`.
- A character-database schema/data snapshot in the available workspace under `/home/smithkt/Documents/Codex/2026-09-07/referenced-chatgpt-conversation-this-is-an/work/transmog/`. Its `custom_transmogrification` and `custom_transmogrification_sets` schemas match the audited upstream module contract.

The checked-out Playerbot core's `modules/` directory is empty, and no installed `mod-transmog` source checkout exists elsewhere in the readable local repositories. The exact PTR-installed `mod-transmog` commit is consequently **not locally verifiable**. The official source and available database snapshot are sufficient to establish the dual-writer conflict, but PTR deployment must record the installed commit before validation. A materially modified/private fork must be re-audited.

No `mod-transmog` source, configuration, database row, or core source was changed by this audit.

## Existing `mod-transmog` mechanism

### In-memory and persistent representation

`Transmogrification::SetFakeEntry` in `src/Transmogrification.cpp` stores:

- item instance GUID in `custom_transmogrification.GUID`;
- source item-template entry in `FakeEntry`;
- character GUID in `Owner`.

It simultaneously populates `entryMap[playerGuid][itemGuid]` and `dataMap[itemGuid]`, then calls `UpdateItem`. `UpdateItem` calls `Player::SetVisibleItemSlot` for equipped items and sends an item update to the owner. `DeleteFakeEntry` removes the persistent/in-memory fake entry and calls the same refresh path.

Relevant audited functions are:

- `Transmogrification::GetFakeEntry`, `UpdateItem`, `SetFakeEntry`, `DeleteFakeEntry`, and `DeleteFakeFromDB` in `src/Transmogrification.cpp`;
- `PS_Transmogrification::OnPlayerAfterSetVisibleItemSlot`, `OnPlayerAfterMoveItemFromInventory`, `OnPlayerLogin`, and `OnPlayerLogout` in `src/transmog_scripts.cpp`;
- `global_transmog_script::OnItemDelFromDB` and `OnMirrorImageDisplayItem` in `src/transmog_scripts.cpp`;
- `unit_transmog_script::ShouldTrackValuesUpdatePosByIndex` and `OnPatchValuesUpdate` in `src/transmog_scripts.cpp`.

### Player visible fields and synchronization

The Playerbot core's `Player::SetVisibleItemSlot` in `src/server/game/Entities/Player/PlayerStorage.cpp` first writes the real equipped item entry to:

```text
PLAYER_VISIBLE_ITEM_1_ENTRYID + slot * 2
```

It then dispatches `PLAYERHOOK_ON_AFTER_SET_VISIBLE_ITEM_SLOT`. `mod-transmog` handles that hook and replaces the entry with its fake item-template entry. Normal AzerothCore object-field update propagation then synchronizes the changed player field to the owner and nearby clients. This changes visual identity only; it does not replace the equipped `Item`, its stats, damage, speed, enchantments, equipment position, or combat rules.

The module additionally handles mirror-image display resolution and outbound value-update patching. The latter restores the real item entry for observers who hide transmogs and when `Transmogrification.Enable` is false.

### Login, logout, equipment, and item lifecycle

On login, `mod-transmog` loads every `custom_transmogrification` row for the character into its caches and calls `SetVisibleItemSlot` for equipped items. On logout it unloads those caches.

Core equipment paths call `SetVisibleItemSlot` from `Player::VisualizeItem` and when an equipment position is cleared, so the module's after-visible-slot hook reapplies its fake entry after normal equipment refreshes.

`PS_Transmogrification::OnPlayerAfterMoveItemFromInventory` deletes the fake entry when the item leaves character inventory through the core transfer path. `global_transmog_script::OnItemDelFromDB` deletes it in the caller's character-database transaction when the item instance is deleted. Startup also deletes rows whose item instance no longer exists.

These lifecycle rules belong only to `mod-transmog`; they do not inspect or update a native Phase 3C table.

### Initialization order

`Addmod_transmogScripts` registers the module's global, unit, creature, player, and world scripts. `mod-native-transmog` independently registers its scripts through `Addmod_native_transmogScripts`.

In the inspected core, module directories are discovered with a CMake glob, loader calls are generated from that list, and enabled hooks are appended to vectors and invoked in registration order. There is no visible-item writer priority, conflict detector, or last-writer arbitration contract. Static and dynamic module configurations may also produce different load circumstances. Depending on registration order to select one module's appearance is therefore undocumented and unsafe.

## Hook conflicts

### Fatal rendering conflict

A correct Phase 3C implementation must restore an item-instance override after login and equipment refresh and must write or patch the same visible entry field used by `mod-transmog`. If both modules contain an override for one equipped item:

1. core writes the real item entry;
2. each module attempts to replace it with its own persisted appearance;
3. the last registered writer determines the current field value;
4. a later login, equip, removal, or refresh can make a different persisted source visible;
5. removing one module's override can expose the other module's override rather than the real item.

The two databases can consequently describe different appearances while only one nondeterministically reaches the client. There is no safe way for `mod-native-transmog` to infer that it owns the field without coupling to or modifying `mod-transmog`.

### Configuration-only disable is unsafe

`Transmogrification.Enable = 0` does not unregister `mod-transmog` hooks. In the audited source:

- `OnPlayerLogin` still loads `custom_transmogrification` and refreshes equipped slots;
- `OnPlayerAfterSetVisibleItemSlot` is not guarded by `IsEnabled()`;
- `unit_transmog_script::OnPatchValuesUpdate` replaces visible entries with the real equipped entry when the module is disabled.

That outbound patch would also erase a native module's appearance from updates. Therefore the only safe PTR isolation is not loading `mod-transmog` code into that worldserver.

### Non-fatal overlapping hooks

Both modules already observe item acquisition and quest completion for their separate collection systems. This can create independent collection rows but does not itself corrupt either database. NPC and command namespaces are separate. These overlaps are not the reason for the stop decision.

## Database coexistence

The schemas are name-separated and can remain installed together:

| Owner | Tables |
|---|---|
| `mod-transmog` | `custom_transmogrification`, `custom_transmogrification_sets`, `custom_unlocked_appearances` |
| `mod-native-transmog` Phase 2-3B | `native_transmog_npc_registration`, `native_transmog_collection` |

`mod-transmog.custom_transmogrification` uses the item instance as its primary key and records an owner character. The current native collection table records entitlements only; it has no applied-appearance rows. There are no shared table names, foreign keys, migrations, or update statements.

Database coexistence is safe while application rendering is isolated. Disabling the module binary must not drop, truncate, migrate, or edit any `custom_*` table. The retained rows allow exact restoration when the old module is re-enabled.

## Runtime coexistence verdict

The existing Phase 1-3B native functionality can coexist with `mod-transmog` because it does not apply appearances. Phase 3C appearance rendering cannot safely coexist with the audited `mod-transmog` runtime.

This verdict is about simultaneous appearance control, not compilation. A successful compile/link with both modules would not resolve the field ownership conflict.

## Required PTR-only disable procedure

Perform this only during a separately authorized PTR deployment; this audit did not deploy anything.

1. Record the PTR core commit, `mod-transmog` commit, current CMake module linkage (`static` or `dynamic`), install prefix, worldserver binary hash, and effective `transmog.conf` hash.
2. Back up the PTR character database, including all three `mod-transmog` tables. The backup is a precaution; the disable procedure must not alter those tables.
3. Stop the PTR worldserver cleanly.
4. Leave `modules/mod-transmog`, `transmog.conf`, and all `custom_*` tables in place.
5. Reconfigure the Playerbot build with the module-specific cache value disabled:

   ```bash
   cmake <PTR_CORE> <all-existing-PTR-options> -D'MODULE_MOD-TRANSMOG=disabled'
   ```

   Preserve the existing `MODULES`, build type, install prefix, Playerbot, and all unrelated module options. Do not use `Transmogrification.Enable=0` as a substitute.
6. Build and install the PTR worldserver through its normal process. For a previously dynamic build, the inspected core's install rules remove the generated `mod_transmog` shared library when the module is disabled; archive that generated binary first if the deployment process does not retain build artifacts. This does not remove module source or data.
7. Before starting PTR, inspect the generated module loader or installed script-module directory and confirm that `Addmod_transmogScripts`/the `mod_transmog` shared library is absent while `mod-native-transmog` remains present.
8. Start PTR and confirm startup/configuration logs do not register/load `mod-transmog`. Confirm the `custom_transmogrification`, `custom_transmogrification_sets`, and `custom_unlocked_appearances` row counts and checksums are unchanged.
9. Only then perform Phase 3C application tests. Production remains unchanged.

If the PTR deployment uses a wrapper that regenerates CMake options, set the equivalent module cache entry in that wrapper and verify the final `CMakeCache.txt` contains:

```text
MODULE_MOD-TRANSMOG:STRING=disabled
```

Do not rename the module directory to manipulate discovery order, edit its loader, remove its source, delete its installed configuration, or delete its database records.

## Rollback procedure

1. Stop the PTR worldserver cleanly.
2. Disable `mod-native-transmog` Phase 3C through its documented module/config rollback once such an implementation has passed a future compatibility gate. Do not leave two appearance writers active during the transition.
3. Restore the recorded `mod-transmog` linkage value, normally `default`, `static`, or `dynamic`, for example:

   ```bash
   cmake <PTR_CORE> <recorded-PTR-options> -D'MODULE_MOD-TRANSMOG=default'
   ```

4. Rebuild and install through the normal PTR process, or restore the recorded complete prior PTR server artifact as one unit. Do not mix an old dynamic module with an incompatible new core binary.
5. Restore the recorded `transmog.conf` unchanged and start PTR.
6. Verify the installed module commit, startup registration, an existing saved appearance, removal, relog restoration, and the row counts/checksums of all `custom_*` tables.
7. Do not restore the database backup merely because the module was disabled: its rows were intentionally preserved. Restore the backup only for an independently demonstrated migration/data failure and with explicit authorization.

## Unresolved compatibility risks and unblock conditions

- The exact PTR-installed `mod-transmog` source revision was unavailable locally. Record and inspect it before any PTR build. A fork might add another rendering path or different disable behavior.
- The current official module has no public arbitration API through which another appearance module can claim a visible slot.
- A configuration-only disable remains unsafe because loaded hooks still touch the visible fields.
- Hook registration order is an implementation detail, not a supported coexistence mechanism.
- Mirror images and per-observer hide settings add outbound rewriting beyond the base visible-field conflict.
- Both collection systems will continue to collect independently if both runtimes are later re-enabled; no migration or entitlement equivalence is implied.

Phase 3C implementation can resume only after one of these conditions is explicitly accepted:

1. PTR tests load only `mod-native-transmog` as the appearance writer, using the build-time isolation procedure above; or
2. a narrowly scoped, documented core-level appearance-provider arbitration API is designed and both modules adopt it; or
3. `mod-native-transmog` deliberately delegates rendering/persistence to an audited public `mod-transmog` API (none exists in the inspected revision), with the licensing and independent-authorship implications reviewed first.

The first option requires no core patch and is the recommended PTR path, but it is an operational choice that must be authorized before implementation proceeds past this gate.
