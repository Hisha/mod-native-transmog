# Phase 3A PTR validation

PTR validation is a separate deployment step. Do not run these steps against production first.

## Deploy and inspect

1. Back up the character database.
2. Deploy the module and apply `data/sql/db-characters/updates/2026_10_28_00_native_transmog_collection.sql` through the normal AzerothCore updater.
3. Install the updated `.conf.dist` values in the realm config, rebuild worldserver, and restart PTR. The EPF/client package is unchanged in Phase 3A.
4. Confirm startup reports Phase 2 NPC initialization and Phase 3A collection initialization without a missing-table error.

Read-only GM diagnostics (all operate on the logged-in GM's authenticated account/character collection):

```text
.nativetransmog collection info
.nativetransmog collection count
.nativetransmog collection list
```

`list` is bounded to the first 50 rows in deterministic order.

Exact character-database SQL diagnostics:

```sql
SELECT owner_type, owner_id, COUNT(*) AS appearances
FROM native_transmog_collection
GROUP BY owner_type, owner_id
ORDER BY owner_type, owner_id;

SELECT owner_type, owner_id, display_id, item_class, item_subclass,
       inventory_type, source_item, acquiring_character, acquired_at,
       acquisition_source
FROM native_transmog_collection
WHERE owner_type = 1 AND owner_id = <ACCOUNT_ID>
ORDER BY item_class, inventory_type, item_subclass, display_id;

SELECT owner_type, owner_id, display_id, item_class, item_subclass,
       inventory_type, source_item, acquiring_character, acquired_at,
       acquisition_source
FROM native_transmog_collection
WHERE owner_type = 2 AND owner_id = <CHARACTER_GUID>
ORDER BY item_class, inventory_type, item_subclass, display_id;
```

Use server-side account/character values from authenticated GM tooling or the `characters` table; no client-supplied owner value participates in collection logic.

## Required tests

### Test 1 — Account-wide collection

With `AccountWide=1`, acquire an eligible visible armor/weapon item on character A. Run `collection info/count/list`. Log into character B on the same account and confirm the same appearance and original acquiring-character provenance are present.

### Test 2 — Cross-class collection

Acquire a plate appearance on a cloth-wearing character. Confirm it is collected. Confirm Phase 3A offers no equip/transmog permission and existing game/mod-transmog restrictions are unchanged.

### Test 3 — Duplicate handling

Acquire two item entries whose `item_template` rows have the same `displayid`, `class`, `subclass`, and `InventoryType`. Confirm count increases once and the first source item/provenance remain unchanged. Also test the same display ID in a different subclass or inventory type and confirm it remains a separate safe category.

### Test 4 — Persistence

Record `collection count`, restart worldserver, relog, and confirm count/list and SQL rows are unchanged.

### Test 5 — Character-specific mode

Set `AccountWide=0`, restart PTR, and acquire distinct items on characters A and B. Confirm isolation. Restore `AccountWide=1`, restart, and confirm the original account rows return unchanged. Switch back once more if desired to confirm character rows were retained. No records should be merged or deleted.

### Test 6 — Existing module regression

- Interact with the dedicated Transmogrifier and confirm the wardrobe opens.
- Confirm entry/spawn NPC registrations and GM NPC diagnostics still work.
- Confirm model preview, rotation, slot selection, simultaneous previews, and reset.
- Confirm the separately installed `mod-transmog` still applies its own transmogs and its tables are unchanged.

## Additional acquisition coverage

Test creature loot, dungeon/raid loot, an actually chosen quest reward, vendor purchase into bags, vendor direct equip, crafted item, mail attachment retrieval, and trade receipt. For each eligible item, confirm exactly one row. Test a consumable, ring, quest object, and item with invalid/zero display data and confirm no row.

## Rollback

Disable `NativeTransmog.Collection.Enable`, restore the prior module binary/config, and restart. Leave `native_transmog_collection` in place: it is module-owned, inert while disabled, and preserves ownership for re-enablement. If organizational policy requires physical removal, archive the table and drop it only as an explicit manual destructive operation; rollback does not require that step. No equipment, `mod-transmog` row, world content, or EPF change needs reversal.
