# Phase 3D PTR validation

This is a manual procedure for the isolated Playerbot PTR. It does not authorize deployment and no
step applies to production. Record command output, hashes, screenshots, client Lua errors, worldserver
logs, and pass/fail beside every check.

## Prepare and publish the client patch

These steps require the Phase 3D protected-FrameXML client patch.

1. Record the active Content Manager build from `.content build list`, the published MPQ SHA-256, the
   Portalkeeper realm configuration, and a restorable copy of the prior module/EPF.
2. In the module checkout run:

   ```bash
   python3 content/build_epf.py
   python3 content/build_epf.py --check
   sha256sum content/mod-native-transmog.epf
   ```

   Run the build/check pair a second time and confirm the SHA-256 is identical.
3. Put `content/mod-native-transmog.epf` in the EPF discovery location already configured by
   `mod-content-manager`. Do not extract it, edit a generated MPQ, create `Interface/AddOns`, or change
   Portalkeeper.
4. In the PTR worldserver console or as an authorized Content Manager GM run:

   ```text
   .content scan
   .content install mod-native-transmog
   .content build
   .content build list
   ```

   If the package was already installed, `.content install` may report that state; do not uninstall it.
   Record the new STAGED build number, package/file counts, protected-framexml requirement, and hash.
5. Activate exactly that build:

   ```text
   .content activate <new-build-number>
   .content build list
   .content allocations
   ```

   Activation must apply/verify the managed Transmogrifier template before publishing the client
   artifact and leave the build ACTIVE/APPLIED. Record the retained `dedicated-transmogrifier`
   `creature-template.id`.
6. Use the existing Portalkeeper realm refresh/distribution operation. Confirm the realm points to the
   new active build and its exact MPQ hash, launch the isolated build-12340 client through Portalkeeper,
   and verify the selected runtime contains the updated cumulative patch and protected FrameXML
   requirement. Do not use a manually patched client.

## Update and rebuild the PTR server

These steps are server-side; only the later UI checks require the client patch.

1. Stop the PTR worldserver. Back up the PTR world and character databases, module checkout/config,
   worldserver binary, and generated module list. Confirm `mod-transmog` is absent from this PTR build.
2. Update only `<PTR_CORE>/modules/mod-native-transmog` to the reviewed Phase 3D tree. Do not commit,
   merge unrelated changes, or update production.
3. Run AzerothCore's normal database updater. Phase 3D adds no migration; confirm the existing module
   migrations are applied and these tables/columns remain available:

   - world: `native_transmog_npc_registration`;
   - characters: `native_transmog_collection.source_quest`;
   - characters: `native_transmog_item_override.appearance_item`.

   Re-run the updater to demonstrate idempotency.
4. Install `conf/mod_native_transmog.conf.dist` through the normal module configuration flow. Confirm
   `AddonChannel = 1` in worldserver configuration and record the collection scope, handedness settings,
   page size, request cooldown, and snapshot lifetime.
5. Configure and build the actual Playerbot branch with the PTR's normal toolchain. Confirm CMake prints
   `phase-3d-native-wardrobe-integration`, all six module translation units compile, `worldserver` links,
   and the generated loader contains `Addmod_native_transmogScripts` but no `Addmod_transmogScripts`.
6. Start PTR. Confirm Content Manager resolves the active/applied dedicated resource, the collection and
   application schemas initialize, and no Lua/protocol/database error is logged. Spawn the retained entry
   with `.npc add <allocated-entry>` only if the PTR does not already have a dedicated spawn.

## Server-only validation

These checks can be run without the Phase 3D client patch; they do not validate the wardrobe UI.

- [ ] Existing `.nativetransmog collection info/count/list` commands reflect account-wide mode, then
  character mode after a controlled config change/restart. Switching scope neither copies nor deletes rows.
- [ ] Existing GM `appearance apply/remove/info` diagnostics still enforce RBAC, collection ownership,
  compatibility, persistence, and removal.
- [ ] Uncollected, class/race restricted, proficiency restricted, armor mismatch, weapon-family mismatch,
  handedness-disabled, and empty-slot applications fail without changing item data or an existing override.
- [ ] Relog and a full worldserver restart restore an applied override; another player sees the visible
  change; unequip/re-equip preserves it. Record weapon and ownership-transfer cases as unproven unless
  explicitly exercised.
- [ ] `/wardrobe` and `/nativetransmog` create no Phase 2 server session and grant no application authority.

## Equipment-triggered collection validation

Before opening the wardrobe, verify equipment-triggered collection independently:

1. Record the current rows for the test account/character and choose an eligible, uncollected plate shoulder
   item (Judgement Spaulders, item `16954`, is the reported regression case). Equip it successfully and confirm
   exactly one composite appearance row is created under the configured account or character owner. Unequip and
   re-equip it twice and confirm the row count and original provenance remain unchanged.
2. Repeat with collection disabled and confirm no row is created. Attempt an invalid equip and confirm no row is
   created. Equip an ineligible item category and confirm it remains excluded. Restore the reviewed configuration
   before continuing.
3. Confirm ordinary loot, inventory transfer, vendor, quest-completion, and quest-backfill collection still follow
   their existing settings and remain idempotent.

## Patched-client wardrobe validation

1. Log in through the Portalkeeper-prepared build-12340 client as a normal player with known collected
   appearances and equip test items in head, shoulder, chest, main-hand, and off-hand slots.
2. Interact with the dedicated Transmogrifier. Confirm the native wardrobe opens automatically. There
   must be no standalone addon and no visible protocol text.
3. For every supported slot, confirm only collected, server-compatible appearances are shown. Verify an
   empty collection and empty equipment slot show meaningful empty/error states. Page through a collection
   larger than the configured page size and verify deterministic Next/Previous behavior.
   As a focused regression, use Hipally's collected plate helmet identity `(51904, 4, 4, 1)` from item `44695`:
   with a compatible plate helmet equipped, select Head and confirm item `44695` appears without a Lua error.
   Confirm an uncollected helmet and incompatible armor remain absent, and that an already-applied `44695`
   remains present with its applied marker. Capture the multipart `PAGE`/`ITEM`/`END` exchange if the catalog
   is unexpectedly empty so server response and client rendering failures can be distinguished.
4. Hover entries and confirm icon, localized item name, and tooltip resolve. Confirm the equipped item,
   applied appearance, preview selection, selected highlight, and applied check mark are distinct.
5. Select an appearance. Confirm only the DressUpModel changes; inventory, equipment, nearby observers,
   and `native_transmog_item_override` do not. Click Reset Preview and confirm the currently applied state
   returns without removing its row.
6. Select again and click Apply Appearance. Confirm no success is displayed before the server response;
   then confirm the success message, durable row, local visible update, nearby observer update, and refreshed
   applied marker. Repeat with an existing override to validate replacement.
7. Click Remove Appearance. Confirm server acknowledgment precedes success, the durable row is deleted,
   the real equipped appearance returns locally and to the observer, and the applied marker clears.
8. Preview a different appearance and click Close. Reopen through the NPC and confirm the preview was not
   applied. Repeat with Reset Preview.
9. While a page is open, change the selected slot's equipment and immediately click Apply. Confirm the stale
   snapshot is rejected with `Equipment changed; refreshing the wardrobe`, nothing is applied to either item,
   and the page refreshes for the new target.
10. Test session closure by moving out of range, entering combat, dying, changing maps, despawning the NPC,
    disabling its registration, waiting past the five-minute session lifetime, and disconnecting. Each case
    must prevent mutations and produce close/expired feedback where delivery remains possible.
11. Open `/wardrobe` directly. Confirm Preview-only mode, disabled Apply/Remove, and no catalog request.
12. Exercise malformed, oversized, rapid, replayed, and stale requests with the controlled test harness—not
    ordinary player chat. Confirm rejection/rate limiting and no state change.
13. Relog, restart worldserver, and reopen the wardrobe. Confirm applied state, catalog ownership scope, and
    observer visibility remain correct.

## Rollback

1. Stop PTR and preserve failure evidence.
2. Restore the previous reviewed module checkout/config and rebuild/reinstall the previous worldserver.
3. Reactivate the recorded prior Content Manager build:

   ```text
   .content activate <prior-build-number>
   .content build list
   ```

4. Refresh the existing Portalkeeper realm metadata and confirm it distributes/selects the prior MPQ hash.
5. Restart PTR and confirm prior NPC/UI behavior. Phase 3D has no new schema, so normally leave the
   namespaced collection/override data intact. Restore database backups only for demonstrated data damage.
6. Never roll back by enabling `mod-transmog`, installing an addon, editing a generated MPQ, changing
   Portalkeeper generation-2 transformation, or running both appearance writers together.

Manual checks remain **not run** until evidence is captured on PTR.
