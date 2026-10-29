# Phase 3B PTR validation

PTR validation is a separate deployment step. None of these steps were run by implementation automation. Replace `<character_guid>`, `<account_id>`, `<quest_id>`, and database names with PTR values.

## Deploy and preflight

1. Back up the character database and the current module binary/config.
2. Build/install the module through the normal Playerbot module process. Apply the character update `2026_10_29_00_native_transmog_quest_provenance.sql` through the AzerothCore updater.
3. Add or retain:

   ```ini
   NativeTransmog.Collection.Enable = 1
   NativeTransmog.Collection.AccountWide = 1
   NativeTransmog.Collection.UnlockOnAcquire = 1
   NativeTransmog.Collection.UnlockAllQuestRewards = 1
   NativeTransmog.Collection.QuestBackfill.Enable = 1
   ```

4. Restart worldserver. Confirm startup reports Phase 3B collection enabled and no missing-table/column error.
5. Verify the additive schema in the character database:

   ```sql
   SHOW COLUMNS FROM native_transmog_collection LIKE 'source_quest';
   SHOW INDEX FROM native_transmog_collection WHERE Key_name = 'idx_native_transmog_source_quest';
   SELECT acquisition_source, COUNT(*)
   FROM native_transmog_collection
   GROUP BY acquisition_source ORDER BY acquisition_source;
   ```

## Find suitable quests without guessing IDs

Run this against the checked-out branch's world database. It uses the actual `quest_template` columns and finds quests with at least two collectible-category selectable rewards. SQL can check item class, slot, and nonzero display ID; the server's DBC lookup remains authoritative.

```sql
SELECT q.ID, q.LogTitle, COUNT(*) AS eligible_choice_items,
       GROUP_CONCAT(CONCAT(r.item_id, ':', i.name) ORDER BY r.slot SEPARATOR ' | ') AS rewards
FROM quest_template q
JOIN (
  SELECT ID, 1 slot, RewardChoiceItemID1 item_id FROM quest_template UNION ALL
  SELECT ID, 2, RewardChoiceItemID2 FROM quest_template UNION ALL
  SELECT ID, 3, RewardChoiceItemID3 FROM quest_template UNION ALL
  SELECT ID, 4, RewardChoiceItemID4 FROM quest_template UNION ALL
  SELECT ID, 5, RewardChoiceItemID5 FROM quest_template UNION ALL
  SELECT ID, 6, RewardChoiceItemID6 FROM quest_template
) r ON r.ID = q.ID AND r.item_id <> 0
JOIN item_template i ON i.entry = r.item_id
WHERE i.class IN (2, 4) AND i.displayid <> 0
  AND i.InventoryType IN (1,3,4,5,6,7,8,9,10,13,14,15,16,17,19,20,21,22,23,25,26)
GROUP BY q.ID, q.LogTitle
HAVING COUNT(*) >= 2
ORDER BY COUNT(*) DESC, q.ID
LIMIT 50;
```

Find guaranteed-only or mixed quests with this query:

```sql
SELECT q.ID, q.LogTitle,
       (q.RewardChoiceItemID1<>0)+(q.RewardChoiceItemID2<>0)+(q.RewardChoiceItemID3<>0)+
       (q.RewardChoiceItemID4<>0)+(q.RewardChoiceItemID5<>0)+(q.RewardChoiceItemID6<>0) AS choices,
       (q.RewardItem1<>0)+(q.RewardItem2<>0)+(q.RewardItem3<>0)+(q.RewardItem4<>0) AS guaranteed
FROM quest_template q
WHERE q.RewardItem1<>0 OR q.RewardItem2<>0 OR q.RewardItem3<>0 OR q.RewardItem4<>0
ORDER BY choices=0 DESC, guaranteed DESC, q.ID
LIMIT 100;
```

Before testing, inspect one candidate's exact current definition:

```sql
SELECT ID, LogTitle,
 RewardChoiceItemID1, RewardChoiceItemID2, RewardChoiceItemID3,
 RewardChoiceItemID4, RewardChoiceItemID5, RewardChoiceItemID6,
 RewardItem1, RewardItem2, RewardItem3, RewardItem4
FROM quest_template WHERE ID = <quest_id>;
```

## Baseline queries

Determine scope and baseline count. Account IDs come from the authenticated character row, not client input.

```sql
SELECT guid, account, name FROM characters WHERE guid = <character_guid>;
SELECT COUNT(*) FROM native_transmog_collection
WHERE owner_type = 1 AND owner_id = <account_id>;
SELECT display_id, item_class, item_subclass, inventory_type,
       source_item, source_quest, acquiring_character, acquired_at, acquisition_source
FROM native_transmog_collection
WHERE owner_type = 1 AND owner_id = <account_id>
ORDER BY acquired_at DESC, display_id DESC LIMIT 50;
```

For character-specific testing use `owner_type = 2 AND owner_id = <character_guid>`.

## Test A — all selectable rewards

1. Use a candidate from the first finder query with multiple eligible appearances.
2. Record `.nativetransmog collection count` and the baseline SQL count.
3. Complete the quest and select exactly one item.
4. Verify inventory contains only the selected reward. Verify all unique eligible choice appearances have rows with `acquisition_source = 4` and `source_quest = <quest_id>`, except appearances already owned (whose original provenance must remain unchanged).
5. Run `.nativetransmog collection list` and the baseline SQL again.

Expected: the count rises by the number of previously unowned unique composite appearances, not by the number of item entries.

## Test B — cross-class rewards

Complete a candidate whose reward items include armor/weapon types unusable by the completing class. Query the quest's items and collection rows. Expected: all eligible identities are collected; only the selected item is granted; equip restrictions do not affect collection.

## Test C — guaranteed rewards

Complete a guaranteed-only or mixed candidate. Expected: every eligible `RewardItem1` through `RewardItem4` appearance is collected in addition to every choice appearance.

## Test D — duplicate protection

Use a repeatable eligible quest if available, or first acquire an offered appearance normally and then complete the quest. Record count before/after two successful completions.

```sql
SELECT owner_type, owner_id, display_id, item_class, item_subclass, inventory_type, COUNT(*)
FROM native_transmog_collection
GROUP BY owner_type, owner_id, display_id, item_class, item_subclass, inventory_type
HAVING COUNT(*) > 1;
```

Expected: no rows; second completion adds zero for already-owned identities and preserves first provenance.

## Test E — historical backfill

Choose an online character with reliable active reward rows:

```sql
SELECT COUNT(*) AS reliable_rewarded_rows
FROM character_queststatus_rewarded
WHERE guid = <character_guid> AND active = 1;
```

Select that character in game (or use the GM character itself), then run:

```text
.nativetransmog collection backfill preview
.nativetransmog collection backfill status
```

Poll status until `preview complete`. Record quests, eligible, already collected, would unlock, unresolved, and ineligible. Confirm the SQL collection count did not change. Then run:

```text
.nativetransmog collection backfill run
.nativetransmog collection backfill status
```

Poll until `run complete`. Expected: SQL count rises by `newly unlocked`; new rows use category 5 and the source quest. Run preview and run again. Expected: `would unlock`/`newly unlocked` is zero and count is unchanged.

Do not treat `character_queststatus.status = 1` as historical reward evidence: it can mean objective-complete but not rewarded. Missing old/repeat completion history cannot be reconstructed. Current world quest definitions are used even if they changed historically.

## Test F — account-wide sharing

With `AccountWide = 1`, log into a different character on the same account and run count/list. Expected: the quest/backfill appearances are visible under the same account owner. The status remains specific to the character that was processed; no sibling was implicitly scanned.

## Test G — existing functionality

1. Loot, craft, trade/mail, or buy an eligible new item. Expected: normal Phase 3A category 1/2/3 collection still works.
2. Interact with the dedicated Transmogrifier. Expected: server authorization opens the wardrobe.
3. Verify `.nativetransmog npc list/info`, registered existing NPC behavior, and wardrobe preview.
4. Exercise the separately installed `mod-transmog` flow and compare its tables before/after. Expected: unchanged by this module.

## Permission, failure, and zero-history checks

- Try all backfill commands without the required RBAC permissions. Expected: command denied.
- Run with no selected player. Expected: the GM's own online character is the explicit target.
- Select a creature or disconnect the intended character. Expected: no unrelated/global target; offline named backfill is unsupported.
- Use a character with zero active rewarded rows. Expected: completed status with zero quests and zero changes.
- Disable global collection. Expected: no live or backfill unlocks.
- Disable only quest reward collection. Expected: normal item acquisition remains; live all-choice enumeration stops.
- Disable only backfill. Expected: commands cannot start jobs; live quest collection remains.

## Rollback

1. Stop worldserver.
2. Restore the previous module binary and config, or set both Phase 3B settings to `0`.
3. Leave `source_quest` and its index in place. They are additive, old rows retain zero, and leaving them is the safest rollback because no ownership is lost. Category 4/5 rows are valid collected ownership and should normally remain.
4. If policy requires removing Phase 3B-granted ownership, restore the pre-deployment character-database backup. Do not delete rows merely by acquisition category without explicit approval; doing so can remove the only ownership record for an appearance.
5. Restart and verify Phase 1–3A and `mod-transmog` behavior.

No EPF, Content Manager, Portalkeeper, client opcode, or standalone addon change is part of this deployment.
