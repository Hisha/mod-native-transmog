# Phase 4B PTR deployment and validation

These are deployment instructions only. Phase 4B development must not deploy automatically. Use an isolated
Playerbot PTR and preserve the prior module checkout, configuration, databases, worldserver, active Content
Manager build, and published client MPQ before beginning.

## Build and package

1. Stop PTR. Back up the PTR character/world databases, module/config, worldserver binary, active Content Manager
   build ID, client package hash, and Portalkeeper generation. Confirm production is not targeted.
2. Install this reviewed checkout at `<PLAYERBOT>/modules/mod-native-transmog`. Confirm no `mod-transmog` source or
   generated library is part of this isolated build.
3. Install `conf/mod_native_transmog.conf.dist` through the normal module configuration flow and retain the realm's
   intended values. Confirm `AddonChannel = 1` in `worldserver.conf`.
4. Configure the checked-out Playerbot AzerothCore branch with the realm's normal compiler/options, build
   `worldserver`, and install it into the isolated PTR runtime. Confirm all module translation units and the final
   executable link succeed and that the generated module loader contains `Addmod_native_transmogScripts`.
5. Run the normal AzerothCore SQL updater. No Phase 4B migration exists; the latest module migration remains
   `2026_11_04_00_native_transmog_hidden_state.sql`.
6. Build the EPF twice and verify identical SHA-256 values:

   ```bash
   python3 content/build_epf.py
   sha256sum content/mod-native-transmog.epf
   python3 content/build_epf.py
   sha256sum content/mod-native-transmog.epf
   python3 content/build_epf.py --check
   ```

7. Put `content/mod-native-transmog.epf` in the existing Content Manager discovery location, then run in the PTR
   worldserver console or as an authorized Content Manager GM:

   ```text
   .content scan
   .content install mod-native-transmog
   .content build
   .content build list
   .content activate <new-build-number>
   .content build list
   .content allocations
   ```

   If already installed, use the realm's established package-update operation instead of uninstalling. Record the
   STAGED build before activation and confirm the selected build becomes ACTIVE/APPLIED with verified parity and a
   `protected-framexml` requirement. Activate the new build only on PTR.
8. Restart PTR so the applied managed Transmogrifier template is loaded. Resolve its active allocated entry with
   `.content allocations` or `.nativetransmog npc list`; create or reuse the reviewed PTR spawn.
9. Publish the activated isolated client generation through the existing Portalkeeper protected-FrameXML flow.
   Do not copy loose FrameXML, install a standalone addon, edit the cumulative TOC manually, or target production.

## Client validation

- [ ] Open through an authorized Transmogrifier at default UI scale and at the smallest supported test scale.
      Capture screenshots. Confirm the window, both slot columns, character, weapon row, catalog, labels, buttons,
      and status line do not overlap or clip.
- [ ] Confirm every equipped slot displays the actual physical item's icon and native item tooltip.
- [ ] Confirm empty usable slots display the stock empty-slot texture, the equip-an-item tooltip, no catalog
      request/result, and disabled Apply/Remove.
- [ ] On at least a relic class and non-relic class, confirm ranged is respectively inactive and active/empty or
      equipped. Test death knight, paladin, druid, and shaman when practical; do not infer from paladin alone.
- [ ] Click each of all fourteen supported icons on applicable classes and confirm the correct slot title, equipped
      item, server catalog, selected preview, and AzerothCore slot mapping.
- [ ] Confirm original slots have no marker, applied appearances have the small ready marker, and hidden appearances
      have the small pass marker immediately after authorized open and after server-confirmed mutations/reopen.
- [ ] Hover applied and hidden equipment icons and confirm the ordinary item tooltip remains intact with only the
      short wardrobe status line appended. Confirm ordinary tooltips outside the wardrobe are unchanged.
- [ ] Confirm Hide is the first tile on permitted slots, remains present with an empty collection, does not consume
      a collected page position, and is absent for main/off/ranged with `NativeTransmog.HideWeapons = 0`.
- [ ] Exercise Previous/Next across enough collected appearances to cross pages; confirm the Hide tile remains
      first and page cursors do not duplicate or skip collected entries.
- [ ] Preview, Apply, Hide, Remove, and Reset Preview for armor and weapons. Confirm only server success changes
      markers or the actual character; Reset/Close never mutate equipment or overrides.
- [ ] Select an appearance, then click other equipment icons. Confirm slot selection itself does not reset or mutate
      the preview unexpectedly and each new tile affects its intended slot.
- [ ] Preview Hide on a character with multiple active overrides. Determine whether build 12340 exposes
      `DressUpModel:UndressSlot`. If fallback is used, record whether other slots temporarily show original models;
      confirm Reset Preview restores server-visible state.
- [ ] Swap, unequip, and equip items while open. Confirm icons refresh, stale requests are rejected, empty state is
      safe, and reopening synchronizes the new item instance's confirmed marker.
- [ ] Rotate by drag, wheel, and both stock rotation buttons; Reset Preview must restore rotation and equipped state.
- [ ] Relog and restart worldserver. Confirm persistence, markers, local/observer rendering, mirror image, enchants,
      weapon gameplay, collection hooks, NPC session closure, and configuration behavior remain Phase 4A-compatible.
- [ ] Inspect FrameXML errors throughout. Record client build, race/class/gender, UI scale, config, screenshots,
      server logs, hashes, and pass/fail for every case. Do not mark visual validation complete without this evidence.

## Rollback

Stop PTR, preserve failure evidence, reactivate the recorded prior Content Manager/client build, restore the prior
reviewed module/config/worldserver, and restart the isolated realm. Phase 4B adds no SQL migration, so ordinary
rollback does not delete or rewrite collection/override data. Database restoration is needed only if unrelated PTR
testing mutated data that must be discarded.
