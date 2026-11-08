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
Right-click clears a draft slot; Shift-click requests explicit hide where the application configuration permits it.
Save is the only operation that writes the draft. Cancel discards it.

Custom preview starts with the player's current model and applies only specified pieces, so unspecified slots remain as
they are. Predefined preview continues to undress the model and dress the complete predefined set. Neither path writes
equipment or item overrides.

## NPC application and security

The existing NPC wardrobe has a Saved Custom Sets selector. Application is deliberately unavailable from Collections.
The NPC path loads the set with both set ID and authenticated character GUID, resolves every canonical appearance,
rechecks collection ownership, validates every currently equipped target with `CompatibilityValidator`, and reports
per-slot failures. A confirmation nonce is issued only when every specified selection is valid. Confirmation rechecks
the live NPC session and atomically writes all item-instance overrides in one character-database transaction before
updating the cache and visible equipment. Unspecified slots are untouched.

Requests are protocol-versioned, length-bounded, rate-limited, paged, and numeric except for the final bounded name
field. Names are trimmed and validated server-side, escaped before SQL use, limited to 48 UTF-8 bytes by default, and
unique per character. The default maximum is 20 sets; `NativeTransmog.CustomSets.MaximumPerCharacter` is clamped to
1–100. Set ownership, appearance ownership, slot validity, hide policy, compatibility, and NPC authorization never rely
on client claims.

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
5. Run `python3 content/build_epf.py`, deploy the resulting `content/mod-native-transmog.epf` through Content Manager,
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
- At an authorized Transmogrifier, preflight a fully compatible set and confirm it. Repeat with a missing/incompatible
  weapon and verify no slot is applied. Try the same request remotely and verify session rejection.
- Verify explicit hide only where configured, no double application, no item/equipment mutation during preview/edit,
  existing single-slot NPC transmog, collection acquisition, icon rendering, Dominos, and Content Manager navigation.

## Known limitations

- Set application is free because the existing application service has no cost policy.
- The protected client uses byte-length rather than Unicode code-point length for names, matching the server and 3.3.5a
  transport constraints.
- Runtime visual acceptance still requires the build-12340 PTR client; automated tests validate Lua 5.1 syntax and UI
  contracts but cannot render a WoW `DressUpModel` off-client.
