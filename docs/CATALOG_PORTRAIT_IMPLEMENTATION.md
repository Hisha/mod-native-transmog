# Automatic catalog portrait implementation

## Production behavior

The Wardrobe owns one `DressUpModel` named
`NativeTransmogCatalogPortraitModel`. It is an 84×111 child of the fixed browser
panel, separate from both the main Wardrobe character preview and the gold
Collections preview. It is created once by XML, moved to the selected tile, and
reused. No selection creates a frame.

All catalog tiles begin with their normal item icon. Clicking a collected Head
appearance copies that tile's current catalog record, selection index, and
source item entry into the active portrait transaction. The renderer resolves
an item link from that entry, clears the reusable model, runs
`SetUnit("player"); Undress(); TryOn(itemLink)`, applies camera 0 with scale
`1.30` and position `(0, -0.13, 0)`, and only then hides the selected icon. A
separate non-model overlay keeps the selection border above the native model.

`TryOn()` is not treated as a Boolean result: build 12340 has no verified
success return or model-ready event. The implementation only treats a resolved
item link whose embedded item ID matches the clicked source entry and an
error-free initialization call sequence as sufficient to show the model.
Because `SetUnit` can finish native equipment initialization after returning to
Lua, the renderer repeats `Undress(); TryOn(the same validated link)` during the
same generation-bound 0.25-second window used for camera stabilization. This
keeps the clicked helmet as the last writer instead of allowing the player's
equipped helmet to overwrite it. Final visible geometry remains a PTR
validation item.

For focused PTR diagnosis, `/nativetransmogportraitdebug` toggles chat logging
of the clicked appearance selection, source item entry, resolved link and link
item ID, item ID passed to `TryOn`, model reset, and the first delayed callback.
It is disabled by default and does not change the server protocol.

The single-model PTR symptom has a separate cause from the removed pool's
stale-record risk: the correct clicked link reaches the initial `TryOn`, but
the asynchronous completion of `SetUnit("player")` can subsequently copy the
player's equipped Judgement helmet over that slot. The old bounded callback
reasserted only camera state, so Judgement remained the last native equipment
writer. The callback now reasserts the already validated clicked item as well.

## Identity and stale-callback diagnosis

The former three-model experiment rendered the first three eligible entries
during catalog layout. Model identity was split across parallel mutable arrays
of pool models, recycled buttons, entries, and camera deadlines. Its item-cache
callback was keyed only by item ID and retried against whichever mutable button
was then stored at that pool index. It had no selection transaction and no
generation tied to page, slot, close/reopen, or rapid user selection. Thus an
asynchronous retry could not prove it still belonged to the catalog state that
scheduled it. Simultaneously initializing three native models also made the
observed duplicate Judgement geometry impossible to associate with one
authoritative click. The checked-in experiment did not contain a literal
global cached Judgement link; the defect was the pool's mutable identity and
callback lifetime model.

The production renderer instead has one active transaction. Every clear or
selection increments `catalogPortraitGeneration`. Item-cache and bounded camera
callbacks capture/read that generation and must also match all of the following
current state before acting: active generation, Head slot, selected appearance
selection and entry, exact appearance-record object, exact tile entry, visible
tile, open Wardrobe, and the one catalog model. A stale callback becomes a
no-op. Model state is cleared before every different item.

## Supported categories and fallback

Only **Head** is supported for 3D catalog portraits. It is the only category
with a successful build-12340 camera baseline established on PTR.

The following remain icon-only until a category-specific framing preset is
verified: Shoulders, Shirt, Chest, Waist, Legs, Feet, Wrists, Hands, Back,
Main Hand, Off Hand, Ranged, Tabard, and relic/ranged-slot appearances. No Head
camera settings are applied to them.

The normal icon remains visible when the selection is Hide, the category is
unsupported, item data is unresolved, the model is missing, initialization
raises an error, the tile is recycled/hidden, the page or slot changes, or the
Wardrobe closes. Cleanup restores the prior icon, hides and clears the model,
hides its overlay, cancels camera stabilization, and invalidates callbacks. The
XML-owned model remains allocated for reuse.

## Command-free PTR validation

1. Build and deploy `content/mod-native-transmog.epf` through the existing
   mod-content-manager EPF pipeline. Do not install a standalone addon.
2. Start client build 12340 with Lua errors visible. Interact with a registered
   Warpweaver and open the Wardrobe normally.
3. Select Head. Confirm every collected helm initially displays its item icon
   and no catalog portrait is present.
4. Click Judgement. Confirm its clicked tile automatically changes to an
   84×111 close portrait, the helm identity matches its icon/tooltip, the
   selection border remains visible, and the main character preview updates as
   before.
5. Click a visually different collected helmet. Confirm Judgement immediately
   returns to its icon and the same tile portrait moves to the new tile with
   the new helmet. Repeat rapidly across at least five helmets, including
   initially uncached item data, and verify the final click always wins.
6. Change pages while a portrait is visible, then return. Change from Head to
   every other equipment category and back. Confirm transitions clear the
   portrait and that unsupported categories remain icon-only without blanks.
7. Select Hide Appearance. Confirm Hide behavior and the main preview remain
   correct and no catalog model is shown.
8. Exercise Reset Preview, Apply Appearance, Remove Appearance, Saved Sets,
   pagination, and equipment-slot changes. Confirm the main preview and server
   operations are unchanged.
9. Open the gold Collections window and verify its previews and navigation are
   unchanged.
10. Close the Wardrobe with a portrait visible and confirm no floating geometry
    remains. Reopen through the Warpweaver: all tiles must start icon-only and a
    new Head selection must render automatically, with no Lua commands or
    toggles.

Test at least two races with substantially different head geometry and both
sexes. Because build 12340 does not reliably clip model geometry, reject the
feature if the conservative Head framing overlaps adjacent tiles or obscures
the selection indicator. Automated tests cannot replace this visual check.
