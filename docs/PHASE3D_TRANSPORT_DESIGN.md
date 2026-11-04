# Phase 3D transport design

## Decision

Phase 3D uses the stock WoW 3.3.5a addon-message transport over a self-whisper. The protected
FrameXML sends requests with `SendAddonMessage("NTRANSMOG", payload, "WHISPER", UnitName("player"))` and
receives server responses through `CHAT_MSG_ADDON`. This is an extension of the Phase 2 server-to-client
path, not an addon package, chat command, custom opcode, or new RPC facility.

The decision was verified against the checked-out Playerbot AzerothCore revision recorded in
`docs/INSPECTION.md`. `WorldSession::HandleMessagechatOpcode` accepts `LANG_ADDON` with
`CHAT_MSG_WHISPER`, applies the core's 255-byte message limit and addon flood accounting, and invokes
the player chat hooks. `Player::Whisper` invokes the private-chat authorization hook before delivery.
The module can therefore recognize and consume only its own authenticated self-whisper traffic with
`PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT` / `PlayerScript::OnPlayerCanUseChat(Player*, uint32, uint32,
std::string&, Player*)`.

## Client APIs and events

- `RegisterAddonMessagePrefix("NTRANSMOG")` registers the prefix when that build-12340 API is present.
- `SendAddonMessage(prefix, message, "WHISPER", UnitName("player"))` sends bounded requests.
- `CHAT_MSG_ADDON` carries replies. Lua accepts only the exact prefix, `WHISPER`, and the local player's
  sender name.
- `GetItemIcon`, `GameTooltip:SetHyperlink`, and `DressUpModel:TryOn` resolve catalog presentation from
  the server-selected canonical item-template entry already present in the build-12340 client data.

The FrameXML remains under `Interface/FrameXML`; nothing is installed below `Interface/AddOns`.

## Server hooks and routing

`NativeTransmogPlayerScript` registers `PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT`. It handles a message
only when all of these are true:

1. chat type is `CHAT_MSG_WHISPER` and language is `LANG_ADDON`;
2. sender and receiver are the same authenticated `Player*`;
3. the message starts with the exact `NTRANSMOG\t` prefix;
4. the protocol version, operation, field count, lengths, and numeric fields are valid.

Recognized module messages are consumed by returning `false`, so they are not echoed or exposed as
ordinary chat. Other addon messages retain normal core behavior. The hook-provided `Player*` is the
sole identity authority; requests contain no account ID, character GUID, item GUID, NPC GUID, or
ownership assertion.

## Authorization and request binding

Every operation includes the opaque Phase 2 session token. The server compares it with the token held
for that authenticated player and then reruns the full Phase 2 session validation: registered
Transmogrifier resolution, live NPC lookup, same map, core NPC-interaction distance/conditions, player
alive, player out of combat, and session lifetime. Direct `/wardrobe` and `/nativetransmog` windows have
no token and remain preview-only.

A catalog response creates a short-lived server snapshot containing the equipment slot, equipped item
instance GUID, and the exact canonical source entries offered on that page. Apply and remove requests
refer to the server-issued snapshot nonce and, for apply, a page-local selection ID. The server never
accepts client item ownership, compatibility, equipment, or account claims. Before invoking Phase 3C,
it verifies that the snapshot is current and the same item instance remains equipped. Phase 3C then
again validates the live session, collection ownership, source template, and compatibility.

## Catalog transfer and pagination

Catalog requests specify only a supported slot and an opaque bounded cursor/offset. The server derives
the collection owner from the authenticated session, resolves the equipped item, queries a bounded
deterministically ordered slice, and filters it with the Phase 3C `CompatibilityValidator`. Canonical
source candidates are indexed once from loaded item templates and sorted by item entry. For a collected
composite appearance identity, the lowest-entry candidate that passes the shared validator for the
current player and target is selected. This avoids depending on a retained physical source item and
does not discard an appearance merely because another template sharing the identity is restricted.

Responses are split into messages below the core's 255-byte maximum: one page header, zero or more item
records, and an end marker. Item records carry selection ID and canonical item entry; icons, localized
names, and tooltips are resolved by the client. Page size is bounded by configuration, ordering is by
the persisted composite identity, and the response returns the next cursor. The client keeps cursor
history for Previous and never requests per frame.

## Validation, replay, and rate limits

- Protocol input has an explicit version, exact operation grammar, a conservative maximum length,
  decimal-only bounded integers, supported-slot allowlisting, and no free-form strings.
- Requests are subject to a per-player steady-clock cooldown in addition to AzerothCore addon flood
  accounting.
- A new page invalidates the previous snapshot. Snapshot nonces are server-issued, expire, and are
  bound to player, session, slot, and equipped item instance. Successful mutations consume their
  snapshot. A replay or stale/equipment-changed request receives an explicit refresh error.
- Unknown versions and malformed, oversized, unauthorized, or rate-limited messages are consumed and
  answered with a bounded result when it is safe to do so; they never reach application services.

## Disconnects and expiration

Logout releases the Phase 2 session and Phase 3D request/snapshot state. Map change, NPC despawn,
distance failure, combat, death, registration removal, or lifetime expiry closes the server session and
sends `CLOSE` when possible. The client closes the authorized wardrobe and clears pending state. Late
responses are ignored unless their token/request identifiers match the current UI state. A request
timeout is client-side presentation only and never implies that an operation succeeded.

## Why no opcode or addon is required

Both directions use facilities already implemented by client build 12340 and the inspected core:
`CMSG_MESSAGECHAT`/`LANG_ADDON` inbound, ordinary addon whisper packets outbound, protected FrameXML
Lua APIs, and existing script hooks. The module does not register an opcode handler, patch the core,
parse unrestricted player chat commands, or ship an addon TOC.

## Build-12340 limitations

- Addon payloads are limited to 255 bytes by the core, so pages are multipart and records are compact.
- Delivery is not cryptographic or reliable. The protocol uses server state for authority, request
  correlation, explicit completion markers, and UI timeouts.
- Item data may initially be uncached client-side; icons/tooltips use normal `GetItemInfo` behavior and
  a question-mark fallback until the client receives item data.
- Protected FrameXML can call the global addon-message APIs in this client, but taint/security behavior
  differs from modern retail APIs; the UI does not hook secure combat actions.
- The transport requires the realm's addon channel (`AddonChannel = 1`). If disabled, requests cannot
  arrive and the UI reports a timeout; deployment validation must check this setting.

## EPF changes

The existing symbolic dedicated creature resource and `clientFrameXml` composition remain unchanged.
The protected `NativeTransmogFrame.lua` and `.xml` resources are updated in place and the deterministic
EPF is rebuilt with `content/build_epf.py`. No arbitrary resource ID, generated MPQ edit, Portalkeeper
change, or Content Manager capability extension is required.
