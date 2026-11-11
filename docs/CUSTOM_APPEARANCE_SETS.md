# Player-created custom appearance sets

## Architecture

Custom sets remain entirely owned by `mod-native-transmog`. Content Manager continues to own the Collections host,
navigation, chrome, and EPF deployment. The module adds a `Predefined` / `My Custom Sets` switch inside the existing
Appearances → Sets page and reuses its list, item buttons, piece strip, and `DressUpModel`. Predefined catalog ordering,
progress, class filtering, search, and totals remain on their original `SetCatalog` path.

The saved identity is the existing canonical `AppearanceKey`: ItemDisplayInfo ID, item class, item subclass, and
inventory type. Representative item entries are resolved from currently loaded templates for preview and application;
they are not durable set data.

## Character database schema

Apply `data/sql/db-characters/updates/2026_11_08_00_native_transmog_custom_set.sql` to the character database. New
installs receive the equivalent `base/003_native_transmog_custom_set.sql` schema.

- `native_transmog_custom_set`: auto-increment set ID, character GUID, case-insensitive per-character unique name,
  and creation/update timestamps.
- `native_transmog_custom_set_piece`: one row per specified equipment slot, appearance/hidden state, and canonical
  appearance identity. Its `(set_id, equipment_slot)` primary key prevents duplicate slots and its foreign key cascades
  only when the owning set is deleted.

The migration does not change or duplicate `native_transmog_collection`. A rollback may drop the piece table first and
then the set table. That rollback permanently removes saved custom sets but does not affect collected appearances or
item-instance overrides; back up both custom-set tables before rollback.

## Creation, editing, and preview

`My Custom Sets` provides New Set, Edit, and Delete. Editing uses a bounded server-side draft. The client requests the
existing Items browser in Collected mode for selection, then submits only the chosen representative entry and slot.
The server resolves it back to a canonical key and verifies collection ownership and structural slot compatibility.
The picker keeps Back to Set, Clear Slot, and Hide Appearance visible even when its category has no results. Clear is
server-acknowledged and removes the row so the slot becomes unspecified. Hide availability comes from the server's
current per-slot application policy (including the weapon-hide setting) and is stored as a distinct hidden state rather
than an appearance. Right-click clear and Shift-click hide remain shortcuts. Save is the only operation that writes the
draft. Cancel or closing Collections discards it.

Custom preview starts with the player's current model and applies only specified pieces, so unspecified slots remain as
they are. Predefined preview continues to undress the model and dress the complete predefined set. Neither path writes
equipment or item overrides.

## NPC application and security

The existing NPC wardrobe has a Saved Custom Sets selector and an **Apply Outfit** button. Application remains
deliberately unavailable from Collections. Selecting a set only loads its read-only preview; it never applies it. The
button becomes available only after the selected preview finishes without eligibility failures, and it is disabled
while a request is pending.

One `CUSTOMAPPLYOUTFIT` request carries the authenticated NPC-session token, request ID, and saved-set ID. The server
loads the set by both set ID and authenticated character GUID, resolves every canonical appearance, rechecks collection
ownership, validates every specified target with `CompatibilityValidator`, and rejects the entire operation before any
write if a selection fails. Successful application atomically writes the applicable item-instance overrides in one
character-database transaction before updating the cache and visible equipment. Explicit hide on an equipped item
writes a hidden override; explicit hide on an already-empty slot succeeds as an already-satisfied no-op because there
is no item instance to key an override to. Unspecified slots are untouched, and no equipped item is replaced or
modified.

Requests are protocol-versioned, length-bounded, rate-limited, paged, and numeric except for the final bounded name
field. Names are trimmed and validated server-side, escaped before SQL use, limited to 48 UTF-8 bytes by default, and
unique per character. The default maximum is 20 sets; `NativeTransmog.CustomSets.MaximumPerCharacter` is clamped to
1–100. Set ownership, appearance ownership, slot validity, hide policy, compatibility, and NPC authorization never rely
on client claims.

Protocol version 5 routes `CUSTOMPREVIEWINFO`, `CUSTOMPREVIEWPIECE`, and `CUSTOMPREVIEWEND` through the protected
self-whisper response allowlist. `CUSTOMPREVIEWPIECE` now appends the server eligibility result after the representative
entry. FrameXML restores every `ok` piece by wire-slot ID, reports each unavailable piece with its slot and reason, and
clears both pending and saved-load state on completion, explicit failure, or timeout. This is an additive version-5
response field; stored custom-set rows and request shapes are unchanged.

Native Transmog currently has no price or charging subsystem for ordinary single-slot applications. Custom-set
application therefore preserves the existing free policy: there is no insufficient-funds branch and no opportunity for
double charging. Add a shared application pricing service before introducing prices for either single-slot or batch
application.

## Deployment

1. Back up the character database tables named above if they already exist.
2. Apply `data/sql/db-characters/updates/2026_11_08_00_native_transmog_custom_set.sql` to the character database. Do not
   apply it to the world or auth database.
3. Merge the three `NativeTransmog.CustomSets.*` settings from `conf/mod_native_transmog.conf.dist` into the realm
   configuration as needed. Defaults enable the feature, allow 20 sets, and limit names to 48 bytes.
4. Rebuild and deploy worldserver with the module. No AzerothCore core patch or custom hook is required.
5. Run `python3 content/build_epf.py` followed by `python3 content/build_epf.py --check`, deploy the resulting
   `content/mod-native-transmog.epf` through Content Manager,
   and run the normal Portalkeeper client-patch generation/deployment flow.
6. Restart worldserver. A configuration reload can change limits, but schema availability is checked at startup/reload.

## PTR acceptance

- Create a named set with armor and weapon selections, log out/restart, and verify it reloads unchanged.
- Rename it, replace and clear individual slots, cancel an edit, and confirm only a later Save persists.
- Verify another character cannot list, edit, delete, preview by forged ID, or apply the set.
- Verify duplicate names, empty names, overlong names, the configured limit, uncollected entries, and wrong-slot entries
  produce useful errors.
- Compare custom preview against current unspecified slots; switch repeatedly between Items, predefined Sets, and custom
  Sets; verify predefined ordering/progress/totals remain unchanged.
- At an authorized Transmogrifier, load a fully compatible set and click **Apply Outfit**. Repeat with a
  missing/incompatible weapon and verify no slot is applied. Try the same request remotely and verify session rejection.
- Verify explicit hide only where configured, no double application, no item/equipment mutation during preview/edit,
  existing single-slot NPC transmog, collection acquisition, icon rendering, Dominos, and Content Manager navigation.

## Known limitations

- Set application is free because the existing application service has no cost policy.
- The protected client uses byte-length rather than Unicode code-point length for names, matching the server and 3.3.5a
  transport constraints.
- Runtime visual acceptance still requires the build-12340 PTR client; automated tests validate Lua 5.1 syntax and UI
  contracts but cannot render a WoW `DressUpModel` off-client.
