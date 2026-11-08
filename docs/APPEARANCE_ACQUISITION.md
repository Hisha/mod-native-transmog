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
- Playerbot revision `8a4e76eac8c4ccebf547113afe7b51d6c3e91641` does not expose a supported
  script callback for a successful Disenchant roll. Its
  `PLAYERHOOK_ON_GROUP_ROLL_REWARD_ITEM` calls are confined to the Need and
  Greed branches. The Disenchant branch knows both the winner and original item,
  but converts the item directly into enchanting loot without invoking a public
  hook that carries both values.

The item-acquisition hooks invoked by material generation identify only the
enchanting materials. Inferring the destroyed appearance from those materials
is ambiguous and is therefore intentionally not attempted. Disenchant-roll
appearance acquisition remains pending a suitable interface in the target
core; selecting or winning Disenchant currently produces no collection call.

`AcquisitionSource::DisenchantRoll` remains reserved solely so collection rows
created by earlier deployments with a custom core patch retain readable
provenance. There is no active module path that writes this source on PTR.

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
