# Phase 2 retail portrait investigation

## Decision

Build 12340 can render one isolated item appearance on a separate character model. The implementation in this phase is therefore a default-off, one-tile PTR experiment, not a production catalog change. It is deliberately restricted to the first non-Hide tile in the Head catalog.

The production icon remains underneath the model and is restored merely by disabling the experiment. No server message, catalog identity, compatibility rule, application path, collection path, or Collections-window renderer changed.

## Verified build-12340 surface

The checked-in stock `FrameXML.toc` loads `DressUpFrame.xml`. The extracted 3.3.5a FrameXML uses a `DressUpModel`, calls `SetUnit("player")`, and passes an item link to `TryOn`. A build-12340 registration-table inventory independently reports these methods:

- `DressUpModel`: `Undress`, `Dress`, `TryOn`.
- `PlayerModel`: `SetUnit`, `SetCreature`, `RefreshUnit`, `SetRotation`.
- `Model`: `SetModel`, `ClearModel`, `SetPosition`, `SetFacing`, `SetModelScale`, `SetSequence`, `SetSequenceTime`, `SetCamera`, `SetLight`, and the corresponding limited getters.

Two commonly suggested methods are not exposed by build 12340: `DressUpModel:UndressSlot` and `PlayerModel:SetPortraitZoom`. Modern API documentation must not be used for this client.

`TryOn` accepts the catalog's canonical item entry (the existing main preview already does this) or an item link. `SetUnit("player"); Undress(); TryOn(entry)` gives an otherwise-undressed player model with the requested appearance. This is the strongest isolation build 12340 offers. It cannot remove only one slot from an already dressed model.

Independent `DressUpModel` widgets have per-widget unit, dress, position, facing, scale, and camera state. The wardrobe already has separate main and Collections models without shared state. The prototype owns one third widget and never calls the two existing model accessors.

Evidence inspected:

- Project-pinned TOC: `content/upstream/FrameXML.toc` (the manifest pins SHA-256 `3158bea13225ae51137a389f0f3ab8566e94b6be84196dd2c1fda27024677754`).
- Extracted 3.3.5 interface mirror: <https://github.com/wowgaming/3.3.5-interface-files/blob/main/DressUpFrame.lua> and <https://github.com/wowgaming/3.3.5-interface-files/blob/main/DressUpFrame.xml>.
- Build-12340 executable registration-table inventory: <https://github.com/brues-code/ClassicAPI/blob/master/docs/BlizzardScriptAPI_3.3.5.md#frame-methods>.
- Existing project proof: the main wardrobe and separate Collections preview both use independent `DressUpModel` widgets in `NativeTransmogFrame.xml`; `previewItem` already passes a catalog entry to `TryOn`.

## PTR diagnosis and corrected prototype

The floating model had a layout cause, not a catalog-coordinate cause. The original widget was created with the appearance button as parent, so its hierarchy was `NativeTransmogFrame` → `BrowserPanel` → `ScrollFrame` → `ScrollChild` → appearance button → `DressUpModel`. It was then constrained with `SetAllPoints(button.icon)`, where the relative region was a texture. Build 12340 has no `SetClipsChildren`, and its 3-D model widgets cannot be treated as reliably clipped texture children inside a scroll child. The button was 84×111, the texture-relative model viewport was only 72×72, and no explicit frame level was assigned. The screenshots are consistent with the native model viewport being composited against the scroll/browser area instead of the intended tile rectangle.

The corrected widget is declared once in XML as an 84×111 child of `NativeTransmogFrameBrowserPanel`, outside the `ScrollFrame`. Lua anchors its two corners directly to the first real Head appearance button and assigns it one frame level above that button. The icon remains beneath it. This avoids reliance on unavailable child clipping and on a texture as the model's geometry reference. It is still exactly one model and one tile.

The inconsistent full-body/head scale was a lifecycle problem. The old code reused the hidden native model without clearing it and issued camera/scale/position calls immediately after `SetUnit`. Native unit/model initialization can complete after that Lua call sequence and restore the model's default camera. Which state won depended on whether the model and item were already loaded. The corrected activation clears the previous native model, reconstructs dress state, applies the full camera preset immediately, and reasserts it during a bounded 0.25-second initialization window.

`NativeTransmog_SetPortraitPrototype(true)` now reuses the one XML-owned `DressUpModel` for the first real Head tile and performs:

1. Hide and `ClearModel()` the previous native state, then call `GetItemInfo(entry)` to obtain the item link used by Blizzard's build-12340 dressing room. If unresolved, the model stays hidden, the icon remains visible, and `GET_ITEM_INFO_RECEIVED` retries the entire activation.
2. `SetUnit("player")`.
3. `Undress()`.
4. `TryOn(itemLink)` when the link is resolved.
5. Camera 0, facing/rotation 0, model scale `1.80`, and position `(0, -0.13, 0)`, reasserted briefly while the native model finishes loading.

Disable, catalog rerender, category/page change, and Wardrobe close all hide and `ClearModel()` the widget, cancel pending camera initialization, and remove its tile reference. Re-enable and Wardrobe reopen therefore start from `SetUnit` rather than hidden native state. The item icon is never removed. The flag remains intentionally unpersisted across a UI reload.

Camera 0 plus `SetModelScale` and `SetPosition` is the only verified build-12340 route to a close crop. There is no field-of-view, custom-camera, or `SetPortraitZoom` API. The corrected viewport and repeatable preset should give the same head/shoulders framing on every activation, but a universal close crop is not guaranteed across race, sex, hairstyle, horns/ears, and helm geometry. PTR must validate the retained `1.80/-0.13` preset; unsupported modern camera APIs must not be added if that preset cannot cover the matrix.

## Appearance isolation result

The verified build-12340 isolation sequence is `SetUnit("player"); Undress(); TryOn(itemLink)`. `Undress()` removes the dressable equipment copied by `SetUnit`; `TryOn` then adds the one resolved catalog head item. The original prototype used the same isolation order, so the apparent retained equipment in a tiny full-body screenshot cannot by itself prove that `Undress()` failed—the body was too small to distinguish base underwear/geosets from equipped armor, and an unresolved numeric entry had no success result. The correction removes that ambiguity by using the item link accepted by Blizzard's own `DressUpFrame` and by waiting for cache resolution. There is still no success return or model-ready event, so visual confirmation with one known collected head appearance is required on PTR. If non-head equipped armor remains visibly present after this corrected sequence, build 12340 cannot provide stronger slot isolation with its exposed API and the prototype must remain icon-only.

## Loading, failure, compatibility, and performance risks

- Item data is asynchronous. `TryOn` has no success return and no model-ready event in this API. A successful item-info event proves cache resolution, not visible geometry.
- Invalid, missing, nondressable, or zero-display items can leave an undressed model. The icon fallback and tooltip remain authoritative presentation fallbacks.
- Reset order matters. Every reuse clears the native model and calls `SetUnit`, `Undress`, and `TryOn`; otherwise prior slot state can survive because dressing is last-write-wins per slot.
- Build 12340 provides no supported clipping API for arbitrary model children. The corrected one-tile viewport avoids needing one; it does not establish that model widgets are safe in a scrolling 18-tile grid.
- Hide is not an item and is never sent to the model.
- Hair, ears, horns, weapon sheathing, robes, tabards, and some geosets can crop or occlude unexpectedly. Lighting is selectable but the stock camera light is retained in the prototype because there is no documented portable light preset across races.
- One model is a small bounded cost. Eighteen simultaneously animated player models multiply geometry, composited character textures, item models, animation updates, and draw calls. The 3.3.5 client offers no reliable Lua memory/GPU accounting per model and no readiness signal. Full-page expansion is therefore not approved until PTR frame-time and memory tests pass. Reusing only the visible models, pausing/hiding offscreen widgets, or pre-rendering textures are not assumed available solutions.
- Server-authoritative collection and compatibility are untouched: only entries already supplied by the existing catalog can be previewed, and Apply still uses the existing nonce/request validation.

## Decorative-corner finding

`Interface\\DialogFrame\\UI-DialogBox-Header` is used by stock/addon FrameXML as a horizontal title header. Cropping its end caps into four `90x44` textures produces narrow fragments, not the large L-shaped bronze foliage in the reference. Further texcoord adjustment cannot manufacture the missing vertical artwork.

The checkout contains the stock TOC and FrameXML references but not an extracted copy of every client BLP archive, so it cannot prove that no obscure stock texture exists. It does prove that the current header source is structurally wrong, and the repository-wide FrameXML inventory found no stock corner asset already used for this purpose. A purpose-built texture is therefore the deterministic recommendation; substituting another unverified stock path would merely move the PTR uncertainty.

Recommended production asset (not implemented here):

- Path: `Interface\\NativeTransmog\\WardrobeCorners.blp`.
- Canvas: `256x256` pixels, power-of-two.
- Layout: four `128x128` cells in TL, TR, BL, BR order; ornament contained within each cell with at least a 2-pixel transparent gutter.
- Encoding: BLP2, BC3/DXT5, explicit 8-bit alpha; transparent pixels must have zero alpha and edge colors should be bled beneath alpha to avoid dark fringes.
- Display size: `72x72` UI units per corner.
- Anchors on `NativeTransmogFrame`: TL `TOPLEFT` at `(305,-72)`, TR `TOPRIGHT` at `(-8,-72)`, BL `BOTTOMLEFT` at `(305,8)`, BR `BOTTOMRIGHT` at `(-8,8)`.
- Texcoords: TL `(0,.5,0,.5)`, TR `(.5,1,0,.5)`, BL `(0,.5,.5,1)`, BR `(.5,1,.5,1)`.

The existing schema-3 EPF `file` entries preserve arbitrary bytes and paths, so this can be packaged through the current pipeline by adding the BLP as a manifest content file. No EPF schema or standalone addon is needed. Artwork creation is outside this investigation.

## Bottom-left correction proposal

The empty rectangle is intentional current geometry: the `284x474` preview reserves a `274x54` opaque state band at its bottom, while the race background and model stop above it. Remove that dedicated band in the approved layout pass, extend the four race-background pieces and the model viewport to the preview panel's lower inset, and keep the existing equipment slots, weapon row, rotation controls, Reset, Apply, Remove, and outfit controls at their current anchors.

Place the three state readouts as a compact, single-row footer in the unused right-side gap below the catalog and above pagination: three approximately `180x14` columns labeled `Equipped`, `Applied`, and `Preview`, each retaining its full-item tooltip. This preserves all three distinct states without consuming character-preview height. At narrow effective scales the whole fixed `960x600` frame continues to scale uniformly, so the columns do not independently reflow.

## PTR procedure

1. Build `content/mod-native-transmog.epf` with `python3 content/build_epf.py` and deploy it through the existing mod-content-manager/Portalkeeper flow. Do not install an addon or change the server module/database.
2. Start build 12340 with Lua errors enabled. Interact with a registered Transmogrifier, equip a head item, select Head, and wait for a page containing at least one non-Hide appearance.
3. Capture the baseline: icons render, the main character preview rotates/resets, and Apply/Remove behavior is unchanged.
4. Choose a page whose first non-Hide entry is a known collected head appearance. Record its icon/name, then run `/run NativeTransmog_SetPortraitPrototype(true)`.
5. Confirm exactly that one real Head tile contains a stable close-up and that the helm matches the recorded appearance. Inspect shoulders/chest carefully: no equipped dressable gear should remain. Base skin, hair, underwear, and race geosets are expected.
6. Run `/run NativeTransmog_SetPortraitPrototype(false)` and confirm the model disappears immediately and the original icon is still present. Repeat the same enable/disable pair two more times (three total cycles). On all three enables, compare scale, facing, position, crop, and helm; they must be identical. At no point may a second model or a model outside the tile appear.
7. Leave the prototype enabled. Change page, return to the original page, select another equipment category, return to Head, close the Wardrobe, and reopen it. Each transition must either hide the prototype or reconstruct the same single-tile portrait; no stale full-body model may reappear.
8. Rotate/reset the large character preview and confirm the tile model does not rotate, dress, clear, or otherwise change. Select the portrait tile and confirm only the large preview changes as before.
9. Test a cached item and, after clearing the client item cache in the normal PTR-safe manner, an initially uncached item. While unresolved, confirm the item icon remains visible. After `GET_ITEM_INFO_RECEIVED`, confirm the same isolated portrait appears without a Lua error.
10. Test at least male/female representatives of Human, Night Elf, Tauren, Gnome, Troll, and Draenei at UI scales 0.64, 0.8, and 1.0. Record crop, ears/horns/hair clipping, helm visibility, frame rate, and process working-set delta with the Wardrobe closed, icon-only, and one-model modes. Recheck Apply, Remove, Reset Preview, pagination, equipment slots, and the separate gold Collections window.

## Recommendation gate

Do not expand to 18 tiles yet. Proceed only if the one-model test is stable across the race/sex/UI-scale matrix, cached and uncached data, repeated page changes, and a 10-minute open-window performance soak. Even after that, approve a second bounded test of three visible models before 18. A full page should be rejected if crops require per-race manual tuning that cannot be made deterministic, models intermittently remain undressed, or frame time/memory rises materially on the PTR's minimum supported client hardware.
