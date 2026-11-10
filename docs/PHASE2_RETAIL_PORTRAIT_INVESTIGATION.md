# Phase 2 retail portrait investigation

> Historical record: the default-off three-portrait prototype described below
> has been removed. The production behavior and command-free PTR procedure are
> documented in `CATALOG_PORTRAIT_IMPLEMENTATION.md`; the prototype Lua commands
> in this file no longer exist.

## Decision

Build 12340 can render isolated item appearances on separate character models. The implementation is now a default-off, maximum-three-tile PTR experiment, not a production catalog change. It is deliberately restricted to the first three unique non-Hide entries in the ordered Head catalog.

The production icon remains underneath the model and is restored merely by disabling the experiment. No server message, catalog identity, compatibility rule, application path, collection path, or Collections-window renderer changed.

## Verified build-12340 surface

The checked-in stock `FrameXML.toc` loads `DressUpFrame.xml`. The extracted 3.3.5a FrameXML uses a `DressUpModel`, calls `SetUnit("player")`, and passes an item link to `TryOn`. A build-12340 registration-table inventory independently reports these methods:

- `DressUpModel`: `Undress`, `Dress`, `TryOn`.
- `PlayerModel`: `SetUnit`, `SetCreature`, `RefreshUnit`, `SetRotation`.
- `Model`: `SetModel`, `ClearModel`, `SetPosition`, `SetFacing`, `SetModelScale`, `SetSequence`, `SetSequenceTime`, `SetCamera`, `SetLight`, and the corresponding limited getters.

Two commonly suggested methods are not exposed by build 12340: `DressUpModel:UndressSlot` and `PlayerModel:SetPortraitZoom`. Modern API documentation must not be used for this client.

`TryOn` accepts the catalog's canonical item entry (the existing main preview already does this) or an item link. `SetUnit("player"); Undress(); TryOn(entry)` gives an otherwise-undressed player model with the requested appearance. This is the strongest isolation build 12340 offers. It cannot remove only one slot from an already dressed model.

Independent `DressUpModel` widgets have per-widget unit, dress, position, facing, scale, and camera state. The wardrobe already has separate main and Collections models without shared state. The prototype owns a fixed pool of three additional widgets and never calls the two existing model accessors.

Evidence inspected:

- Project-pinned TOC: `content/upstream/FrameXML.toc` (the manifest pins SHA-256 `3158bea13225ae51137a389f0f3ab8566e94b6be84196dd2c1fda27024677754`).
- Extracted 3.3.5 interface mirror: <https://github.com/wowgaming/3.3.5-interface-files/blob/main/DressUpFrame.lua> and <https://github.com/wowgaming/3.3.5-interface-files/blob/main/DressUpFrame.xml>.
- Build-12340 executable registration-table inventory: <https://github.com/brues-code/ClassicAPI/blob/master/docs/BlizzardScriptAPI_3.3.5.md#frame-methods>.
- Existing project proof: the main wardrobe and separate Collections preview both use independent `DressUpModel` widgets in `NativeTransmogFrame.xml`; `previewItem` already passes a catalog entry to `TryOn`.

## PTR diagnosis and corrected prototype

The floating model had a layout cause, not a catalog-coordinate cause. The original widget was created with the appearance button as parent, so its hierarchy was `NativeTransmogFrame` → `BrowserPanel` → `ScrollFrame` → `ScrollChild` → appearance button → `DressUpModel`. It was then constrained with `SetAllPoints(button.icon)`, where the relative region was a texture. Build 12340 has no `SetClipsChildren`, and its 3-D model widgets cannot be treated as reliably clipped texture children inside a scroll child. The button was 84×111, the texture-relative model viewport was only 72×72, and no explicit frame level was assigned. The screenshots are consistent with the native model viewport being composited against the scroll/browser area instead of the intended tile rectangle.

Each of the three pool widgets is declared once in XML as an 84×111 child of `NativeTransmogFrameBrowserPanel`, outside the `ScrollFrame`. Lua anchors each widget's two corners directly to its assigned Head appearance button and assigns it one frame level above that button. The icons remain beneath them. This preserves the corrected hierarchy without relying on unavailable child clipping or on textures as model geometry references. Missing appearances leave the unused pool widgets hidden and cleared; no runtime widget is created.

The inconsistent full-body/head scale was a lifecycle problem. The old code reused the hidden native model without clearing it and issued camera/scale/position calls immediately after `SetUnit`. Native unit/model initialization can complete after that Lua call sequence and restore the model's default camera. Which state won depended on whether the model and item were already loaded. The corrected activation clears the previous native model, reconstructs dress state, applies the full camera preset immediately, and reasserts it during a bounded 0.25-second initialization window.

`NativeTransmog_SetPortraitPrototype(true)` reuses up to three XML-owned `DressUpModel` widgets for the first three eligible, unique Head entries. For each assigned widget independently it performs:

1. Hide and `ClearModel()` the previous native state, then call `GetItemInfo(entry)` to obtain the item link used by Blizzard's build-12340 dressing room. If unresolved, the model stays hidden, the icon remains visible, and `GET_ITEM_INFO_RECEIVED` retries the entire activation.
2. `SetUnit("player")`.
3. `Undress()`.
4. `TryOn(itemLink)` when the link is resolved.
5. Camera 0, facing/rotation 0, model scale `1.30`, and position `(0, -0.13, 0)`, reasserted briefly while the native model finishes loading. The X/Z offsets remain zero so the head stays centered horizontally and vertically; the Y value retains the verified camera-0 depth.

Disable, catalog rerender, category/page change, and Wardrobe close all hide and `ClearModel()` every initialized pool widget, cancel each widget's pending camera initialization, and remove every tile reference. The pool objects remain allocated for reuse. Re-enable and Wardrobe reopen therefore start each assignment from `SetUnit` rather than hidden native state. Item icons are never removed. The flag remains intentionally unpersisted across a UI reload.

Camera 0 plus `SetModelScale` and `SetPosition` is the only verified build-12340 route to a close crop. There is no field-of-view, custom-camera, or `SetPortraitZoom` API. The Judgement PTR capture showed that the former `1.80` scale overfilled the tile: upper geometry rendered beyond the nominal widget and the lower geometry was cropped. That observation also confirms that the 3-D result is not safely clipped to the `DressUpModel` frame boundary on this client. The corrected `1.30/-0.13` preset reduces projected geometry by about 28% while retaining centered X/Z offsets. This deliberately spends portrait size on internal camera-space margin; neither the frame nor a scroll-child parent is used as a clipping guarantee.

The repeatable preset should give the same head/shoulders framing on every activation, but a universal close crop is not guaranteed across race, sex, hairstyle, horns/ears, and helm geometry. Tauren horns, Troll ears, Night Elf ears, Draenei horns/crests, and unusually tall or wide helm geosets can exceed Human-like bounds. Build 12340 exposes neither model bounds nor a race-aware portrait camera, so further exceptions must be handled by a more conservative single shared scale, not per-race offsets, unless PTR evidence proves a deterministic race table is necessary. Unsupported modern camera APIs must not be added.

## Appearance isolation result

The verified build-12340 isolation sequence is `SetUnit("player"); Undress(); TryOn(itemLink)`. `Undress()` removes the dressable equipment copied by `SetUnit`; `TryOn` then adds that widget's resolved catalog head item. Every widget executes the full sequence and owns a separate 0.25-second camera deadline, so no dress or camera state is intentionally shared. There is still no success return or model-ready event, so all three known collected appearances require visual confirmation on PTR. If non-head equipped armor remains visibly present, build 12340 cannot provide stronger slot isolation with its exposed API and the prototype must remain icon-only.

## Loading, failure, compatibility, and performance risks

- Item data is asynchronous. `TryOn` has no success return and no model-ready event in this API. A successful item-info event proves cache resolution, not visible geometry.
- Invalid, missing, nondressable, or zero-display items can leave an undressed model. The icon fallback and tooltip remain authoritative presentation fallbacks.
- Reset order matters. Every reuse clears the native model and calls `SetUnit`, `Undress`, and `TryOn`; otherwise prior slot state can survive because dressing is last-write-wins per slot.
- Build 12340 provides no supported clipping API for arbitrary model children. The PTR overflow confirms that the nominal one-tile viewport does not contain out-of-bounds 3-D geometry. The corrected scale therefore uses safe internal camera margins; this does not establish that model widgets are safe in a scrolling 18-tile grid.
- Hide is not an item and is never sent to the model.
- Hair, ears, horns, weapon sheathing, robes, tabards, and some geosets can crop or occlude unexpectedly. Lighting is selectable but the stock camera light is retained in the prototype because there is no documented portable light preset across races.
- Three simultaneously animated player models multiply geometry, composited character textures, item models, animation updates, and draw calls relative to the verified single-model baseline. Activation also performs three clear/unit/dress operations and up to three camera reassertions per frame for 0.25 seconds. The 3.3.5 client offers no reliable Lua GPU accounting, per-widget memory metric, or readiness signal, so automated contracts cannot establish acceptable frame time, hitching, or resource use. The fixed pool bounds allocation and avoids enable/disable churn, but only PTR measurement can determine whether loading and steady-state cost are acceptable. Expansion beyond three is not approved.
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
2. Start build 12340 with Lua errors enabled. Interact with a registered Transmogrifier, equip a head item, select Head, and wait for a page containing at least three collected non-Hide appearances. The flag is deliberately false after `/reload`.
3. Capture the baseline: icons render, the main character preview rotates/resets, and Apply/Remove behavior is unchanged.
4. Record the icon/name of the first three unique non-Hide entries, then run `/run NativeTransmog_SetPortraitPrototype(true)`. Confirm exactly those three tiles contain stable close-ups in catalog order and that every helm matches its own recorded entry. No tile may duplicate another appearance.
5. Inspect all three shoulders/chests: no equipped dressable gear should remain. Base skin, hair, underwear, and race geosets are expected. Confirm the `1.30` scale, facing, centering, 84×111 placement, spacing, selection glow, and applied marker. No geometry may float elsewhere or overlap a neighboring tile.
6. Run `/run NativeTransmog_SetPortraitPrototype(false)` and confirm all three models disappear immediately while all original icons remain. Repeat the enable/disable pair two more times. The same three appearances, scale, facing, position, and crop must return on every enable, with no duplicate or stale geometry.
7. Leave the prototype enabled. Go to the next catalog page and back; choose another equipment category and return to Head; close and reopen the Wardrobe. Each transition must clear the old three and either show no portraits outside Head or reconstruct the current page's first three eligible entries. Test a page with one or two eligible entries and confirm only one or two models appear.
8. Rotate/reset the large character preview and confirm none of the three tile models rotate, dress, clear, or otherwise change. Select each portrait tile and confirm only the large preview changes as before. Recheck Apply, Remove, Hide, Reset Preview, pagination, equipment slots, Saved Sets, and the separate gold Collections window.
9. Test cached entries and, after clearing the client item cache in the normal PTR-safe manner, initially uncached entries. While unresolved, confirm each corresponding icon remains visible and no old model remains in that tile. After each `GET_ITEM_INFO_RECEIVED`, confirm the correct isolated portrait appears without a Lua error or disturbing the other two portraits.
10. With the prototype enabled, trigger an appearance-catalog update, close/reopen, and `/reload`. Confirm the update reassigns current ordered entries, close leaves no geometry behind, and reload returns to icon-only because the setting is not persisted.

### FPS, loading, and resource comparison

1. Use the same character, Head page, camera direction, quiet test location, window mode, resolution, UI scale, and graphics settings for every sample. Ensure the three test entries are cached before the steady-state comparison. Press `Ctrl+R` to show the client's FPS counter.
2. Run `/run NativeTransmog_SetPortraitPrototype(false)`, keep the Wardrobe open on that Head page for 30 seconds, then record the displayed FPS every five seconds for two minutes. Record the minimum and median of those 24 readings and the client process working set from the operating system's process monitor. This is the icon-only baseline.
3. Without moving or changing the page, run `/run NativeTransmog_SetPortraitPrototype(true)`. Note any visible activation hitch or delayed/incorrect model load. After 30 seconds, take the same 24 FPS readings and working-set measurement. This is the three-model sample.
4. Repeat the disabled/enabled comparison three times in alternating order. Report each run rather than only the best run. A stable drop, large minimum-FPS regression, repeated activation hitch, continuing memory growth, or visual corruption is a failure requiring investigation; this document intentionally sets no universal FPS threshold for different PTR hardware.
5. Leave all three models enabled for 10 minutes. Every minute, change page and return once, watching FPS, process working set, item/model loading, camera stability, appearance identity, overlap, and corruption. Disable at the end and confirm FPS trends toward the icon-only baseline and all geometry disappears.
6. Repeat the visual/cost check for male and female representatives of Human, Night Elf, Tauren, Gnome, Troll, and Draenei at UI scales 0.64, 0.8, and 1.0. Record crop, ears/horns/hair clipping, helm visibility, FPS summary, activation behavior, and working-set delta. Do not describe the pool as performant based only on automated tests.

## Recommendation gate

Do not expand beyond three tiles. Accept this experiment only if all three models remain stable across the race/sex/UI-scale matrix, cached and uncached data, repeated lifecycle changes, and the 10-minute open-window soak. Reject further expansion if crops require nondeterministic per-race tuning, models intermittently remain undressed, appearance identities cross between widgets, visual corruption occurs, or frame time/memory rises materially on supported PTR hardware.
