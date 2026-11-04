# Phase 3D architecture

Phase 3D connects the protected native wardrobe to the existing collection and application services. It
does not replace the Phase 3C appearance engine.

## Request flow

An NPC interaction creates the Phase 2 server session and sends protocol-v2 `OPEN`. Protected FrameXML
requests a slot page over the supported addon self-whisper transport. `WardrobeService` derives the player
from the core hook, validates the token/live NPC, resolves the equipped item, reads a bounded collection
slice, and selects compatible canonical entries through `ApplicationService::ValidateForTarget`, which
delegates to the Phase 3C validator.

A server snapshot binds page selections to the token, slot, item GUID, request ID, expiry, and nonce.
Apply/Remove revalidate it and call the existing `ApplicationService::Apply`/`Remove` with NPC-session
authorization. Phase 3C repeats live authorization, ownership, source, and compatibility validation before
persistence and visible refresh.

## Catalog and canonical sources

The identity remains `(display ID, class, subclass, inventory type)`. At startup the wardrobe maps each
eligible identity to sorted loaded item-template entries. It chooses the lowest entry that passes the shared
validator for the current player/target, so physical source retention is unnecessary and every legitimate
representative is considered.

SQL narrows by target class, subclass/family, and inventory family. A click scans at most eight configured
pages in chunks of 64, returns at most 36 entries, and follows the collection table's identity ordering. The
client retains raw cursor history for Previous. No detailed catalog loads at player login.

## UI and failures

Equipped item, applied override, and preview selection are separate. Preview uses only `DressUpModel`;
Apply/Remove wait for `RESULT`. Reset reconstructs the model from current visible state, and Close sends no
mutation. Timeouts affect presentation only.

Token mismatch, session/snapshot expiry, replay, equipment replacement, malformed input, request flooding,
missing equipment, collection changes, and Phase 3C validation failures preserve the real item and existing
override and return bounded feedback.

See `PHASE3D_TRANSPORT_DESIGN.md` for wire/security details and `PHASE3D_PTR_VALIDATION.md` for the
unexecuted manual milestone.
