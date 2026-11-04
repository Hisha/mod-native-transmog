# Phase 4B native paper-doll architecture

## Build-12340 UI inspection

Phase 4B was designed against the extracted WoW 3.3.5a FrameXML resources for `CharacterFrame.xml/.lua`,
`PaperDollFrame.xml/.lua`, and `DressUpFrame.xml/.lua`, plus the repository's verified build-12340
`FrameXML.toc`. The relevant stock behavior is:

- `CharacterFrame` is a 384x512 managed panel whose tab/subframe code owns `PaperDollFrame` visibility,
  portrait, and global character-sheet state. The wardrobe remains a separate dialog and does not modify it.
- `PaperDollItemSlotButtonTemplate` inherits `ItemButtonTemplate`, then adds CharacterFrame event registration,
  equipping/dragging, modified-click handling, cursor behavior, equipment-set flyouts, and a private
  `itemSlotButtons` registry. Those ownership-bearing handlers are not reused.
- `PaperDollItemSlotButton_OnLoad` derives the inventory ID and native empty texture with
  `GetInventorySlotInfo`. `PaperDollItemSlotButton_Update` uses `GetInventoryItemTexture`,
  `SetItemButtonTexture`, item counts, broken-state coloring, and cooldowns. Phase 4B reuses the safe icon and
  inventory API conventions locally, without calling the CharacterFrame update function.
- `PaperDollItemSlotButton_OnEnter` uses `GameTooltip:SetInventoryItem("player", slot)`. Phase 4B uses that
  native item tooltip call directly and appends only wardrobe-local confirmed-state text.
- The stock paper doll places armor slots in vertical edge columns and main/off/ranged in a horizontal bottom
  row. Phase 4B follows that grammar at a larger 900x540 dialog size so the existing catalog can remain beside
  the model at original WotLK UI scale.
- `DressUpFrame` uses `DressUpModel`, `SetUnit("player")`, `TryOn`, stock rotation artwork, and race-specific
  backgrounds. Phase 4B retains its existing isolated `DressUpModel`, `TryOn`, drag/wheel rotation, and reset
  behavior. It does not call functions that assume the global `DressUpFrame` model or textures.

All textures referenced by Phase 4B are stock named interface assets: dialog and tooltip backgrounds/borders,
quick-slot and item-button art, check highlights, rotation buttons, ReadyCheck markers, the group-loot pass
marker, and existing inventory/item icons. No custom texture ID or new bitmap asset is introduced.

## Local paper-doll implementation

`NativeTransmogEquipmentSlotTemplate` inherits only `ItemButtonTemplate`. Fourteen instances retain the Phase 4A
wire IDs while resolving their actual client inventory IDs from the existing slot-name mapping. Left and right
vertical columns surround a 286x342 model. Main hand, off hand, and ranged form a bottom row above the Reset and
rotation controls. The 408x292 scrollable appearance catalog remains on the right, with five tiles per row and
unchanged cursor pagination.

Equipped icon updates are client-local and read-only. On load, show, world entry, and
`PLAYER_EQUIPMENT_CHANGED`, the UI reads `GetInventoryItemTexture` and `GetInventoryItemCount`. An empty slot uses
the texture returned by `GetInventorySlotInfo`, cannot issue `CAT`, and cannot enable Apply or Remove. Clicking it
selects the location only long enough to show `Equip an item to customize this slot.`

## Class-specific presentation

All supported armor/body/hand slots and both hand slots have a potentially dressable item for every WotLK class.
The exceptional physical position is ranged: death knights, paladins, druids, and shamans use it for relics,
which have no character-model appearance. The stock client already exposes this distinction through
`UnitHasRelicSlot("player")`; the wardrobe dims that position, prevents catalog requests, and explains that it has
no customizable appearance. This follows the client's class/equipment convention and avoids hardcoded class
names. For usable slots, the existing server validator still enforces class, race, skill, spell, armor/weapon
proficiency, subclass, inventory type, hand, and configuration rules. No server rule is weakened.

## Confirmed indicators and additive state sync

The Phase 4A `PAGE` reply confirms state only for the selected slot. Phase 4B needs authoritative markers on the
whole paper doll before a click, so the server sends fourteen small additive replies after `OPEN`:

```text
NTRANSMOG\t2\tSTATE\t<session-token>\t<wire-slot>\t<state>\t<appearance-entry>
```

State `0` is the effective original presentation, `1` is an applied collected appearance, and `2` is actively
hidden. A retained hidden-weapon row reports `0` while weapon hiding is disabled, matching its effective render.
The server derives state from the currently equipped item instance and the existing `ApplicationService` cache.
`STATE` is outbound-only and adds
no mutation, opcode, database column, or new protocol version. The existing authenticated self-whisper filter now
allows that response vocabulary. `PAGE` continues to refresh the selected marker after a confirmed mutation.
Local preview selection never changes a paper-doll marker.

Applied state uses a 15px stock ReadyCheck marker; hidden state uses a 17px stock group-loot pass marker. Both
occupy only the lower-right corner and leave the item icon readable. Original state has no overlay.

## Tooltip and preview behavior

Equipped slots call `GameTooltip:SetInventoryItem` and optionally append `Appearance: Hidden` or
`Transmogrified appearance active` from confirmed state. Empty and class-inapplicable slots use concise local
text. No global GameTooltip hook is installed.

Selecting a slot does not touch the model. Selecting a catalog tile resets the model to the currently visible
player state and applies only that preview. Reset Preview calls `SetUnit("player")` and sends no mutation. For
Hide preview the client first tries the slot-local `DressUpModel:UndressSlot` API. Because availability must be
confirmed in the actual build-12340 client, the call is guarded. The Phase 4A reconstruction remains as fallback:
it undresses and retries every physical link except the selected slot. That fallback can temporarily restore
other slots' original item appearances; Reset Preview restores the server-visible state. No unsafe render field,
character equipment mutation, or dependency on the slot API is introduced.

## Unchanged boundaries

Catalog collection, compatibility, nonce/item-GUID snapshots, NPC authorization, pagination, Hide policy,
application/removal, persistence, equipment collection hooks, and the FrameForge/EPF/Content Manager/Portalkeeper
pipeline are unchanged. There is no equipment-set catalog, outfit storage, cost, collection notification, global
tooltip hook, standalone addon, new opcode, or Portalkeeper change.

