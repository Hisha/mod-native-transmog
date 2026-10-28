# mod-native-transmog

`mod-native-transmog` is an MIT-licensed native AzerothCore module and client-content package for a retail-inspired transmogrification wardrobe on WoW 3.3.5a build 12340.

The current implementation is **Phase 1: implemented and awaiting PTR validation**. It proves the native client interface and preview workflow without an addon, database writes, equipment changes, custom opcodes, NPC registration, or changes to `azerothcore/mod-transmog`.

## Phase 1 capabilities

- Native AzerothCore module registration, configuration loading, and startup logging.
- Schema 3 EPF packaging through `mod-content-manager`.
- Additive protected-FrameXML registration after stock `DressUpFrame.xml`.
- Blizzard-styled movable wardrobe window with a player `DressUpModel`.
- Head, shoulders, chest, main-hand, and off-hand selectors.
- Scroll-frame appearance browser, stock item icons, selection highlights, and item tooltips.
- Click-to-preview with `DressUpModel:TryOn`; no inventory or persistent state is changed.
- Drag/button model rotation and reset to the player's currently equipped appearance.
- Temporary `/wardrobe` and `/nativetransmog` prototype commands.
- Deterministic, independently authored stock build-12340 catalog.

The two weapon compatibility settings are read and reported but deliberately do not enforce policy in Phase 1.

## Repository layout

```text
conf/                         AzerothCore configuration template
content/manifest.json         Schema 3 package declaration
content/build_epf.py          deterministic EPF builder/checker
content/client/...            native FrameXML XML and Lua
content/upstream/FrameXML.toc verified stock build-12340 composition input
docs/                         inspection record and PTR validation guide
src/                          module registration and config initialization
tests/                        package, UI-contract, and catalog tests
```

There is intentionally no `Interface/AddOns` content and no addon `.toc`.

## Server installation

1. Place or clone this repository as `modules/mod-native-transmog` in the Playerbot-based AzerothCore checkout.
2. Keep `mod-content-manager` installed and configured as it is for the target PTR.
3. Configure/build AzerothCore using the normal environment process. The module's `CMakeLists.txt` registers its C++ sources; AzerothCore's module discovery installs `conf/mod_native_transmog.conf.dist`.
4. Copy the generated configuration and retain the Phase 1 defaults unless testing module disablement:

   ```ini
   NativeTransmog.Enable = 1
   NativeTransmog.AllowTwoHandAppearanceOnOneHand = 0
   NativeTransmog.AllowOneHandAppearanceOnTwoHand = 0
   ```

5. Start the PTR worldserver and confirm the Phase 1 initialization log. No SQL migration is required or supplied.

This module does not require or modify AzerothCore core files.

## Client-content integration

Generate and verify the package:

```bash
python3 content/build_epf.py
python3 content/build_epf.py --check
```

The checked-in `content/mod-native-transmog.epf` is the distributable package. Install it through the existing `mod-content-manager` EPF discovery flow, then build the cumulative client MPQ using the normal content-manager command for the PTR.

The manifest contributes `NativeTransmogFrame.xml` and `NativeTransmogFrame.lua` as ordinary managed files. `clientFrameXml` composes the XML entry immediately after stock `DressUpFrame.xml`, automatically records the `protected-framexml` client requirement, and leaves the stock TOC owned by the content manager's composer. Collision detection, parity hashing, cumulative MPQ construction, activation, publication, and rollback are inherited from that existing pipeline.

The UI is hand-authored because Phase 1 needs behavior beyond a static FrameForge layout. Existing Schema 3 raw resource packaging already supports this; FrameForge and `mod-content-manager` need no changes.

For the isolated PTR realm, its Portalkeeper Schema 1 configuration must already declare:

```ini
[Client]
Requirements=protected-framexml
```

Portalkeeper's existing generation-2 transformation and ordinary patch delivery are used unchanged.

## Opening and testing the wardrobe

After launching the prepared PTR client, log in and enter either command in chat:

```text
/wardrobe
/nativetransmog
```

Select a slot, click an appearance, rotate the model by dragging it or using the arrow buttons, and click **Reset Preview** to return to the live character's equipped look. Escape or the close button closes the window. Reopening starts with a clean preview of the player's equipment.

## Automated checks

Run from the repository root:

```bash
python3 content/build_epf.py --check
python3 -m unittest tests/test_phase1.py
python3 tests/verify_catalog.py \
  /path/to/azerothcore-wotlk/data/sql/base/db_world/item_template.sql
```

The tests cover EPF repeatability and required members, Schema 3/FrameXML registration, load ordering, safe MPQ paths, the no-addon contract, XML parsing, UI behavior markers, catalog determinism, module registration, and configuration defaults. `mod-content-manager` already owns cumulative cross-package collision and backward-compatibility tests; this module does not duplicate that framework.

## Known limitations

- Manual Windows/PTR testing has not yet been performed; successful static/package tests do not prove in-game rendering.
- The client `DressUpModel` preview is local and non-authoritative. It makes no server request and never applies transmogrification.
- The stock 3.3.5a `TryOn` behavior normally accumulates compatible slots. Trying mutually exclusive weapon shapes or client-incompatible combinations may replace/clear another weapon preview; this must be recorded during PTR validation.
- The deterministic catalog is a test fixture, not a collection/unlock system and not filtered by player usability.
- No NPC opens the window in Phase 1. The slash command is a temporary native-FrameXML test entry point.
- No appearance persistence, server-side validation, saved outfits, filtering, database schema, or migration exists.
- The configuration options for one-hand/two-hand appearance compatibility are reserved only.

## Roadmap boundaries

- **Phase 2:** dedicated Transmogrifier NPC, creature-entry and spawn-GUID service registration, preserved existing NPC services, and server-authorized opening.
- **Phase 3:** collections, server-side transmogrification/validation, weapon compatibility policy, and a separately planned migration from existing `mod-transmog` data.
- **Phase 4:** saved outfits, advanced filtering, interface polish, and more equipment slots.
- **Future:** vehicle-passenger/mobile Transmogrifiers without assuming a fixed entry, spawn, or location.

Presentation remains separate from future NPC identification and gameplay authorization. The client will never be trusted to authorize or persist an appearance change.

## License

All implementation in this repository is independently authored and licensed under the [MIT License](LICENSE). No AGPL implementation code is copied or adapted.
