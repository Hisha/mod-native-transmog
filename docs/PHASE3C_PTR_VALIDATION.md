# Phase 3C PTR validation

This is a manual plan for the isolated Playerbot PTR. It does not authorize deployment. Production remains unchanged.

## Isolation and staging

1. Record the PTR core/module commits, current binary/config hashes, database row counts, and rollback artifact.
2. Confirm `mod-transmog` is excluded from the PTR build/load. Its loader symbol/shared library must be absent; disabling only its configuration is not sufficient. Do not alter or migrate its retained database tables.
3. Confirm `mod-native-transmog` is the only module containing a post-visible-item-slot writer or writing `native_transmog_item_override`.
4. Back up the PTR character database. Run the normal module SQL updater and confirm `native_transmog_item_override` is the only Phase 3C table created. Re-run the update to verify idempotency.
5. Build and link the actual Playerbot worldserver. Confirm the generated module list contains `mod-native-transmog` and no `mod-transmog`.
6. Preserve the existing mod-content-manager EPF pipeline and protected FrameXML package. Phase 3C needs no EPF rebuild beyond deterministic verification and no Portalkeeper change.

## Authorization and compatibility

- [ ] An ordinary player has no application command and no client application button.
- [ ] A direct/local wardrobe preview does not authorize application.
- [ ] NPC authority closes on range, combat, death, map change, despawn, registration removal, and logout.
- [ ] The apply service rejects missing/expired authority when exercised through a controlled server harness.
- [ ] GM apply/remove/info enforce RBAC and selected-player security.
- [ ] An uncollected source, missing template, ineligible category, and empty/invalid equipment slot are rejected without a database row or visible change.
- [ ] Account-wide and character-specific collection modes each use their current authenticated namespace.
- [ ] Class-restricted armor/weapon sources are rejected.
- [ ] Race-restricted and required-skill/rank/spell sources are rejected when requirements are not met.
- [ ] Cloth, leather, mail, plate, and shield proficiency restrictions are correct for representative classes.
- [ ] Armor subclass and inventory-slot mismatches are rejected; chest/robe interchange works.
- [ ] A one-handed sword target accepts collected one-handed axe and mace appearances.
- [ ] A two-handed sword target accepts collected two-handed axe, mace, and polearm appearances.
- [ ] Main-hand/off-hand, ranged, thrown, wand, and fishing-pole cases retain their existing policy.
- [ ] Both handedness-crossing directions fail regardless of the two retained legacy configuration values.

## Persistence, lifecycle, and synchronization

- [ ] Apply a collected appearance and confirm the real item entry/stats/damage/speed/enchantments/durability remain unchanged.
- [ ] Confirm the owner and a nearby observer see the override without relogging.
- [ ] Relog and restart worldserver; confirm the override restores from the same item GUID.
- [ ] Equip/unequip and swap compatible equipment; confirm an override follows its item instance and normal slot refreshes do not erase it.
- [ ] Move an overridden item to bags and back without transferring ownership; confirm expected persistence.
- [ ] Transfer through trade, mail, auction, and guild-bank paths; confirm the override is removed before the recipient can use the item.
- [ ] Delete/vendor/destroy an overridden item; confirm transactional cleanup leaves no orphan row.
- [ ] Create a mirror image and confirm the override display is used.
- [ ] Remove via the diagnostic command and confirm immediate owner/observer restoration of the real appearance and durable row deletion.
- [ ] Change compatibility configuration so a stored pairing becomes invalid, relog, and confirm safe rejection/removal.
- [ ] Exercise representative Playerbots through login, equipment changes, transfers, and logout; record errors and database load.

## Sole-writer evidence

Capture generated loader/module configuration, symbol search, startup logs, and database general/audit log (or an equivalent controlled trace) showing:

- no `Addmod_transmogScripts` registration or `mod_transmog` shared object;
- only `NativeTransmogPlayerScript` writes `PLAYER_VISIBLE_ITEM_1_ENTRYID` after the core's normal writer;
- only `mod-native-transmog` writes `native_transmog_item_override`;
- legacy `custom_transmogrification`, `custom_transmogrification_sets`, and `custom_unlocked_appearances` row counts/checksums do not change.

## Rollback

Stop PTR, restore the prior complete PTR server artifact/config, and restore the prior content-manager activation only if it was changed during separately authorized staging. Do not enable old and native appearance writers together during transition. Restore the database backup only for a demonstrated migration/data failure; normal rollback may leave the namespaced Phase 3C table intact. Do not change production.
