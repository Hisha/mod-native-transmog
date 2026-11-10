# Phase 3C appearance application architecture

Phase 3C adds server-authorized application, compatibility validation, item-instance persistence, lifecycle cleanup, and visible rendering. It retains the Phase 1 protected-FrameXML preview, Phase 2 NPC authorization, and Phase 3A/3B collection unchanged. There is still no client wardrobe application button or client-supplied apply packet.

## Authority and ownership

`ApplicationService::Apply` accepts only an authenticated `Player`, an equipped server-side slot, a world item-template entry, and an explicit authority category. Ordinary application authority requires a current Phase 2 Transmogrifier session and immediately revalidates its creature, registration, map, distance, combat, alive, and interaction state. The GM diagnostic path is separate and protected by existing AzerothCore RBAC and target-security checks.

The target `Item` is resolved from the player's server-side equipment and must be owned by that character. The source template must resolve to the same composite appearance key used by the collection. `CollectionService::IsCollected` derives the current account or character owner from the authenticated session; no application API accepts an account ID, owner GUID, target item GUID, display ID, or compatibility assertion from a client.

Persistence completes synchronously before the in-memory override becomes visible. Failure at any validation step leaves the item, visible fields, cache, and database unchanged.

## Compatibility policy

Collection remains intentionally broad. Every application independently checks:

- source and target are eligible visible armor/weapon templates;
- the source `AllowableClass` and `AllowableRace` contain the player, and required skill/rank/spell gates pass;
- source and target are both armor or both weapons;
- armor subclasses match exactly and the player has the source armor proficiency;
- armor inventory types match, with chest and robe treated as one visual slot;
- the player has the source weapon proficiency;
- one-hand main-hand/off-hand restrictions are preserved;
- other weapon inventory types match exactly;
- one-handed axes, maces, and swords are mutually compatible;
- two-handed axes, maces, swords, and polearms are mutually compatible;
- all other weapon subclasses retain exact-subclass behavior, and handedness never crosses.

`NativeTransmog.AllowTwoHandAppearanceOnOneHand` and `NativeTransmog.AllowOneHandAppearanceOnTwoHand` remain parsed as legacy settings so existing realm configuration does not break, but they no longer broaden eligibility. This supersedes the earlier Phase 3C family-crossing policy because PTR acceptance requires handedness to remain strict while axe/mace/sword subclasses cross within a handedness group.

## Persistence and rendering

`native_transmog_item_override` is a new character-database table keyed by `item_guid`. It records the authenticated character owner, authoritative source item entry, validated display/category identity, and application timestamp. It has no foreign key and no relationship to legacy `mod-transmog` tables. The source item entry is used in `PLAYER_VISIBLE_ITEM_1_ENTRYID`; the real equipped item remains unchanged and continues to supply stats, combat behavior, enchantments, durability, and ownership.

On login, rows for the character are loaded only when the item instance still belongs to the player, the source template and stored appearance identity still agree, and current compatibility policy still permits the pairing. Invalid rows are removed. Equipped slots are then refreshed through `Player::SetVisibleItemSlot`. The post-visible-slot hook revalidates the actual main/off-hand slot before reapplying an override after ordinary equip/unequip/core refreshes, allowing normal object-field propagation to synchronize the owner and nearby observers. The mirror-image hook supplies the override display ID.

Removing an override deletes the owner-scoped row before refreshing the equipped slot to its real entry. Moving an item out of character inventory synchronously removes its override. Permanent item deletion appends cleanup to the core's existing character-database transaction. Logout releases only in-memory cache state; the row remains for the next login.

## Diagnostics and phase boundary

The following commands target the selected online player, or the executing GM when no player is selected:

```text
.nativetransmog appearance apply <equipment-slot> <appearance-item-entry>
.nativetransmog appearance remove <equipment-slot>
.nativetransmog appearance info <equipment-slot>
```

Apply uses NPC-add RBAC, removal uses NPC-delete, and inspection uses NPC-info. These are diagnostic server commands, not a player-facing application UI.

Phase 3C does not add saved outfits, hide-item appearances, appearance costs, client collection filtering, an application addon, arbitrary resource IDs, or legacy data import. The existing EPF is unchanged.

## Core hooks and limitations

The inspected Playerbot core provides every hook needed for the implemented lifecycle; no core patch was required. The branch does not expose a supported API for replacing an item's visible entry in every possible one-off packet. Phase 3C covers normal player object-field propagation and the explicit mirror-image display hook. PTR must still validate nearby observers, relog, equipment swaps, bank/mail/trade/auction transfer paths, death/teleport, and mirror images.

Disabling `NativeTransmog.Application.Enable` on a live configuration reload clears the module cache but does not proactively iterate every online player's visible slots; use a controlled PTR restart or relog/equipment refresh for rollback validation. No attempt is made to preserve an override when an item leaves the character's ownership.

The project owner retired `mod-transmog` from PTR. Production remains unchanged. Phase 3C contains no coexistence layer, hook arbitration, legacy API call, table migration, or import path.
