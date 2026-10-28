# PTR deployment and manual validation

This procedure targets the separate PTR AzerothCore installation and databases. Do not run it against production. Replace angle-bracket placeholders with the established PTR paths/commands; the exact local content-manager command and publication endpoint are environment configuration, not properties of this module.

## Stage the server and package

1. Confirm the PTR core is the intended Playerbot checkout and the production installation is not the active target.
2. Install this repository at `<PTR_CORE>/modules/mod-native-transmog` without changing or disabling `mod-transmog`.
3. From this repository, run:

   ```bash
   python3 content/build_epf.py --check
   python3 -m unittest tests/test_phase1.py
   python3 tests/verify_catalog.py <PTR_CORE>/data/sql/base/db_world/item_template.sql
   ```

4. Configure and build the PTR core using its established build procedure. Confirm `-- MOD NATIVE TRANSMOG CONFIGURED (phase-1-wardrobe-prototype) --` appears during configuration and that the worldserver links successfully.
5. Install the generated configuration as the PTR module configuration with the documented defaults. Do not change production configuration.
6. Start the PTR worldserver. Confirm the initialization log and that no database migration runs (none is supplied).
7. Place `content/mod-native-transmog.epf` in the module/content discovery location used by the PTR `mod-content-manager` installation.
8. Use the existing content-manager validation/build command to create a new cumulative client build. Confirm the package reports `protected-framexml`, both native files are staged, and no collision is reported.
9. Inspect the built MPQ/listing and confirm these paths exist:

   ```text
   Interface/FrameXML/FrameXML.toc
   Interface/FrameXML/NativeTransmogFrame.xml
   Interface/FrameXML/NativeTransmogFrame.lua
   ```

10. Confirm the composed `FrameXML.toc` loads `NativeTransmogFrame.xml` immediately after `DressUpFrame.xml` and that no `Interface/AddOns` path exists.
11. Activate/publish or stage that build only to the PTR channel using the existing content-manager/Portalkeeper process. Record the prior PTR build number so the existing activation/rollback operation can restore it.
12. Confirm the PTR Portalkeeper realm configuration is Schema 1, isolated, and contains `[Client] Requirements=protected-framexml`. Do not modify Portalkeeper or the WoW executable outside its established preparation flow.

## Windows client checklist

Record pass/fail and evidence for every item. Do not mark the phase complete solely from build success.

- [ ] Portalkeeper prepares/selects the expected generation-2 isolated PTR executable and downloads/selects the new cumulative patch.
- [ ] WoW 3.3.5a build 12340 launches normally with no FrameXML error.
- [ ] Login and world entry succeed.
- [ ] `/wardrobe` opens the wardrobe; `/nativetransmog` toggles the same window.
- [ ] The model shows the current player's race, gender, and equipped appearance.
- [ ] Head, shoulders, chest, main hand, and off hand each update the browser.
- [ ] Every catalog entry shows an icon; hovering shows a valid item tooltip.
- [ ] Clicking each entry highlights it and changes only the preview.
- [ ] Compatible selections in several slots remain visible simultaneously.
- [ ] Record exact behavior for mutually exclusive one-hand/two-hand/off-hand combinations; do not infer policy from preview behavior.
- [ ] Dragging the model and both rotation buttons work.
- [ ] Reset returns to the player's equipped appearance and clears highlights.
- [ ] Escape and the close button close the window; reopening starts clean.
- [ ] Actual equipped items, inventory, stats, and combat behavior remain unchanged.
- [ ] No persistent appearance override or existing transmogrification record changes.
- [ ] Existing `mod-transmog` NPC/UI/application behavior still operates.
- [ ] Other native FrameXML content and ordinary client interface features still operate.
- [ ] Logout/restart does not persist prototype selections.

## Failure and rollback

If client load, UI, or coexistence validation fails, stop PTR publication and use the existing content-manager activation/rollback operation to reactivate the recorded prior PTR build. Preserve logs, the cumulative MPQ hash/listing, Portalkeeper preparation output, screenshots, and the exact client error. Do not repair the failure by installing an addon, changing production, editing `mod-transmog`, inventing an opcode, or modifying Portalkeeper's executable transformation.
