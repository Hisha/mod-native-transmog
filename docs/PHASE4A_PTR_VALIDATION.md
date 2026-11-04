# Phase 4A PTR deployment and validation

This procedure targets only the isolated Playerbot PTR. It does not authorize deployment, database mutation,
Content Manager activation, Portalkeeper publication, commit, or push. Back up the current PTR character/world
databases, module/config, worldserver, active Content Manager build, and published MPQ before beginning. Record
worldserver logs, SQL updater output, hashes, client Lua errors, screenshots, observer evidence, and pass/fail.

## Exact deployment sequence

1. Review the Phase 4A diff and confirm the PTR core is the intended AzerothCore 3.3.5a Playerbot branch,
   `mod-native-transmog` is the only visible-item override writer, and `mod-transmog` is absent from this PTR
   build/load. Do not change production or Portalkeeper code.
2. Stop PTR. Replace `<PTR_CORE>/modules/mod-native-transmog` with this reviewed tree and install
   `conf/mod_native_transmog.conf.dist` through the normal module config flow. Preserve realm-specific values;
   add exactly `NativeTransmog.HideWeapons = 0`. Confirm `AddonChannel = 1` in `worldserver.conf`.
3. Run the normal AzerothCore character database updater. Confirm
   `2026_11_04_00_native_transmog_hidden_state.sql` adds
   `native_transmog_item_override.override_state TINYINT UNSIGNED NOT NULL DEFAULT 0`. Query existing rows and
   prove their appearance fields are unchanged and their state is `0`. Re-run the updater and confirm no error or
   duplicate/destructive change. Do not drop or truncate the table.
4. Configure and build the actual PTR toolchain with its existing Playerbot, module, build type, and install
   options. Confirm all six module translation units compile, `worldserver` links, the generated loader contains
   `Addmod_native_transmogScripts`, and it contains no `Addmod_transmogScripts`.
5. In the reviewed module checkout run twice:

   ```bash
   python3 content/build_epf.py
   python3 content/build_epf.py --check
   sha256sum content/mod-native-transmog.epf
   ```

   Confirm both rebuilds have the same SHA-256. Put the EPF in the existing Content Manager discovery location.
6. With the PTR worldserver/Content Manager workflow, run `.content scan`, install/update
   `mod-native-transmog`, run `.content build`, and inspect `.content build list`. Record the STAGED build,
   package/file counts, protected-FrameXML requirement, and artifact hash. Activate exactly that build with
   `.content activate <build-number>`, then confirm ACTIVE/APPLIED and record the retained
   `dedicated-transmogrifier` allocation using `.content allocations`.
7. Use the established Portalkeeper realm refresh/distribution operation to publish that exact active artifact.
   Do not edit a generated MPQ or create `Interface/AddOns`. Launch the isolated build-12340 client through
   Portalkeeper and confirm its selected MPQ hash matches Content Manager.
8. Start PTR. Confirm the module reports collection/application/wardrobe initialization and the reviewed
   `hide-weapons: false` policy with no database or Lua/protocol errors. Spawn the retained dedicated entry only
   if required, then interact with it as a normal player.

## Server and persistence checks

- [ ] Existing Phase 3C collected-appearance rows still load, render, replace, and remove.
- [ ] An ordinary client without an authorized, live Transmogrifier NPC session cannot apply, hide, or remove.
- [ ] Hide creates one item-GUID row with `override_state=1` and zero appearance identity fields. It does not
  change `item_instance`, item template data, entry, owner, contained/bag position, count, durability,
  enchantments, gems, stats, spells, or combat results.
- [ ] Hide creates no `native_transmog_collection` row, unlock notification, or provenance change.
- [ ] Apply collected → Hide → Remove returns to the physical appearance.
- [ ] Hide → Apply collected replaces state `1` with state `0` and the validated appearance identity.
- [ ] Unequip/re-equip and ordinary equipment swaps keep the override attached to the same item GUID. A stale
  open catalog cannot mutate the replacement item.
- [ ] Relog and a full worldserver stop/start restore hidden and collected states.
- [ ] Bank/mail/trade/auction/ownership-transfer cleanup remains consistent with the Phase 3C ownership policy;
  no former owner's cached row renders on a new owner.
- [ ] Reconfigure `NativeTransmog.HideWeapons=1`, reload/restart as required by PTR policy, and verify weapon
  hiding. Return it to `0`: online visible fields refresh to the real weapons, new hide requests are rejected,
  and hidden-weapon rows remain in the database. Re-enable it and confirm the retained rows hide again.
- [ ] Shields and held-in-off-hand items follow the off-hand weapon-hiding switch even though their item class is
  armor.

## Full-slot client matrix

For Head, Shoulders, Shirt, Chest, Waist, Legs, Feet, Wrists, Hands, Back, Main Hand, Off Hand, Ranged, and
Tabard, equip a real compatible item and record the character race/gender and source/target entries.

- [ ] The slot control selects the correct AzerothCore equipment slot and reports the correct equipped item.
- [ ] The catalog contains only collected entries accepted by the Phase 3C validator. Verify armor subclass,
  chest/robe interchange, main/off-hand placement, ranged types, and the two handedness settings.
- [ ] Hide Appearance is first, is visibly distinct, has a tooltip, and does not change Next/Previous cursors or
  the configured number of collected entries. It remains present when the compatible collection is empty.
- [ ] Selecting Hide changes only the local preview. Note that build-12340 exposes no single-slot undress method;
  preview rebuilds the model from equipped item links, so other already-transmogrified slots may temporarily
  preview their physical appearances. This is preview-only and must not be mistaken for a server mutation.
- [ ] Apply Hide waits for server acknowledgment, marks the Hide tile as applied, removes the selected model on
  the player's model and a nearby observer, and leaves gameplay effects intact.
- [ ] Remove Appearance waits for acknowledgment, deletes the row, restores the physical model for player and
  observer, and clears the applied marker.
- [ ] A compatible collected appearance can be applied after Hide, and Hide can replace it again.

With `NativeTransmog.HideWeapons=0`, Main Hand, Off Hand, and Ranged must omit Hide while all non-weapon slots
retain it. With `1`, repeat the hide/apply/remove checks for one-hand, two-hand, dual-wield, shield, held-in-off-hand,
bow/gun/crossbow, wand, and thrown equipment that the test character can legally equip.

## Rendering and regression checks

- [ ] Validate the player's own model and at least one nearby independent client observer after application,
  movement, combat start/end, death/resurrection, teleport/map change, equipment refresh, relog, and worldserver
  restart. Do not mark observer rendering verified from the same client or from database/object-field inspection.
- [ ] Validate head/back behavior with the stock Hide Helm/Hide Cloak flags both on and off.
- [ ] Validate enchant glows on visible weapons before/after restoring original. Record client behavior for hidden
  weapons; the server preserves enchant fields and does not modify enchantments.
- [ ] Trigger a mirror image with hidden Head, Shoulders, Shirt, Chest, Waist, Legs, Feet, Wrists, Hands, Back,
  and Tabard where class mechanics permit; record which slots the stock mirror-image packet actually includes.
- [ ] Confirm FrameXML loads without error, all 14 controls fit at common UI scales, icons/tooltips work, and
  Reset Preview/Close remain non-mutating.
- [ ] Re-run Phase 3C compatibility, persistence, transfer/deletion, and Phase 3D catalog/session/pagination/stale
  snapshot regressions. Confirm equipment-triggered collection remains idempotent.
- [ ] Confirm `/wardrobe` and `/nativetransmog` remain preview-only and cannot issue a state-changing request.

## Known pre-PTR limitations

No build-12340 client validation has been performed by the implementation work alone. Public
`PLAYER_VISIBLE_ITEM_*_ENTRYID = 0` is the same core representation used for an empty visible slot, and the core
publishes those fields to observers; the mirror-image hook likewise accepts display `0`. That establishes the
protocol path but does not prove every slot/race/gender client renderer. The Hide preview reconstruction limitation
is described above. Record any slot that the actual client refuses to hide and report it as unsupported rather
than claiming success.

## Rollback

Stop PTR and preserve evidence. Restore the prior module/config/worldserver, reactivate the recorded prior Content
Manager build, refresh the existing Portalkeeper realm metadata, and restart. Leave `override_state` and module rows
in place unless a demonstrated database problem requires restoring the backup: the additive column is inert to the
prior binary, and preserving rows avoids destructive rollback. Never enable a second transmog writer, install a
standalone addon, edit generated MPQs, or change Portalkeeper to repair a Phase 4A failure.

Manual checks remain **not run** until evidence is captured on PTR.
