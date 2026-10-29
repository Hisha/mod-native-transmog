# Phase 3B quest reward collection architecture

Phase 3B extends the Phase 3A collection service. It does not add a second ownership store, grant reward items, apply appearances, filter the client wardrobe, or change `mod-transmog`.

## Live completion path

The inspected Playerbot revision is `8a4e76eac8c4ccebf547113afe7b51d6c3e91641`. In that branch, `Player::RewardQuest` delivers the selected choice and every guaranteed item, marks the quest rewarded, calls `SaveToDB`, updates the player, and only then invokes `ScriptMgr::OnPlayerCompleteQuest`. `NativeTransmogPlayerScript::OnPlayerCompleteQuest` uses that post-reward hook. Quest acceptance, objective completion, reward preview, failed turn-in, and abandonment do not invoke this module path.

WotLK's loaded `Quest` has exactly these item reward arrays:

- `RewardChoiceItemId[QUEST_REWARD_CHOICES_COUNT]`, where the count is 6;
- `RewardItemId[QUEST_REWARDS_COUNT]`, where the count is 4.

Phase 3B enumerates every nonzero entry in both arrays. It never calls an item grant API. Missing templates are unresolved; present templates pass through `CollectionService::ResolveAppearance`, retaining Phase 3A's visible armor/weapon rules and composite identity. Class, race, proficiency, skill, and equip requirements are never consulted.

The collection service selects policy by durable acquisition source: ordinary acquisitions honor `UnlockOnAcquire`, live quest enumeration honors `UnlockAllQuestRewards`, and historical enumeration honors `QuestBackfill.Enable`. All three still require global collection enablement and database availability. Ownership selection, deduplication, synchronous first insert, and the owner cache remain shared.

## Provenance and migration

Acquisition categories 4 and 5 mean live all-offered-reward enumeration and historical quest backfill. The additive `source_quest` column stores the current quest entry; ordinary Phase 3A rows retain zero. The existing primary key is unchanged, so `INSERT IGNORE` preserves the first item, character, timestamp, acquisition category, and quest provenance when another path encounters an owned appearance. On a normal completion, Phase 3A's `StoreNewItem` hook runs while the core delivers the selected/guaranteed physical items, before the post-reward Phase 3B hook. If that path creates the first ownership row, its ordinary item-storage provenance correctly remains first; category 4 is used for newly unlocked offered appearances that were not already collected by physical receipt.

The base schema includes the new column for new installations. `2026_10_29_00_native_transmog_quest_provenance.sql` conditionally adds the column and index for existing databases and is safe to rerun. No old row is rewritten or removed.

## Historical evidence and limitations

Backfill reads only `(guid, quest)` rows with `active = 1` from `character_queststatus_rewarded`. These rows are persisted reward evidence. Rows in `character_queststatus` can represent accepted, incomplete, failed, or objective-complete-but-unrewarded quests and are deliberately ignored. Achievements are not evidence.

The rewarded table proves at least one recorded completion, not the selected reward, the number of repeat completions, or the reward definition at that historical time. Daily/weekly/monthly/seasonal reset tables and old quest definitions are not reconstructed. The current authoritative in-memory quest and item templates are used. Missing/inactive history and deleted quest/item templates are reported rather than inferred.

## Controlled batching

Only an in-game RBAC-authorized GM can start a job, for the selected online player or the GM's own character. There is no offline, account-wide, realm-wide, startup, login, or scheduled scan. Selecting one character in account-wide mode contributes that character's evidence to the shared owner; it does not mark sibling characters processed.

Jobs advance from that target player's update hook. Each history query uses the `(guid, quest)` primary key and a monotonic quest cursor with `ORDER BY quest LIMIT 25`, no offset and no per-quest database lookup. New ownership from a run batch is deduplicated and written with one multi-row `INSERT IGNORE`, rather than one query per appearance. A 100 ms gate limits work to one batch per target update interval. Disconnecting pauses practical progress until that character is online again. Completed status remains available until a new job replaces it or configuration reload clears jobs.

Preview and run use the same enumeration and job-wide appearance set. Preview calls only collection reads and reports `would unlock`; run calls `CollectionService::Unlock` and reports `newly unlocked`. Both are repeatable and bounded. Duplicate item IDs, shared appearance identities, normal acquisition races, repeatable quests, and reruns converge on the collection primary key.

## Commands and security

```text
.nativetransmog collection backfill preview
.nativetransmog collection backfill run
.nativetransmog collection backfill status
```

Preview/status use the existing NPC-info RBAC permission. Run uses the stronger NPC-add RBAC permission. Commands reject a missing online target, never accept owner/account IDs, and do not expose a global mode. Status includes target GUID/name, the captured owner scope, quests examined, unique eligible appearances, already-owned/new counts, unresolved definitions, ineligible items, and cursor.

## Phase boundary

Phase 3B records ownership only. Appearance application, compatibility enforcement at application time, client collection filtering, saved outfits, and wardrobe redesign remain later work.
