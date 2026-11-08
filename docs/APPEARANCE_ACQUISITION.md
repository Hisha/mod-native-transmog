# Appearance acquisition flow

All acquisition paths converge on `CollectionService::Unlock`; there is no
second collection store or eligibility implementation.

## Live paths

- `PLAYERHOOK_ON_STORE_NEW_ITEM` covers newly created physical items, including
  direct loot, crafting, and delivered quest rewards.
- `PLAYERHOOK_ON_AFTER_MOVE_ITEM_TO_INVENTORY` covers existing items entering
  inventory through paths such as trade or mail.
- `PLAYERHOOK_ON_EQUIP` rechecks the authoritative equipped slot after success
  and unlocks eligible equipment that was not observed through acquisition.
- `PLAYERHOOK_ON_PLAYER_COMPLETE_QUEST` enumerates all offered and guaranteed
  quest rewards after core reward delivery, then uses the same service.
- Need and Greed group-roll wins create and store the original item; the normal
  `STORE_NEW_ITEM` path therefore collects them.
- Playerbot revision `8a4e76eac8c4ccebf547113afe7b51d6c3e91641` never creates the original
  item. The additive `PLAYERHOOK_ON_GROUP_ROLL_DISENCHANT` hook fires once for
  the resolved winner immediately before the core generates enchanting
  materials. The module resolves `itemEntry` to the original `ItemTemplate` and
  calls `CollectionService::Unlock` with `DisenchantRoll` provenance.

Selecting Disenchant does not invoke the winner hook. Losing, passing, going
offline before resolution, or another player winning produces no collection
call for that player. Material generation and its inventory-full mail fallback
remain entirely core-owned and execute after the hook.

## Eligibility and deduplication

`ResolveAppearance` requires a loaded `ItemTemplate`, nonzero `DisplayInfoID`
present in `ItemDisplayInfo.dbc`, armor or weapon class, and a supported visible
equipment inventory type. It intentionally does not inspect item quality,
class/race usability, proficiency, required skill, or required spell. Eligible
poor (gray) and common (white) armor and weapons therefore collect; arbitrary
gray junk, non-equipment inventory types, and missing display records do not.

The durable identity is `(display_id, item_class, item_subclass,
inventory_type)`. The active owner scope is derived only from the authenticated
player session. An owner cache avoids repeat work, while the database composite
primary key and synchronous `INSERT IGNORE` preserve first provenance and make
all overlapping hooks idempotent.

Collection state is stored in the character database table
`native_transmog_collection`. Account-wide mode keys it by account ID;
character mode keys it by character GUID counter. Switching modes does not
delete or rewrite either namespace.
