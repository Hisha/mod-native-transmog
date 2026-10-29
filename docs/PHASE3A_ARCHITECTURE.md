# Phase 3A collection architecture

Phase 3A records ownership only. It neither changes equipment nor decides whether an appearance may be applied. Collection deliberately ignores class, race, armor proficiency, weapon proficiency, and required skill. Phase 3C must independently validate every application request.

## Storage and ownership

`native_transmog_collection` is in the character database, matching AzerothCore's convention for character/account gameplay state. It uses no separate database and does not reference or alter `mod-transmog`.

`owner_type=1` means the authenticated WoW account and `owner_type=2` means the character GUID. `owner_id` is always derived from `Player::GetSession()->GetAccountId()` or the server-side player GUID. The composite primary key makes unlocks idempotent. The first source item, acquiring character, timestamp, and acquisition-source category are retained. There are deliberately no foreign keys to `characters` or world `item_template`: deleting a character or retiring a source item cannot delete collection history. A missing source template is reported diagnostically and does not invalidate ownership.

Changing `NativeTransmog.Collection.AccountWide` changes which owner namespace new unlocks and queries use. It does not copy, merge, promote, or delete rows. Thus account → character → account restores the earlier account collection exactly, while character rows remain dormant until character mode is selected again.

Account-wide means one account inside the configured character database. Realms with independent character databases have independent collections even if their auth databases share account IDs. Realms sharing one character database share account rows; deployments must ensure account-ID meaning is also shared.

## Appearance identity and eligibility

The durable key is:

```text
(ItemDisplayInfo ID, item class, item subclass, inventory type)
```

WotLK item entries are sources, not appearance identities. `DisplayInfoID` supplies client display data, while class/subclass/inventory type retain the category and slot semantics needed for later safe application. Two items with the complete same key deduplicate. A shared display ID in different armor subclasses, weapon subclasses, or inventory types remains distinct because those categories may not be mutually applicable. This is deliberately conservative and avoids unsupported assumptions about client rendering.

Eligible records require a resolvable world `ItemTemplate`, a nonzero `DisplayInfoID` present in AzerothCore's loaded `ItemDisplayInfo.dbc`, item class armor or weapon, and a visible/equippable inventory type. Shirts (`BODY`), tabards, cloaks, robes, shields, held-in-offhand items, ranged weapons, thrown weapons, and fishing poles are included when their class/display data qualify. Necklaces, rings, trinkets, bags, ammo, quivers, and relics are excluded because build 12340 does not expose an ordinary wearable model appearance for this wardrobe model. Consumables, currency, quest/miscellaneous objects, and every non-equippable item are excluded. Eligibility never calls player equipment checks.

## Acquisition and query paths

The Playerbot branch's `OnPlayerStoreNewItem` hook is the central path for newly created/stored items, covering ordinary loot storage, received quest rewards, crafted items, and most purchases. `OnPlayerAfterMoveItemToInventory` covers existing-item transfers such as trades and mail attachment retrieval. A focused post-vendor hook covers purchases equipped directly without `StoreNewItem`. The first two persisted source values describe the authoritative core operation (`new-item` or `inventory-transfer`), since the centralized hook does not reliably carry the higher-level loot/craft/quest/trade/mail cause.

No startup or login scan occurs. Existing equipped, bag, bank, or quest history is untouched. A future controlled backfill can enumerate an explicitly selected source and call `CollectionService::Unlock`; that is the service boundary, but no backfill command is exposed in Phase 3A.

`CollectionService` owns identity resolution, unlocks, ownership checks, deterministic listing, provenance lookup, source resolution, counts, and item-class/inventory-type filters. Future client communication must call it with the current authenticated `Player`; it must not query the table or accept owner IDs from a packet.

## Performance and ordering

The primary key and owner/category index support ownership, count, and filtered listing. The first acquisition per active owner loads its appearance keys once; repeated acquisitions are in-memory set lookups and cause no database write. New ownership uses synchronous `INSERT IGNORE` before updating memory, so an immediate logout cannot strand an asynchronous insert and concurrent duplicate inserts remain idempotent. Lists are bounded to 200 at the API and 50 in GM output, ordered by class, inventory type, subclass, then display ID.

Playerbots use the same ordinary hooks and gain no special gameplay behavior. Repeated bot acquisitions are cheap after that owner's cache is loaded, but a large population acquiring its first eligible item concurrently can still produce normal character-database read/write load. Operators may disable unlock-on-acquire while diagnosing load. Owner caches are released on logout to bound long-lived memory; if another same-account character remains active, its next acquisition safely reloads that account through the owner index.

## Known acquisition limitations

- The central new-item hook records the core storage category, not a precise creature/quest/craft identifier.
- Items deposited directly into bank/guild bank without first entering player inventory are not unlocked at deposit time. A later move into player inventory is observable.
- Auction delivery is collected when its mail attachment is taken, not when the auction completes.
- Phase 3B all-choice quest reward discovery is not implemented; only the reward actually received passes through normal storage.
- Historical ownership is not inferred.
