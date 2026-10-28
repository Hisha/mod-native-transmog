# Phase 2 PTR deployment and manual validation

This procedure targets the separate PTR AzerothCore installation and databases. Do not run it against production. Record pass/fail and evidence; this repository has not performed or claimed Phase 2 PTR validation.

## Stage server, SQL, and client content

1. Confirm the target core is the intended Playerbot PTR checkout and production is not active.
2. Install this repository at `<PTR_CORE>/modules/mod-native-transmog`. Do not remove, disable, reconfigure, or migrate `mod-transmog`.
3. Run the local checks:

   ```bash
   python3 content/build_epf.py --check
   python3 -m unittest tests/test_phase1.py tests/test_phase2.py
   python3 tests/verify_catalog.py <PTR_CORE>/data/sql/base/db_world/item_template.sql
   ```

4. Back up the PTR world database. Apply the normal AzerothCore module updater, including `data/sql/db-world/updates/2026_10_28_00_native_transmog_npc_service.sql`. Confirm `native_transmog_npc_registration` exists and no `mod-transmog` table or character appearance row changed.
5. Configure/build the PTR core normally. Confirm `-- MOD NATIVE TRANSMOG CONFIGURED (phase-2-npc-services) --`, all three module translation units compile, and worldserver links.
6. Confirm Content Manager Milestone 2 and migration `2026_09_25_06_content_managed_server_resources.sql` are installed. Install `content/mod-native-transmog.epf`, run the cumulative build, and confirm it allocates `dedicated-transmogrifier` as `creature-template.id`, copies donor `28699` model `25615`, and composes the two protected FrameXML files without collision.
7. Activate the build on PTR so its managed server bundle is APPLIED, then publish through the established Portalkeeper process. Record the prior build for rollback. Do not modify Portalkeeper.
8. Restart PTR so AzerothCore loads the applied template. Confirm runtime resolution reports the allocated dedicated entry and registry row counts. Record the entry from `.content allocations` or `.nativetransmog npc list`.

## Required in-game checklist

- [ ] 1. The updated module builds and installs on PTR.
- [ ] 2. Module database migrations apply twice without destructive changes or errors; they create only the registration table and never insert a creature template/model.
- [ ] 3. Content build/activation allocates the symbol, applies the template plus model row, and restart resolves the same retained entry.
- [ ] 4. As a GM, run `.npc add <allocated-entry>`; record its persistent spawn ID.
- [ ] 5. Interact with the dedicated Transmogrifier.
- [ ] 6. The wardrobe opens from the server interaction without typing `/wardrobe`.
- [ ] 7. Character model, rotation, all five slots, icons, tooltips, multi-slot preview, and Reset Preview still work; equipment and inventory do not change.
- [ ] 8. Select an existing interactive NPC and run `.nativetransmog npc add entry`.
- [ ] 9. Every loaded instance of that entry opens the wardrobe while retaining its original behavior.
- [ ] 10. Select a different persistent NPC and run `.nativetransmog npc add spawn`.
- [ ] 11. That spawn opens the wardrobe; another NPC with the same entry does not.
- [ ] 12. Validate at least one vendor and one quest/gossip NPC: vendor inventory, buying/selling, quest markers/dialog, and existing scripted gossip remain available.
- [ ] 13. Run both remove commands and confirm service removal is immediate while original NPC services remain.
- [ ] 14. Re-enable registrations, restart worldserver, and confirm persistence and resolution order with `.nativetransmog npc list/info`.
- [ ] 15. Confirm an ordinary player cannot execute add, remove, list, or info commands.
- [ ] 16. Confirm installed `mod-transmog` NPC/UI/application behavior still works.
- [ ] 17. Compare existing `mod-transmog` tables and appearance records before/after; confirm unchanged.
- [ ] 18. Confirm the client has no standalone native-transmog addon or addon dependency.

## Authorization/session checks

- [ ] `/wardrobe` still opens a local preview but `.nativetransmog npc info`/server logs show that it did not create a service session.
- [ ] Moving beyond interaction range closes an NPC-authorized wardrobe within roughly one second.
- [ ] Entering combat closes it.
- [ ] Despawning the NPC closes it.
- [ ] Changing maps closes it; logout/relogin does not retain authorization.
- [ ] A dynamic creature of an entry-registered template resolves by entry even with spawn ID zero.
- [ ] Spawn registration rejects a temporary creature with a clear error.
- [ ] A creature vehicle passenger does not open the wardrobe in Phase 2; record this as the intentional future-work guard.
- [ ] Normal say/whisper/guild/gossip chat remains unaffected and the protocol payload is not printed as chat.

## Client regression checks

- [ ] Portalkeeper launches the expected isolated build-12340 client and selects the new cumulative patch.
- [ ] No FrameXML error appears during launch, login, reload, or logout.
- [ ] `/wardrobe` and `/nativetransmog` remain functional debug toggles and never change equipped items.
- [ ] Existing native FrameXML modules and ordinary UI panels still function.
- [ ] Record mutually exclusive weapon-preview behavior without treating it as server policy.

## Failure and rollback

On failure, stop PTR publication, preserve worldserver/client logs, SQL updater output, MPQ hash/listing, Portalkeeper output, screenshots, selected entry/spawn IDs, and reproduction steps. Reactivate the recorded prior client build through content-manager rollback and restore the PTR database backup if migration state itself is suspect. Do not repair a failure by installing an addon, changing production, editing `mod-transmog`, inventing an opcode, changing existing NPC flags/scripts, or modifying Portalkeeper's executable transformation.
