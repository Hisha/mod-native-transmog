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
- Playerbot revision `e7e2e288e7d9ec30e2dfe6f417178a95986fcbb2` exposes
  `ServerScript::OnPacketSent`. The final server-authored `SMSG_LOOT_ROLL_WON`
  packet carries the original item entry, winner GUID, winning roll, and roll
  type. The module handles only roll type `DISENCHANT` and only on the winning
  player's own authenticated session, then passes the original item template to
  `CollectionService::Unlock` with `AcquisitionSource::DisenchantRoll`.
- `PLAYERHOOK_ON_GROUP_ROLL_REWARD_ITEM` remains confined to Need and Greed.
  Disenchant conversion does not create the original item, so the packet hook is
  the only active Disenchant path. Material item-acquisition callbacks are not
  used to infer the destroyed appearance.

The winner packet is emitted synchronously after the roll winner and vote type
are finalized, immediately before the core consumes the original item and
generates enchanting loot. Network delivery is not acquisition authority: the
module observes the server-authored result before socket dispatch, including for
client-less Playerbot sessions.

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
