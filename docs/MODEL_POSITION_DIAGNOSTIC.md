# Three-view model-position diagnostic

## Scope and result status

This is a temporary, command-only PTR experiment for WoW 3.3.5a build 12340.
It does not change the Wardrobe, Collections, Saved Sets, server module, or
protocol. Automated checks establish isolation, call order, timing, cleanup,
and packaging; they **cannot establish that the rendered pixels move**. Model
repositioning remains unproven until the three live client views are captured
and compared.

## Implementation

The diagnostic uses three independent XML-declared `DressUpModel` widgets,
each `220x300`, inside a hidden `738x370` top-level frame. They have the same
dark tooltip background and remain visible side-by-side after the one-second
measurement interval. The labels are Negative Z, Default Z, and Positive Z.

The report's `(0, -0.13, Z)` baseline is used instead of the objective's
initial `(0, 0, Z)` table. `-0.13` is the already verified camera-0 depth used
by the accepted Head portrait. Holding it fixed isolates Z while avoiding a
second unverified change. Requested Z values remain the deliberately extreme
`-2`, `0`, and `+2`; they are diagnostic values, not production presets.

All three widgets receive the same item link and this initial sequence. Each
step is run across all three widgets before the next step begins, preventing
one view from receiving an end-to-end native-loading head start:

1. `Hide()` and `ClearModel()`.
2. Seed only that view's requested `SetPosition(0, -0.13, Z)` so the effect of
   each following initialization call can be read back.
3. `SetUnit("player")`, then log `GetPosition()`.
4. `Undress()`, then log `GetPosition()`.
5. `TryOn(the same item link)`, then log `GetPosition()`.
6. `SetCamera(0)`, `SetFacing(0)`, `SetModelScale(1.30)`, and finally reapply
   `SetPosition(0, -0.13, Z)`.
7. `Show()` and immediately log `GetPosition()` and `GetModelScale()`.

The probe deliberately does not call `SetRotation`. At target times `0.05`,
`0.25`, `0.50`, and `1.00` seconds, a bounded frame `OnUpdate` first records
the position before any Lua reapplication. It then runs the identical
`Undress(); TryOn(itemLink)` equipment sequence, reapplies the common camera,
facing, and scale followed by the per-view position, and records the position
again. Each line records the target time, actual elapsed callback time,
requested position, measured position, model scale, and whether Lua model
initialization or equipment application occurred. This includes the required
immediate, 0.25, 0.5, and 1 second samples; 0.05 is the report's additional
early-reset sample. All sampling stops after 1 second.

The slash command accepts an optional cached item ID or item link. With no
argument it uses the first equipped item link it finds, so normal use requires
no configuration. The frame will not open without a resolved link because
omitting `TryOn` would make that run incomparable.

## Client API limitations

- Build 12340 has no model-ready event. `OnUpdate` can sample only on the first
  rendered frame at or after a target threshold; the log therefore reports
  actual elapsed time as well as the target.
- `TryOn` has no success result. A cached/equipped link proves only that the
  same request was made to all three widgets, not that geometry appeared.
- `GetPosition()` can report retained values without proving that camera 0
  changes composition. Visual comparison is decisive.
- The client exposes no model bounds, equipment bounds, custom camera target,
  camera distance, field of view, portrait zoom, or reliable child clipping.
- Native initialization may occur asynchronously. The pre-reapply readings
  are retained specifically to expose a reset rather than hide it.
- Timing and pixels cannot be validated by the Lua/XML source test suite.

## Files changed

- `content/client/Interface/FrameXML/NativeTransmogModelPositionProbe.xml` —
  isolated window and three `DressUpModel` widgets.
- `content/client/Interface/FrameXML/NativeTransmogModelPositionProbe.lua` —
  command, initialization, bounded measurements, logging, and cleanup.
- `content/manifest.json` — packages and loads the protected diagnostic after
  the existing Native Transmog FrameXML.
- `content/mod-native-transmog.epf` — regenerated deterministic client package.
- `tests/test_model_position_diagnostic.py` — structural, Lua 5.1, runtime
  lifecycle, timing, isolation, cleanup, and Head-regression contracts.
- `tests/test_phase1.py` — expected protected FrameXML load order updated.
- `docs/MODEL_POSITION_DIAGNOSTIC.md` — this implementation and PTR procedure.
- `docs/TEST_RESULTS.md` — automated suite and deterministic EPF results.

The existing `NativeTransmogFrame.xml` and `NativeTransmogFrame.lua` are
unchanged.

## PTR publication and acceptance

These steps target the isolated PTR only. No AzerothCore core/module rebuild,
SQL, configuration change, or server restart is introduced by this probe.

1. Build and verify the reviewed package:

   ```bash
   python3 content/build_epf.py
   sha256sum content/mod-native-transmog.epf
   python3 content/build_epf.py
   sha256sum content/mod-native-transmog.epf
   python3 content/build_epf.py --check
   ```

   The two hashes must match. Copy `content/mod-native-transmog.epf` into the
   existing PTR Content Manager EPF discovery directory.

2. In the PTR worldserver console or as an authorized Content Manager GM, run:

   ```text
   .content scan
   .content validate mod-native-transmog
   .content build
   .content build list
   .content activate <new-staged-build-number>
   .content build list
   ```

   Record the new build number and hash. Confirm that exact build is
   `ACTIVE/APPLIED` with protected-FrameXML parity. Publish that activated
   generation through the realm's existing Portalkeeper flow. Do not install
   loose FrameXML, create an addon, or edit the cumulative TOC. Fully exit and
   restart the build-12340 client so protected FrameXML reloads; no additional
   worldserver restart is required beyond the realm's normal patch process.

3. Log in on the test character, enable the client chat log, and open the
   diagnostic with one of these exact commands:

   ```text
   /chatlog
   /nativetransmogmodeltest
   /nativetransmogmodeltest 16955
   ```

   The no-argument form uses the first equipped item. Use the item-ID form
   only after that item is cached. A shift-clicked item link is also accepted.
   The short alias is `/ntmodelprobe`.

4. Wait until chat prints `sampling complete`. Keep all three views visible
   and take one unedited screenshot using the client's Screenshot key. The
   capture must show the Negative Z, Default Z, and Positive Z viewports at
   once. Record whether the character visibly shifts relative to each fixed
   viewport; identical views are a valid result. Do not infer visible movement
   from getters alone.

5. Collect every `[NT model probe]` line from the in-game chat or the client's
   `Logs/WoWChatLog.txt`. Preserve the opening item link plus every requested
   and measured tuple at immediate/after-`SetUnit`/after-`Undress`/after-`TryOn`
   and before/after the `0.05`, `0.25`, `0.50`, and `1.00` reapplications.
   Preserve Lua errors, if any, alongside the screenshot and active EPF hash.

6. Close and clean up with the same toggle command (or the window close
   button):

   ```text
   /nativetransmogmodeltest
   ```

   Confirm the frame disappears and no later probe messages occur. Reopen it
   once to confirm all three views start from a fresh `ClearModel()` sequence,
   then close it again.

7. Visit an authorized Warpweaver and exercise the normal Wardrobe. Confirm
   the accepted purple Head portrait, large character preview, appearance
   selection, delayed `TryOn` behavior, apply/remove/hide, Saved Sets,
   Collections/Appearances, pagination, and weapon-slot navigation still work.
   Close the Wardrobe and confirm no probe window opens and no probe log lines
   appear. The probe command is never required for normal functionality.

## Automated verification

Run the full Lua/XML/source suite with:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 content/build_epf.py --check
```

Final test count, EPF SHA-256, and the two-build determinism result are recorded
in `docs/TEST_RESULTS.md`. They validate the experiment's mechanics only, not
live model repositioning.
