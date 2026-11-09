# Historical Phase 2 PTR deployment and manual validation

For the current Phase 4A server/client deployment and full-slot Hide Appearance checklist, use
[`PHASE4A_PTR_VALIDATION.md`](PHASE4A_PTR_VALIDATION.md). This document remains the historical Phase 2
service baseline.

This procedure targets the separate PTR AzerothCore installation and databases. Do not run it against production. Record pass/fail and evidence; this repository has not performed or claimed Phase 2 PTR validation.

## Stage server, SQL, and client content

1. Confirm the target core is the intended Playerbot PTR checkout and production is not active.
2. Install this repository at `<PTR_CORE>/modules/mod-native-transmog`. Remove or exclude the legacy `mod-transmog` source from the PTR build if present; do not delete its database records.
3. Run the local checks:

   ```bash
   python3 content/build_epf.py --check
   python3 -m unittest tests/test_phase1.py tests/test_phase2.py
   python3 tests/verify_catalog.py <PTR_CORE>/data/sql/base/db_world/item_template.sql
   ```

4. Back up the PTR world database. Apply the normal AzerothCore module updater, including `data/sql/db-world/updates/2026_11_09_00_native_warpweavers.sql`. Confirm entry `14999992` and nine spawns exist and no `mod-transmog` table, entry `190010`, or legacy appearance row changed.
5. Configure/build the PTR core normally. Confirm `-- MOD NATIVE TRANSMOG CONFIGURED (phase-2-npc-services) --`, all three module translation units compile, and worldserver links.
6. Install `content/mod-native-transmog.epf`, run the cumulative Content Manager build, and confirm it composes the protected FrameXML without declaring a server-side creature resource.
7. Activate and publish the client build through the established Portalkeeper process. Record the prior build for rollback. Do not modify Portalkeeper.
8. Restart PTR so AzerothCore loads entry `14999992`. Confirm `.nativetransmog npc list` reports the native dedicated entry and the nine database spawns load.

## Required in-game checklist

- [ ] 1. The updated module builds and installs on PTR.
- [ ] 2. Migration replay leaves exactly one template/model and nine defaults, with unchanged recorded GUIDs.
- [ ] 3. Entry `14999992` is Warpweaver/Transmogrifier with model `19646`, scale/probability `1`, and all defaults respawn in 300 seconds.
- [ ] 4. Restart worldserver and confirm no additional creature rows appear.
- [ ] 5. Interact with each dedicated Warpweaver.
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
- [ ] 16. Confirm legacy `mod-transmog` is absent from the compiled/loaded PTR module set.
- [ ] 17. Compare retained legacy tables, template/model `190010`, and appearance records before/after; confirm unchanged.
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
