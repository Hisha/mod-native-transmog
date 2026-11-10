# Equipment-focused 3-D rendering investigation (WoW 3.3.5a build 12340)

Investigation date: 2026-11-10.

## Executive conclusion

Build 12340 exposes enough of the old `Model` transform API to justify one
more isolated positioning experiment, but it does **not** expose the modern
camera controls that would make arbitrary body-region framing deterministic.
The removed non-Head presets did not prove that `SetPosition` is unusable. They
proved only that one uninstrumented set of offsets, scales, and a 0.25-second
stabilization window continued to produce a Head view on PTR.

The most promising next step is an EPF-delivered diagnostic containing three
large, independent `DressUpModel` frames with deliberately extreme negative,
zero, and positive Z positions. It must print `GetPosition()` immediately and
after native initialization. This separates three possibilities that the old
test conflated: an overwritten transform, a retained transform that does not
pan camera 0, and a transform whose direction or magnitude was simply wrong.

Until that visual test succeeds, production should remain unchanged: the
already working Head portrait stays as it is and every other category stays on
its item icon. Automated tests cannot establish that the intended pixels were
rendered.

## 1. Verified build-12340 API surface

The strongest version-specific evidence is the method registration inventory
recovered from a 3.3.5a executable. It lists methods registered by the client,
not names copied from current API documentation. `DressUpModel` inherits
`PlayerModel`, which inherits `Model`, which in turn inherits ordinary frame
behavior.

| Owner | Methods registered in build 12340 that matter here |
|---|---|
| `DressUpModel` | `Undress`, `Dress`, `TryOn` |
| `PlayerModel` | `SetUnit`, `SetCreature`, `RefreshUnit`, `SetRotation` |
| `Model` | `SetModel`, `GetModel`, `ClearModel`, `SetPosition`, `GetPosition`, `SetFacing`, `GetFacing`, `SetModelScale`, `GetModelScale`, `SetSequence`, `SetSequenceTime`, `AdvanceTime`, `SetCamera`, `SetLight`, `GetLight`, `ReplaceIconTexture`, fog controls, and `SetGlow` |

The complete `Model` registration table contains 24 methods. In particular,
the following calls are verified as present:

```lua
model:SetPosition(x, y, z)
local x, y, z = model:GetPosition()
model:SetModelScale(scale)
local scale = model:GetModelScale()
model:SetFacing(radians)
local facing = model:GetFacing()
model:SetCamera(index)
model:SetModel(path)
local path = model:GetModel()
```

The registration inventory proves existence, but not the projection semantics
of each coordinate, valid camera indices for every asset, or when asynchronous
unit construction is complete. Historical widget documentation describes
`SetPosition` as positioning the mesh in the model frame coordinate system;
old portrait code commonly uses Z to change the vertical crop. Those semantic
claims are useful experiment guidance, not build-12340 proof for this exact
`DressUpModel`/camera combination.

The stock 3.3.5a `DressUpFrame.lua` is narrower evidence of the supported
dressing path: it calls `DressUpModel:SetUnit("player")`, followed by
`DressUpModel:TryOn(link)`. The stock XML declares a `316x331`
`DressUpModel`. It does not implement body-region cameras.

### APIs that must not be imported from newer clients

The build-12340 registration tables do **not** expose any of the following:

- `PlayerModel:SetPortraitZoom`
- `PlayerModel:SetCamDistanceScale`
- `PlayerModel:SetDisplayInfo` or `PlayerModel:SetItem`
- `DressUpModel:UndressSlot`
- `SetCameraDistance`, `SetCameraPosition`, `SetCameraTarget`,
  `SetCameraFacing`, `SetCustomCamera`, or `RefreshCamera`
- `SetViewTranslation`, `SetViewInsets`, `SetTransform`, or model-bounds
  queries
- a model-ready query/event or a success result from `TryOn`

Current `SimpleModelAPI` documentation includes many of those calls, but it is
not evidence for 3.3.5a. `UndressSlot` is guarded elsewhere in this project for
compatibility, but its presence must not be assumed for an unmodified build
12340 client.

Sources:

- [Build-12340 executable registration inventory](https://raw.githubusercontent.com/brues-code/ClassicAPI/master/docs/BlizzardScriptAPI_3.3.5.md)
- [Extracted 3.3.5a DressUpFrame.lua](https://raw.githubusercontent.com/wowgaming/3.3.5-interface-files/main/DressUpFrame.lua)
- [Extracted 3.3.5a DressUpFrame.xml](https://raw.githubusercontent.com/wowgaming/3.3.5-interface-files/main/DressUpFrame.xml)
- [Modern generated SimpleModel API, included only as the do-not-import comparison](https://github.com/Gethe/wow-ui-source/blob/live/Interface/AddOns/Blizzard_APIDocumentationGenerated/SimpleModelAPIDocumentation.lua)

## 2. Trace of the current portrait renderer and the removed profiles

The current selected-tile renderer owns one XML-created `84x111`
`DressUpModel`. For a resolved item link it performs this sequence:

1. Hide and `ClearModel()` the old model.
2. Anchor the model over the selected tile, outside the scroll child.
3. Call `SetUnit("player")`.
4. Call `Undress()` and `TryOn(itemLink)`.
5. Apply camera, facing/rotation, scale, and position.
6. Show the frame.
7. During a bounded 0.25-second `OnUpdate` window, repeat step 4 and then
   step 5 so the selected item and transform remain the last writers.

The delayed `TryOn()` correction is therefore preserved and is correctly
ordered before the transform on every pass.

Commit `b17a0fe` extended the Head table with these non-Head presets; commit
`b36f6ef` removed them after PTR continued showing the head:

| Region group | Removed scale | Removed position characteristics |
|---|---:|---|
| Shoulders/chest/tabard | `1.05` | Y `-0.13`, Z `0.18` or `0.55` |
| Waist/legs/feet | `0.85`–`1.05` | Y `-0.13`, Z `1.05`–`2.15` |
| Wrists/hands | `0.78`–`0.82` | Y `-0.13`, Z `0.58`–`0.68` |
| Back | `0.90` | facing/rotation pi, Z `0.62` |
| Weapons | `0.68`–`0.72` | small X/facing offsets, Z `0.72`–`0.78` |

### Findings against the requested failure questions

1. **Were the coordinates valid?** Yes in the Lua/API sense. Every value was
   a finite number, and the active slot selected the expected table entry.
   There was no `GetPosition()` logging, so retention by the native widget was
   not verified.
2. **Were the values appropriate?** Not established. The profiles assumed Z
   was the useful vertical-pan axis and selected only positive offsets. They
   also reduced scale below the working Head value (`1.30`). Because scale is
   a mesh transform rather than a crop rectangle, smaller values tend toward
   showing more character, not a close equipment study. No negative/zero/
   positive axis comparison was performed.
3. **Do `SetUnit`, `Undress`, or `TryOn` reset position?** `SetUnit` can finish
   native initialization after returning and has already been observed to
   restore native model/camera state. The available API documentation does not
   define whether `Undress` or `TryOn` rebuilds transform state. In this code,
   all three occur before each transform reapplication, so a synchronous reset
   by them cannot explain the final state during the stabilization window.
4. **Can delayed initialization overwrite the request?** Yes. That is why the
   working Head path has stabilization. The 0.25-second limit is a pragmatic
   value, not a readiness guarantee; a later native reset remains possible,
   especially on an uncached item.
5. **Where does scaling occur?** The API exposes no selectable pivot. Treat
   scale as occurring around the model/character origin, not around the chosen
   equipment. Consequently scale and position must be tuned together, and
   race stature changes the apparent result.
6. **Does the frame clip?** PTR evidence from the earlier Head prototype showed
   geometry outside the nominal model rectangle. Build 12340 has no verified
   child-clipping control suitable for this use. The tile boundary cannot be
   used as a safety crop.
7. **Do dimensions matter?** Yes. The stock dressing room uses `316x331`; the
   portrait is `84x111`. The small, narrow viewport magnifies projection,
   overflow, and aspect-ratio differences. It does not explain a retained
   `GetPosition`, but it makes an otherwise valid crop unsafe for a tile.

Additional issue: the removed path set both inherited `SetFacing` and
`PlayerModel:SetRotation` to the same value. Their exact interaction is not
documented for 12340 and was not isolated. A framing experiment should change
only one transform dimension at a time.

### Why the previous attempt failed

The defensible diagnosis is **insufficiently isolated transform testing**, not
"build 12340 cannot pan a player model." The experiment combined guessed
offset direction and magnitude, smaller scales, facing, an extremely small
viewport, repeated dressing, and a fixed stabilization deadline. It did not
read the transform back or compare visibly extreme values side by side. Thus
it could not distinguish a wrong profile from a native overwrite or a camera-0
limitation.

## 3. Feasibility of equipment-region framing on a character

Character-region framing is conditionally feasible if the proposed PTR probe
shows that `SetPosition` visibly changes camera-0 composition after dressing.
The client has the minimum controls needed for a crop: model translation,
uniform scale, facing, and a predefined camera. It lacks the controls needed
for a guaranteed crop: camera target/distance, model bounds, equipment bounds,
and a readiness notification.

A small reusable profile set is more realistic than per-item tuning:

1. head;
2. upper torso/shoulders;
3. forearms/hands;
4. waist;
5. legs/feet;
6. rear torso/cloak.

Each profile would contain camera index, one rotation mechanism, scale, and
position. It would still need a modest race/sex adjustment table or a
conservative common crop. Per-item exceptions should be avoided because the
client exposes no bounds and exceptional geometry would make such a table
large, brittle, and impossible to validate automatically.

Practical limitations by region:

- Shoulders and torso are favorable because they are central and visible in
  the idle pose.
- Wrists and gloves are difficult: the hands sit off-center, can overlap the
  torso, and bracers are often texture/geoset changes rather than independent
  objects.
- Waist, legs, and feet should be translatable in principle, but race height,
  hooves, robes, and skirt geosets change both target height and occlusion.
- A cloak requires a rear view. Use either `SetFacing(pi)` or
  `SetRotation(pi)` after independently determining which is stable; do not
  set both without proving their relationship.
- Weapons on a character are poor tile subjects because sheath location,
  hand, stance, weapon length, and dual-wield state vary. Direct geometry is a
  better research path for them.

No region should ship merely because `GetPosition()` reports a changed value.
The visible body region and the equipment's prominence must be confirmed on
PTR across representative races, sexes, robes, and unusually large geometry.

## 4. Standalone item-model access

Build 12340 can load a known mesh path into a plain `Model` using
`SetModel(path)`. It cannot accept an item ID or ItemDisplayInfo ID in that
call, and it exposes no `SetItem`/`SetDisplayInfo` bridge.

For build 3.3.5.12340, `ItemDisplayInfo.dbc` contains two `ModelName` fields,
two `ModelTexture` fields, two inventory-icon fields, three geoset groups, two
helmet-visibility records, eight component-texture names, `ItemVisual`, and
particle-color information. This explains why `TryOn(itemLink)` can assemble
an item, but the Lua API does not expose those DBC columns. A direct renderer
would need a generated display-ID-to-asset mapping delivered through the
existing EPF content, or an equivalent mapping sent by the existing module
protocol in a separately approved change. Neither exists today.

[The build-specific ItemDisplayInfo definition](https://github.com/wowdev/WoWDBDefs/blob/master/definitions/ItemDisplayInfo.dbd)
is the authoritative structural reference for this distinction.

Feasibility by asset type:

| Asset | Standalone prospect | Blocking details |
|---|---|---|
| Weapons | Promising research target | Usually have an M2 and texture, but Lua cannot derive their paths from item ID. A direct M2 may lack a useful embedded camera; 12340 has no custom-camera API. Item visuals/glows are separate. |
| Shields | Promising research target | Same path/texture/camera issues as weapons; handed orientation needs tuning. |
| Shoulders | Technically possible but incomplete as one asset | ItemDisplayInfo can name left/right component models. They normally rely on character shoulder attachment transforms; two raw models will not automatically form an equipped pair. |
| Helmets | Poor replacement for the current character path | Model resolution and visibility depend on race/sex and helmet geoset data. A raw helmet lacks the head attachment, hair/ear/horn hiding, and the character context that makes it recognizable. |
| Chest, wrists, gloves, belt, legs, boots, cloak, shirt, tabard | Generally not standalone | Much of this appearance is composited character texture and character geoset selection. Do not assume an independent mesh. |

`ReplaceIconTexture` is registered, but its name and existence do not prove
that it performs all ItemDisplayInfo material substitutions. Direct weapon or
shield rendering therefore needs a separate path-plus-texture probe with a
known DBC row. It must also test whether the asset has a usable camera 0.

## 5. Recommended strategy by equipment category

| Category | Recommendation after investigation |
|---|---|
| Head | Keep the current verified `DressUpModel` portrait unchanged. |
| Shoulders | First test the upper-torso character profile. Investigate two-component direct models only as a later fallback. |
| Chest, shirt, tabard | Character upper-torso profile; icon fallback if translation is not deterministic. |
| Wrists, hands | Character forearm/hands profile only if the idle pose keeps the item prominent across races; otherwise retain icons. |
| Waist | Character waist profile; validate robes and large belts. |
| Legs | Character lower-body profile; validate robe/skirt occlusion. |
| Feet | Character feet profile; validate hooves and robe occlusion. |
| Back | Rear-facing character torso profile. Cloaks are not assumed to be standalone. |
| Main hand, off hand, ranged | Prefer a future direct-asset experiment for weapons; character framing is a fallback, not the preferred tile presentation. |
| Shields | Prefer a future direct-asset experiment. |
| Helmet standalone | Do not replace the working character-based Head portrait. |

## 6. Browsing strategies and cost

### One live 3-D portrait for the selected appearance

This is the recommended production shape if a region profile passes PTR. It
reuses the current bounded lifecycle, limits asynchronous item/model churn,
and keeps all unselected appearances as cheap, stable icons. Selection changes
can still hitch while item data and composite character textures load, but the
cost is bounded to one live character widget.

### Multiple simultaneous model frames

This is technically possible—the old Head prototype allocated three
independent widgets—but it multiplies animated character evaluation, composite
texture work, item loading, draw calls, and stabilization callbacks. It also
reintroduces unreliable clipping inside a dense scrolling grid. Build 12340
provides no Lua GPU/memory metric or readiness signal, so acceptable cost can
only be measured on the target client. Expanding to a page of live models is
not recommended.

### Static portraits generated from 3-D models

The 3.3.5a Lua surface has no model-to-texture capture or pixel-readback API.
Static portraits therefore require an offline capture/render pipeline, a
race/sex/profile matrix for character-bound armor, asset storage, mapping, and
EPF distribution. They browse efficiently at runtime but have the highest
build complexity and invalidation/storage cost. They are especially
combinatorial for texture-based armor. No such pipeline should be started from
this investigation.

## 7. Minimal isolated PTR experiment

Implement this only as a temporary, separately approved experiment. It must be
delivered through mod-content-manager's existing EPF injection mechanism, not
as an addon, and must not call or parent itself to any Wardrobe frame.

### Structure

- Add a protected FrameXML diagnostic file, for example
  `NativeTransmogModelPositionProbe.xml/.lua`, loaded by the existing EPF
  manifest after stock `DressUpFrame.xml`.
- Declare one hidden top-level control frame with three large (`220x300` or
  larger) side-by-side `DressUpModel` children. Do not use the Wardrobe's
  selected portrait, model accessor, scroll child, state, or callbacks.
- Open/close it only through a probe-specific slash command such as
  `/ntmodelprobe`. Closing it must hide and `ClearModel()` all three widgets.
- Accept a typed item ID/link locally. It must not send an addon message or
  alter selection, application, collections, sets, acquisition, or protocol.

### First decisive test

For all three frames, run the identical sequence:

```lua
model:ClearModel()
model:SetUnit("player")
model:Undress()
model:TryOn(itemLink)
model:SetCamera(0)
model:SetFacing(0)       -- do not also call SetRotation in this test
model:SetModelScale(1.30)
```

Then assign deliberately separated positions:

```lua
left:SetPosition(0, -0.13, -2.0)
middle:SetPosition(0, -0.13, 0.0)
right:SetPosition(0, -0.13, 2.0)
```

Label each viewport with the requested values. Reapply dressing first and the
same transform second at 0.00, 0.05, 0.25, 0.50, and 1.00 seconds. At every
step, print each widget's `GetPosition()` and `GetModelScale()` to chat. Stop
all callbacks after the 1.00-second sample. This longer diagnostic schedule
does not change the production Head portrait's working 0.25-second correction.

The three Z values are intentionally not candidate production presets. They
are a falsifiable axis test. Add buttons for an X-axis trio
`(-1.5, 0, +1.5)` with fixed Y/Z and a Y-axis trio
`(-2.0, -0.13, +2.0)` with fixed X/Z only after the Z test. Change one axis at
a time.

### Interpretation

| Observation | Conclusion |
|---|---|
| The three body regions visibly differ and getters retain the requested values | Position-based profiles are viable; tune large diagnostic viewports first, then test the `84x111` tile separately. |
| Views initially differ, then converge; getters also revert | Native initialization overwrote the transform; determine the latest reset time and retain post-dress reapplication. |
| Getters differ but all three views remain the same | Camera 0 is following model space or otherwise ignores translation for composition; stop pursuing `SetPosition` body-region profiles. |
| Getters and views never differ | The transform is rejected/reset in this widget path; record Lua errors and exact timestamps. |
| Large viewports work but `84x111` does not | The blocker is viewport/aspect/clipping, not positioning. Keep icons or redesign only under separate layout approval. |

After the axis test, validate one upper-torso, one hands, one feet, and one rear
profile on at least a short and a tall race, both sexes, a robe, and oversized
shoulder/helm geometry. A screenshot and human observation are required for
each claimed success. Source tests may verify isolation and call order, but
must not be reported as visual validation.

## 8. Limitations and unresolved questions

- Exact `SetPosition` axis direction, units, pivot, and interaction with camera
  0 remain unverified on the target client.
- It is unknown whether the final native reset can occur after 0.25 seconds or
  whether uncached `TryOn` changes that timing.
- The interaction between `SetFacing` and `SetRotation` needs a one-variable
  PTR test.
- No model/equipment bounds are queryable, so universal race/item-safe crops
  cannot be computed.
- Model widgets are not proven to clip to their frames on this client.
- Direct item M2s may not contain a useful embedded camera, and 12340 cannot
  define a custom one through the registered Lua API.
- The direct asset path/material conventions must be verified against actual
  client MPQ/DBC data for known weapons, shields, shoulders, and helmets.
- No runtime static-image capture facility has been identified.
- Performance of even a small multi-model pool requires target-client frame
  time observation; source tests cannot answer it.

These unresolved points are precisely what the isolated probe is designed to
answer without changing the working Wardrobe.
