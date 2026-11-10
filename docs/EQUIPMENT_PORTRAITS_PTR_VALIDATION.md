# Catalog portrait camera and weapon navigation validation

Investigation date: 2026-11-10.

## Build-12340 camera result

The build-12340 registration inventory exposes these relevant methods:

- `DressUpModel`: `Undress`, `Dress`, and `TryOn`.
- inherited player/model controls: `SetUnit`, `SetCamera`, `SetFacing`,
  `SetRotation`, `SetModelScale`, `SetPosition`, `ClearModel`, and limited
  corresponding getters.

It does not expose a model-bounds query, field-of-view control, camera target,
portrait zoom, model-ready event, `TryOn` success result, or isolated item-model
renderer. In particular, modern `SetPortraitZoom` guidance does not apply.

The removed non-Head configurations changed camera 0's facing, scale, and
`SetPosition` coordinates. Confirmed PTR behavior shows that those calls do not
reliably pan the viewport from the head to a selected body region. The renderer
did apply each slot's table entry: it called the transform sequence immediately
and again during its bounded 0.25-second initialization window. That same
delayed callback also repeated `Undress(); TryOn(itemLink)` before reapplying the
transform. The sequence therefore did not overwrite a working category camera
with Head values; it repeatedly applied ineffective or incorrectly interpreted
non-Head transforms.

There is no supported API evidence for a different deterministic vertical or
horizontal viewport repositioning scheme. Rather than substitute another set
of guessed offsets, production now keeps the PTR-verified Head configuration
unchanged and leaves Shoulders, Shirt, Chest, Waist, Legs, Feet, Wrists, Hands,
Back, Main Hand, Off Hand, Ranged, and Tabard on their normal item icons.

| Category | Catalog rendering | PTR status |
|---|---|---|
| Head | Single reusable `DressUpModel`; camera 0, scale `1.30`, position `(0,-0.13,0)` | Previously accepted; regression verification required |
| All other supported equipment categories | Normal item icon | Deterministic fallback; verify no head model appears |
| Relic/ranged slot on relic classes | Existing unavailable-slot behavior | Unchanged |

## Weapon navigation result

Main Hand, Off Hand, and Ranged already had complete module support: XML wire
IDs 11/12/13, `MainHandSlot`/`SecondaryHandSlot`/`RangedSlot` inventory names,
the common click handler, catalog requests, and server mappings to
`EQUIPMENT_SLOT_MAINHAND`, `EQUIPMENT_SLOT_OFFHAND`, and
`EQUIPMENT_SLOT_RANGED`. No intentional weapon-category disable was present.

Their horizontal row overlaps the mouse-enabled large character preview. The
preview could receive hit testing above those center buttons, unlike most
side-column slots. Equipment-slot initialization now puts every slot button one
frame level above the preview model. The remaining visible model area continues
to handle drag rotation. No server or collection behavior changed.

## Automated validation

Run from the module root:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 content/build_epf.py
sha256sum content/mod-native-transmog.epf
python3 content/build_epf.py
sha256sum content/mod-native-transmog.epf
python3 content/build_epf.py --check
```

The tests assert that only Head has a 3D framing entry, unsupported categories
retain icons, stale callbacks remain rejected, only one catalog model exists,
weapon buttons sit above the mouse-enabled preview, clicks use the shared slot
handler, and all three client/server slot mappings remain connected. These are
source and lifecycle contracts, not proof of client pixels or hit testing.

## Required PTR checks

1. Select two different Head appearances, including one initially uncached.
   Confirm the existing crop, exact item identity, rapid-selection behavior,
   and cleanup on page/slot/close transitions remain correct.
2. Visit every non-Head category and click multiple appearances. Confirm the
   selected tile remains its normal item icon and never presents the character's
   head as the selected equipment.
3. With compatible physical items equipped, click Main Hand, Off Hand, and
   Ranged. Confirm each selection highlight moves, its title changes, and its
   catalog request completes. A relic class should retain the existing ranged
   unavailability message.
4. Drag the uncovered character preview before and after weapon navigation to
   confirm rotation still works. Recheck Apply, Remove, Hide, pagination,
   Collections, Saved Sets, and the EPF deployment path.

Automated tests cannot establish successful visual framing or native hit
testing. Head and the three restored weapon buttons still require this PTR
verification; the other categories intentionally require no 3D framing check.
