# Phase 4C PTR deployment and validation

These are operator instructions only. Development does not deploy automatically. Use the isolated Playerbot PTR,
record the current module revision, config, database backups, worldserver hash, ACTIVE/APPLIED Content Manager build,
client EPF hash, and Portalkeeper generation, and confirm that no production target is selected.

## Exact deployment sequence

1. Stop the PTR worldserver and back up its character/world databases and current runtime artifacts.
2. Place this reviewed checkout at `<PLAYERBOT>/modules/mod-native-transmog`; exclude `mod-transmog` from the build.
3. Install `conf/mod_native_transmog.conf.dist` through the existing module config flow without changing the realm's
   reviewed settings. Confirm `AddonChannel = 1` in `worldserver.conf`.
4. Configure the Playerbot branch with the PTR's normal Release options, build and install `worldserver`, and verify
   that all module translation units and the executable link succeed and the generated loader contains
   `Addmod_native_transmogScripts`.
5. Run the normal AzerothCore SQL updater. Phase 4C has no migration; the latest module migration remains
   `2026_11_04_00_native_transmog_hidden_state.sql`.
6. From the module checkout, build twice and require identical hashes, then check the committed package:

   ```bash
   python3 content/build_epf.py
   sha256sum content/mod-native-transmog.epf
   python3 content/build_epf.py
   sha256sum content/mod-native-transmog.epf
   python3 content/build_epf.py --check
   ```

7. Put `content/mod-native-transmog.epf` in the existing PTR Content Manager discovery directory. In the PTR
   worldserver console (or with the established authorized GM), run:

   ```text
   .content scan
   .content install mod-native-transmog
   .content build
   .content build list
   .content activate <new-build-number>
   .content build list
   .content allocations
   ```

   For an already-installed package, use the realm's established update operation rather than uninstalling it.
   Record the STAGED build, then confirm the selected build becomes ACTIVE/APPLIED with verified parity and the
   `protected-framexml` requirement.
8. Restart only PTR so its server bundle and managed Transmogrifier template load. Resolve the allocated entry with
   `.content allocations` or `.nativetransmog npc list`, and reuse or create the reviewed PTR spawn.
9. Publish that activated isolated client generation through the existing Portalkeeper protected-FrameXML flow.
   Do not copy loose FrameXML, install an addon, edit the cumulative TOC manually, or modify Portalkeeper.

## Collection notification validation

- [ ] Acquire one eligible, uncollected appearance through loot/storage and confirm exactly one normal chat line:
      `Appearance saved: <actual item name>`.
- [ ] Acquire another entry with the same composite appearance identity and confirm no message.
- [ ] Unequip/re-equip the item repeatedly and confirm no message.
- [ ] Equip an eligible previously owned and uncollected item for the first time and confirm exactly one message.
- [ ] Validate receiving/trade/mail/vendor and live quest-reward paths already supported by `CollectionService`.
- [ ] Run preview and execution of a historical quest backfill and confirm no appearance-saved messages.
- [ ] With collection disabled, confirm no collection row and no message. Restore the reviewed setting afterward.
- [ ] Against a disposable database fault simulation, make collection persistence fail and confirm no message and no
      in-memory unlock. Restore database health and confirm a later successful insert produces one message.
- [ ] In account-wide mode, unlock on character A, then acquire/equip the same appearance on character B and confirm
      B receives no message. Repeat in character-specific mode and confirm each character can unlock once.
- [ ] Apply, remove, and hide appearances and confirm none of those operations emits an unlock message.

## Tooltip and synchronization validation

- [ ] Before visiting a Transmogrifier after login, open CharacterFrame and hover an original equipped item. Confirm
      its full ordinary tooltip is unchanged and no appearance line is present.
- [ ] Before visiting a Transmogrifier, hover an item with a persisted applied override. Confirm the final line is
      `Transmogrified to: <actual applied source name>`, not the physical item's name.
- [ ] Before visiting a Transmogrifier, hover a persisted hidden item and confirm `Appearance: Hidden`.
- [ ] Repeat those checks in the wardrobe. Names and states must match CharacterFrame.
- [ ] Use two collected source entries that share a display ID where available; confirm the applied canonical source
      entry's name is shown rather than a display-ID guess or the physical target name.
- [ ] Hover repeatedly, move between slots, close/reopen CharacterFrame, and allow tooltip refreshes. Confirm the
      appearance line never duplicates and item name, quality, stats, enchants, gems/sockets, durability,
      requirements, sell price, and comparison tooltips remain intact.
- [ ] Preview an appearance without applying it and confirm neither wardrobe nor CharacterFrame reports it applied.
- [ ] Apply, Hide, and Remove through an authorized NPC session; confirm server success updates the affected slot and
      Remove clears the extra line. State-changing requests must still fail after session expiry.
- [ ] Swap, unequip, and equip items across supported slots. Confirm no unequipped/new item inherits another physical
      item's override state and only the changed slot updates.
- [ ] Relog, execute `/reload`, and restart worldserver. Before opening the Transmogrifier each time, confirm persisted
      applied/hidden tooltip state is restored through read-only `SYNC`.
- [ ] Disable addon channels only in a disposable test and confirm the documented transport dependency; restore
      `AddonChannel = 1` before continuing.

## Relic and regression validation

- [ ] On paladin, druid, shaman, and death knight where practical, hover/click the ranged/relic position and confirm
      `Relic appearances cannot be customized.` It must not say that the class cannot equip the slot.
- [ ] On a ranged-weapon class, confirm the same position remains a normal customizable ranged slot.
- [ ] Confirm no relic catalog or application is introduced and server-side restrictions remain unchanged.
- [ ] Run the complete Phase 4B paper-doll, Hide, preview, pagination, rotation, persistence, observer, mirror-image,
      enchant, and weapon-gameplay regression plan.
- [ ] Keep FrameXML errors visible and record client build, race/class/gender, UI scale, configuration, screenshots,
      server logs, hashes, and pass/fail evidence. Do not mark client support complete without this evidence.

## Rollback

Stop PTR, preserve evidence, reactivate the recorded prior Content Manager/client build, restore the prior reviewed
module/config/worldserver, and restart PTR. Phase 4C adds no SQL migration, so rollback does not rewrite collection
or override data. Restore the database backup only if destructive fault testing or unrelated validation requires it.
