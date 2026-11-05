# Phase 5A stabilization PTR deployment and validation

This stabilization changes both the protected client FrameXML and the C++ world module. It has no SQL migration, configuration addition, protocol-version change, custom outfit, cost, or full-set application path.

## Exact deployment requirements

1. Record the current PTR core/module revisions, worldserver hash, active Content Manager build, EPF/MPQ hash, and Portalkeeper generation. Back up the prior module binary and active client build. Confirm the target is PTR and `mod-transmog` remains excluded from this isolated build.
2. Build and link `worldserver` from the reviewed module checkout against the PTR Playerbot/AzerothCore revision. Install the resulting server artifact through the normal PTR process. A module-only hot copy is insufficient because `NativeTransmogSetCatalog.cpp` and `NativeTransmogWardrobe.cpp` changed.
3. Keep protocol version 3 and the existing configuration. No database updater or manual SQL is required.
4. Build `content/mod-native-transmog.epf` twice with `python3 content/build_epf.py`, confirm identical SHA-256 values, and run `python3 content/build_epf.py --check`.
5. Put that EPF in the existing PTR Content Manager discovery location. Run `.content validate mod-native-transmog`, `.content build`, record the new STAGED build and hash, then `.content activate <new-build-number>`. Confirm `.content build list` reports that exact build ACTIVE/APPLIED with protected FrameXML parity.
6. Restart the PTR worldserver and publish the activated isolated client generation through the existing Portalkeeper flow. Do not install loose FrameXML, a standalone addon, or modify the cumulative TOC manually.
7. Launch the prepared build-12340 client with Lua errors enabled. A client restart is required so protected FrameXML is reloaded.

## Required PTR checks

- Open and close the NPC wardrobe repeatedly; switch between Appearances and Sets and confirm existing application, authorization, tooltips, overrides, and pagination are unchanged.
- Page forward/back through All, Incomplete, and Complete. Repeatedly select sets with different piece counts, including eight-piece Judgement Armor, and rapidly select another set before the first detail finishes.
- Close the wardrobe immediately after page and detail requests, reopen it, and confirm late replies neither raise Lua errors nor replace current rows.
- Confirm Judgement remains 8/8 for the known collected character, previews all eight pieces, and displays authoritative piece names even after clearing the client item cache.
- Confirm only the documented curated catalog appears for each class; verify a representative Tier 1/2, WotLK arena, Tier 9, and Tier 10 family, and confirm miscellaneous gameplay sets such as 881/882 are absent.
- Preserve client Lua logs, worldserver startup catalog count/source summary, screenshots, active build/hash, and the exact character/class used.

Rollback requires reactivating the recorded prior Content Manager build, restoring the prior compatible worldserver/module artifact, and restarting PTR. No database rollback is needed.
