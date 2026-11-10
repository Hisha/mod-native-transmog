# Equipment-focused catalog portraits: implementation and PTR validation

Implementation date: 2026-11-10.

## Implementation status

The Wardrobe reuses the single XML-owned `NativeTransmogCatalogPortraitModel` for the currently selected appearance.
Selection clears the old model, resolves and verifies the exact source item link, calls `SetUnit("player")`,
`Undress()`, and `TryOn(itemLink)`, applies the selected slot's framing preset, and moves the model over the selected
tile. Every other tile remains an item icon. The main Wardrobe preview and Collections preview are not used by this
path.

The Head preset is unchanged from the PTR-accepted implementation. All other presets are implemented but have not
been visually verified in a build-12340 client and must be treated as initial tuning values.

| Wardrobe category | Rendering method | Camera / orientation | Scale | Position `(x,y,z)` | Visual status |
|---|---|---:|---:|---:|---|
| Head | Selected item dressed on isolated player model | camera 0, front `0` | `1.30` | `(0,-0.13,0)` | PTR accepted; preserved |
| Shoulders | Selected paired shoulder appearance on player model | camera 0, front `0` | `1.05` | `(0,-0.13,0.18)` | Implemented; PTR tuning required |
| Shirt | Selected garment texture/geometry on torso | camera 0, front `0` | `1.05` | `(0,-0.13,0.55)` | Implemented; PTR tuning required |
| Chest | Selected chest/robe texture and geometry on torso | camera 0, front `0` | `1.05` | `(0,-0.13,0.55)` | Implemented; PTR tuning required |
| Waist | Selected belt texture/geometry on player model | camera 0, front `0` | `1.05` | `(0,-0.13,1.05)` | Implemented; PTR tuning required |
| Legs | Selected leg texture/geometry on player model | camera 0, front `0` | `0.85` | `(0,-0.13,1.45)` | Implemented; PTR tuning required |
| Feet | Selected boot texture/geometry on player model | camera 0, front `0` | `1.00` | `(0,-0.13,2.15)` | Implemented; PTR tuning required |
| Wrists | Selected bracer textures/geometry with forearms | camera 0, front `0` | `0.78` | `(0,-0.13,0.58)` | Implemented; PTR tuning required |
| Hands | Selected glove/gauntlet textures and geometry | camera 0, front `0` | `0.82` | `(0,-0.13,0.68)` | Implemented; PTR tuning required |
| Back | Selected cloak on player model | camera 0, rear `pi` | `0.90` | `(0,-0.13,0.62)` | Implemented; PTR tuning required |
| Main Hand | Selected weapon dressed through `TryOn` | camera 0, facing/rotation `0.35` | `0.72` | `(0.20,-0.13,0.72)` | Implemented; held pose and crop require PTR verification |
| Off Hand | Selected weapon, shield, or held item through `TryOn` | camera 0, facing/rotation `-0.35` | `0.72` | `(-0.20,-0.13,0.72)` | Implemented; each item family requires PTR verification |
| Ranged | Selected bow, gun, crossbow, thrown weapon, or supported ranged item through `TryOn` | camera 0, facing/rotation `0.35` | `0.68` | `(0.18,-0.13,0.78)` | Implemented; held/sheathed pose and crop require PTR verification |
| Tabard | Selected garment texture on torso | camera 0, front `0` | `1.05` | `(0,-0.13,0.55)` | Implemented; PTR tuning required |

These are the module's actual 14 wire slots. A class relic in the ranged equipment slot remains excluded by the
existing `UnitHasRelicSlot` rule because it is not an ordinary dressable appearance.

## Build-12340 limitations and fallback

Build 12340 exposes no model-bounds query, field-of-view control, portrait zoom, success result from `TryOn`,
model-ready event, or supported isolated item-model renderer. Camera 0 plus model facing, rotation, scale, and
position is the verified control surface. Shirts, tabards, many chest/leg/waist/wrist/hand/foot appearances, and
parts of other armor are character textures rather than separable geometry, so the relevant dressed body region is
the honest 3-D representation.

Weapons, shields, held items, and ranged items are also dressed on the player model. The implementation does not
substitute a generic item model. Whether a particular item is held, sheathed, occluded, or outside the initial crop
cannot be detected from Lua and requires the matrix below.

The item-specific icon remains visible until item identity is resolved and the protected model initialization
finishes without a Lua error. Missing item data, an identity mismatch, a missing preset/model, or a failed protected
model call leaves that exact item's icon in place. A silent native `TryOn` failure has no programmatic signal; if PTR
finds a category or item family that cannot render reliably, keep its icon and record the unsupported family rather
than accepting a blank or unrelated portrait.

The source-item entry, selected slot, selected tile, selection identity, and generation token are all rechecked by
item-info and model-update callbacks. Switching slots or appearances invalidates the old generation before the next
render. During the bounded 0.25-second native initialization window, the selected source item remains the final
`TryOn` writer so late `SetUnit` initialization cannot restore equipped gear over it.

## Exact PTR procedure

### Prepare and publish

1. Use an isolated PTR checkout and record the module revision, active Content Manager build, client package hash,
   character race/sex/class, client build, resolution, and UI scale. Do not target production.
2. Run from the module root:

   ```bash
   python3 -m unittest discover -s tests -p 'test_*.py'
   python3 content/build_epf.py
   sha256sum content/mod-native-transmog.epf
   python3 content/build_epf.py
   sha256sum content/mod-native-transmog.epf
   python3 content/build_epf.py --check
   ```

   The two hashes must match.
3. Publish `content/mod-native-transmog.epf` through the existing FrameForge → EPF → Content Manager → Portalkeeper
   protected-FrameXML pipeline. Do not install an addon or edit a generated MPQ.
4. Launch the isolated build-12340 PTR client with Lua errors visible. Interact with a native Warpweaver; no script,
   slash command, or manual portrait activation is part of acceptance.

### Validate every category

5. For each row below, equip a compatible physical item, select the Wardrobe slot, and click at least three visually
   distinct collected appearances. Capture the selected icon and portrait after each click. A passing portrait must
   match that source item and emphasize the named region without overflowing into neighboring tiles.

   - [ ] Head — helmet/headpiece; confirm the accepted crop is unchanged.
   - [ ] Shoulders — both shoulder pieces visible where the model geometry permits.
   - [ ] Chest — chest or robe centered on the torso.
   - [ ] Shirt — shirt design centered on the torso.
   - [ ] Tabard — tabard design centered on the torso.
   - [ ] Wrists — both bracers/forearms recognizable.
   - [ ] Hands — both gloves/gauntlets recognizable.
   - [ ] Waist — belt and buckle centered.
   - [ ] Legs — leg armor fills the tile without feet/torso becoming the focus.
   - [ ] Feet — both boots recognizable.
   - [ ] Back — cloak shown from behind; verify rear orientation on short and long cloaks.
   - [ ] Main Hand — test one-hand and two-hand weapons; selected weapon is recognizable.
   - [ ] Off Hand — separately test a one-hand weapon, shield, and held-in-offhand item.
   - [ ] Ranged — separately test a bow, gun, and crossbow; test thrown/fishing appearances if the catalog offers them.

6. Repeat step 5 on at least one short race and one tall/wide race, both sexes where available. Record clipping,
   occlusion, empty space, and whether texture-only pieces remain legible. Tune only the relevant preset; do not alter
   tile/window dimensions or the accepted Head values.

### Identity, lifecycle, and fallback regressions

7. Enable `/nativetransmogportraitdebug`, click two known look-alike variants and verify each diagnostic reports its
   own appearance ID, source item ID, resolved item link, and matching `tryOnItemId`.
8. Click 10 appearances rapidly in one category, then switch categories during the 0.25-second initialization
   window. Only the last selected tile may contain a model; every prior tile must restore its own icon, with no late
   model jump or unrelated equipment.
9. Page forward/back, change slots, select Hide, close/reopen the Wardrobe, unequip the target, and reset the main
   preview. Each action must clear the catalog portrait cleanly. Hide and unavailable/relic slots remain icon/UI-only.
10. Test a normally uncached source item after clearing the client item cache by the PTR's approved procedure. Its
    item-specific icon must remain until item data resolves; an identity mismatch or Lua error must never reveal a
    stale model.
11. Rotate and reset the large character preview before and after catalog selections. Confirm it does not rotate,
    dress, clear, move, or otherwise share state with the tile portrait. Repeat in Collections/Appearances and Saved
    Sets and confirm those previews are unchanged.
12. Recheck Apply, Remove, Hide, pagination, equipment-slot selection, Saved Sets, acquisition/ownership, tooltips,
    and the purple selected-tile accent. No server, database, NPC, protocol, or transmog behavior should differ.

For each category, record **implemented framing result**, **visually verified result**, tested item entries, race/sex,
screenshots, and any item family left on icon fallback. Automated tests establish configuration and lifecycle only;
they do not establish that any new crop looks correct in the client.
