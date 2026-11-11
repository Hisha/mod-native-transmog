# Native Transmog for AzerothCore

**`mod-native-transmog`** brings appearance collection, equipment transmogrification, and saved outfits to **World of Warcraft: Wrath of the Lich King 3.3.5a (build 12340)**. It is an independently authored, MIT-licensed AzerothCore module with a native, protected-FrameXML interface.

Players can collect appearances through gameplay, browse them in **Collections → Appearances**, and visit a **Warpweaver** to preview and apply appearances without changing their equipped items or stats. Custom outfits can be saved, edited, previewed, and applied together.

The project does **not** install a standalone WoW addon, patch AzerothCore's core, or depend on `mod-transmog`. Client content is distributed through the existing **EPF → mod-content-manager → Portalkeeper** pipeline.

## Features

| Feature | Description |
| --- | --- |
| Persistent appearance collection | Unlock eligible armor and weapon appearances from acquired/equipped items and completed quest rewards. |
| Account-wide or character-specific collection | Choose the collection scope through configuration; switching scopes does not erase either collection. |
| Collections browser | Browse collected appearances and preview Blizzard equipment sets, including incomplete sets. |
| Native Transmogrify window | A character paper doll, equipment-slot catalogs, previews, and apply/remove actions, opened through an authorized NPC. |
| Search and pagination | Search the **entire compatible collection for the selected slot** before pagination, not just the visible page. |
| Hide Appearance | Hide supported equipment appearances and restore their original look. Weapon hiding is optional and disabled by default. |
| Saved custom outfits | Create, edit, and save named outfits; load them into the preview and apply a complete outfit with **Apply Outfit**. |
| Compatibility enforcement | Server-side checks for collection ownership, class/race eligibility, armor type, weapon grouping, handedness, and equipped-slot compatibility. |
| Notifications and tooltips | Announce newly saved appearances and show applied/hidden state on supported equipped-item tooltips. |
| GM administration | NPC registration, collection diagnostics, controlled quest-history backfill, and appearance diagnostics. |

### Supported equipment slots

Head, Shoulders, Shirt, Chest, Waist, Legs, Feet, Wrists, Hands, Back, Main Hand, Off Hand, Ranged, and Tabard. Necklaces, rings, and trinkets are not appearance slots. Ranged/relic behavior depends on the equipped item and the client's supported slot behavior; relic appearances cannot be customized.

Armor generally requires the same armor subclass and visual slot, with chest/robe interchange. One-handed swords, axes, and maces share a compatibility group; two-handed swords, axes, maces, and polearms share another. These groups do not cross handedness. Shields remain shields. The server makes the final eligibility decision.

## How to use it

### 1. Collect appearances

Eligible appearances unlock as items enter your inventory or are equipped. Completing a quest can also unlock the eligible appearances from its offered rewards, subject to configuration. Newly persisted unlocks produce an `Appearance saved: <item name>` system message. Previously collected appearances do not generate duplicate notifications.

Historical quest rewards are **not** scanned automatically. An authorized GM can preview and run a limited backfill for a selected online character; see [quest collection design](docs/PHASE3B_ARCHITECTURE.md).

### 2. Browse Collections

Open the **Appearances** page under Collections to browse and preview collected appearances and equipment sets. The equipment-set browser includes a reviewed catalog of 263 Blizzard class-tier and PvP set identities from Classic, The Burning Crusade, and Wrath of the Lich King, subject to the installed game data.

Collections browsing does not require a Warpweaver. It is not a substitute for NPC authorization when applying an appearance to equipped gear. Custom sets can also be managed from the Collections interface. See [custom appearance sets](docs/CUSTOM_APPEARANCE_SETS.md) and [equipment-set data design](docs/PHASE5A_DATA_DESIGN.md).

### 3. Transmogrify equipment

Visit a **Warpweaver — Transmogrifier**. The module installs its own NPC (creature entry `14999992`) at nine default city locations.

In the Transmogrify window:

1. Choose an equipped slot on the character paper doll.
2. Browse or search the collected appearances compatible with that slot. Search is applied across all matching results **before** pages are formed.
3. Select an appearance to preview it, then use **Apply Appearance** to change that slot.
4. Use **Remove Appearance** to restore the item's original look, or **Hide Appearance** where supported.

Selecting an appearance or using **Reset Preview** does not modify equipped gear. The server validates application requests against the live NPC session, equipped item, and owned collection.

### 4. Save and apply an outfit

Build a look by selecting appearances across multiple slots, then save it as a named custom outfit. You can also manage saved custom sets in Collections.

To wear a saved outfit:

1. Open Transmogrify at a Warpweaver.
2. Choose the saved outfit from the dropdown.
3. Inspect the complete character preview.
4. Click **Apply Outfit** to apply the saved selections together.

**Selecting an outfit only previews it**; it does not automatically apply it. Apply Outfit is a separate server-authoritative action that reloads and validates the owned saved set. Explicitly hidden slots are respected, while **unspecified slots remain unchanged**. Equipped item IDs, statistics, enchantments, and gameplay behavior are not replaced by the selected appearances.

## Installation

### Requirements

- An AzerothCore **Playerbot-branch** build compatible with the module's hooks and WoW client **3.3.5a build 12340**.
- A configured `mod-content-manager` deployment supporting managed server resources, `ContentResourceApiV1` (Milestone 2), and the migration `2026_09_25_06_content_managed_server_resources.sql`.
- The existing `protected-framexml` realm requirement and EPF distribution path through Content Manager and Portalkeeper.
- AzerothCore addon-message transport enabled (`AddonChannel = 1`). This is the **stock client messaging facility**, not a standalone addon.

### Server and client setup

1. Install the repository as `modules/mod-native-transmog` in your AzerothCore source tree. **Do not run it alongside `mod-transmog` as a competing appearance writer.**
2. Apply the module's SQL migrations using the normal AzerothCore database updater. The world migration `2026_11_09_00_native_warpweavers.sql` installs the dedicated Warpweaver template and nine default spawns. Its one-time installation avoids recreating deleted or administrator-modified default NPCs on later runs.
3. Install `conf/mod_native_transmog.conf.dist` using the module configuration workflow. Review and enable the desired collection, application, and custom-set settings.
4. In `worldserver.conf`, set:

   ```ini
   AddonChannel = 1
   ```

5. Build and deploy the updated worldserver.
6. Generate and validate the client EPF:

   ```bash
   python3 content/build_epf.py
   python3 content/build_epf.py --check
   ```

7. Publish `content/mod-native-transmog.epf` through **mod-content-manager** and distribute/activate it through **Portalkeeper**. Restart the client after updating protected FrameXML.
8. Restart the worldserver and verify the native Warpweaver is available. For NPC migration and deployment checks, see [Native Warpweaver installation](docs/NATIVE_WARPWEAVER_INSTALLATION.md).

The EPF contains client UI content only; the module's SQL updater owns server-side Warpweaver installation. The EPF does not install a standalone addon, replace the raw FrameXML TOC, or require a custom network opcode.

### Configuration

The module's authoritative configuration file is **`conf/mod_native_transmog.conf.dist`**. The following are key settings documented by the project; consult the installed file for the full list and exact defaults.

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
NativeTransmog.CustomSets.Enable = 1
NativeTransmog.HideWeapons = 0
NativeTransmog.Wardrobe.PageSize = 24
NativeTransmog.Wardrobe.RequestCooldownMs = 250
NativeTransmog.Wardrobe.SnapshotLifetimeMs = 30000
```

The `NativeTransmog.CustomSets.Enable` setting is required for the saved-outfit workflow; verify its spelling and default against the current `.conf.dist` before publishing this README. The legacy `NativeTransmog.AllowTwoHandAppearanceOnOneHand` and `NativeTransmog.AllowOneHandAppearanceOnTwoHand` settings remain accepted for configuration compatibility but **do not** override the current weapon grouping and handedness rules.

Collection is account-wide by default. Changing to character-specific scope does not merge or delete account-wide rows. `NativeTransmog.HideWeapons` is disabled by default; this covers main hand, off hand (including shields), and ranged slots.

## GM commands

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

Select a creature before selection-based NPC commands. Appearance commands operate on the selected online player or the executing GM. Slot arguments use AzerothCore's zero-based equipment slot IDs (for example, Head `0`, Main Hand `15`, Off Hand `16`, Ranged `17`). GM commands use AzerothCore's existing RBAC permissions: NPC-add for adding/application/backfill execution, NPC-delete for removal, and NPC-info for read-only diagnostics/backfill preview and status.

## Architecture and security

The client uses protected FrameXML and stock build-12340 addon messages (`NTRANSMOG` over `LANG_ADDON` self-whisper). The Playerbot branch's existing hooks pass authenticated traffic to the module. No standalone addon, custom opcode, or AzerothCore core patch is needed.

The server—not the client—decides whether an NPC interaction is authorized, an appearance belongs to the player, and a source is compatible with the actual equipped item. Wardrobe requests use a time-limited NPC session and equipment-bound request snapshots; changing equipment invalidates pending slot authorization. Saved outfits are loaded and applied through the same authoritative appearance system, with transactional persistence of applicable overrides.

The collection's canonical appearance identity is `(display ID, item class, item subclass, inventory type)`. Appearance overrides are attached to the **real item-instance GUID**, not applied by replacing the item. Read-only appearance state also synchronizes to supported CharacterFrame tooltips.

Detailed implementation references:

- [Collection architecture](docs/PHASE3A_ARCHITECTURE.md)
- [Quest rewards and backfill](docs/PHASE3B_ARCHITECTURE.md)
- [Appearance application](docs/PHASE3C_ARCHITECTURE.md)
- [Transport design](docs/PHASE3D_TRANSPORT_DESIGN.md)
- [Native paper doll](docs/PHASE4B_ARCHITECTURE.md)
- [Equipment-set data design](docs/PHASE5A_DATA_DESIGN.md)
- [Custom appearance sets](docs/CUSTOM_APPEARANCE_SETS.md)

## Testing

Run the repository's automated checks:

```bash
python3 content/build_epf.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
```

The project also has PTR validation guides for [weapon compatibility and saved outfits](docs/WEAPON_COMPATIBILITY_SAVED_OUTFIT_PTR_VALIDATION.md) and [equipment portraits](docs/EQUIPMENT_PORTRAITS_PTR_VALIDATION.md), plus [test results](docs/TEST_RESULTS.md).

The saved-outfit workflow has been exercised on PTR: a custom outfit was loaded, previewed, and applied to the actual character, with the underlying item IDs and stats unchanged. Automated checks complement but do not replace gameplay testing across different races, equipment types, and client environments.

## Scope and limitations

- The Collections browser is available without a Warpweaver, but **applying or removing equipped appearances requires an authorized NPC interaction** (or an authorized GM diagnostic command).
- The wardrobe supports the fourteen visual slots listed above; it does not transmogrify jewelry or trinkets. Relic appearances are not customizable.
- Item previews use regular item icons in the catalog. The selected Head appearance has a specialized 3D portrait; equivalent close-up rendering for other equipment categories is not a supported feature.
- CharacterFrame appearance tooltip integration is limited to supported equipped-item slots. It does not extend to bag items, chat links, inspection, or other players' tooltips.
- Quest-history backfill relies on retained rewarded-quest records and current quest definitions. It cannot reconstruct missing historical choices or deleted quest definitions, and does not operate on offline targets.
- Registered existing NPCs retain their original gossip/script behavior. Some unsupported interaction types and vehicle-passenger creatures cannot serve as Warpweavers.
- This is not a migration tool for `mod-transmog`; existing legacy appearance records are not automatically imported.

## License

`mod-native-transmog` is independently authored and distributed under the [MIT License](LICENSE). No AGPL implementation from `mod-transmog` was copied or adapted.
