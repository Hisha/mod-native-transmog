#include "NativeTransmogCustomSet.h"

#include "DatabaseEnv.h"
#include "ItemTemplate.h"
#include "Log.h"
#include "NativeTransmogApplication.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "SharedDefines.h"

#include <algorithm>
#include <unordered_set>

namespace native_transmog
{
namespace
{
bool CharacterOwner(Player const* player, std::uint32_t& owner)
{
    owner = player ? player->GetGUID().GetCounter() : 0;
    return owner != 0;
}

bool PlayerCanUseSource(Player const* player, ItemTemplate const* source)
{
    if (!player || !source || (source->AllowableClass & player->getClassMask()) == 0 ||
        (source->AllowableRace & player->getRaceMask()) == 0)
        return false;
    if (source->RequiredSkill && player->GetSkillValue(source->RequiredSkill) < source->RequiredSkillRank)
        return false;
    return !source->RequiredSpell || player->HasSpell(source->RequiredSpell);
}
}

CustomSetService& CustomSetService::Instance()
{
    static CustomSetService service;
    return service;
}

void CustomSetService::Configure(CustomSetConfig const& config)
{
    _config = config;
    _config.maximumSets = std::max<std::uint32_t>(1, std::min<std::uint32_t>(config.maximumSets, 100));
    _config.maximumNameBytes = std::max<std::uint32_t>(8, std::min<std::uint32_t>(config.maximumNameBytes, 96));
}

bool CustomSetService::Initialize()
{
    QueryResult table = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM `information_schema`.`TABLES` WHERE `TABLE_SCHEMA` = DATABASE() "
        "AND `TABLE_NAME` IN ('native_transmog_custom_set', 'native_transmog_custom_set_piece')");
    _databaseAvailable = table && table->Fetch()[0].Get<std::uint64_t>() == 2;
    if (!_databaseAvailable)
        LOG_ERROR("module.native_transmog", "Custom-set tables are missing; custom appearance sets are unavailable.");
    return _databaseAvailable;
}

bool CustomSetService::IsEnabled() const { return _config.enabled && _databaseAvailable; }
std::uint32_t CustomSetService::MaximumSets() const { return _config.maximumSets; }
std::uint32_t CustomSetService::MaximumNameBytes() const { return _config.maximumNameBytes; }

bool CustomSetService::NormalizeName(std::string& name, std::uint32_t maximumBytes)
{
    auto space = [](unsigned char value) { return value == ' ' || value == '\t' || value == '\r' || value == '\n'; };
    while (!name.empty() && space(static_cast<unsigned char>(name.front())))
        name.erase(name.begin());
    while (!name.empty() && space(static_cast<unsigned char>(name.back())))
        name.pop_back();
    if (name.empty() || name.size() > maximumBytes)
        return false;
    for (unsigned char value : name)
        if (value < 32 || value == 127 || value == '\t' || value == '\r' || value == '\n')
            return false;
    return true;
}

bool CustomSetService::SlotAccepts(std::uint8_t slot, AppearanceKey const& appearance)
{
    if (!IsSupportedEquipmentSlot(slot))
        return false;
    if (appearance.itemClass == ITEM_CLASS_ARMOR)
    {
        switch (slot)
        {
            case EQUIPMENT_SLOT_HEAD: return appearance.inventoryType == INVTYPE_HEAD;
            case EQUIPMENT_SLOT_SHOULDERS: return appearance.inventoryType == INVTYPE_SHOULDERS;
            case EQUIPMENT_SLOT_BODY: return appearance.inventoryType == INVTYPE_BODY;
            case EQUIPMENT_SLOT_CHEST: return appearance.inventoryType == INVTYPE_CHEST || appearance.inventoryType == INVTYPE_ROBE;
            case EQUIPMENT_SLOT_WAIST: return appearance.inventoryType == INVTYPE_WAIST;
            case EQUIPMENT_SLOT_LEGS: return appearance.inventoryType == INVTYPE_LEGS;
            case EQUIPMENT_SLOT_FEET: return appearance.inventoryType == INVTYPE_FEET;
            case EQUIPMENT_SLOT_WRISTS: return appearance.inventoryType == INVTYPE_WRISTS;
            case EQUIPMENT_SLOT_HANDS: return appearance.inventoryType == INVTYPE_HANDS;
            case EQUIPMENT_SLOT_BACK: return appearance.inventoryType == INVTYPE_CLOAK;
            case EQUIPMENT_SLOT_TABARD: return appearance.inventoryType == INVTYPE_TABARD;
            case EQUIPMENT_SLOT_OFFHAND:
                return appearance.inventoryType == INVTYPE_SHIELD || appearance.inventoryType == INVTYPE_HOLDABLE;
            default: return false;
        }
    }
    if (appearance.itemClass != ITEM_CLASS_WEAPON)
        return false;
    if (slot == EQUIPMENT_SLOT_MAINHAND)
        return appearance.inventoryType == INVTYPE_WEAPON || appearance.inventoryType == INVTYPE_WEAPONMAINHAND ||
            appearance.inventoryType == INVTYPE_2HWEAPON;
    if (slot == EQUIPMENT_SLOT_OFFHAND)
        return appearance.inventoryType == INVTYPE_WEAPON || appearance.inventoryType == INVTYPE_WEAPONOFFHAND;
    if (slot == EQUIPMENT_SLOT_RANGED)
        return appearance.inventoryType == INVTYPE_RANGED || appearance.inventoryType == INVTYPE_RANGEDRIGHT ||
            appearance.inventoryType == INVTYPE_THROWN;
    return false;
}

std::uint32_t CustomSetService::ResolveRepresentative(Player const* player, CustomSetPiece const& piece) const
{
    if (piece.state == CustomSetSelectionState::Hidden)
        return 0;
    if (!CollectionService::Instance().IsCollected(player, piece.appearance))
        return 0;
    std::uint32_t best = 0;
    for (auto const& [entry, itemTemplate] : *sObjectMgr->GetItemTemplateStore())
    {
        AppearanceKey resolved;
        if (CollectionService::ResolveAppearance(&itemTemplate, resolved) && resolved == piece.appearance &&
            SlotAccepts(piece.equipmentSlot, resolved) && PlayerCanUseSource(player, &itemTemplate) && (!best || entry < best))
            best = entry;
    }
    return best;
}

bool CustomSetService::ResolveSelection(Player const* player, std::uint8_t equipmentSlot,
    std::uint32_t representativeItem, CustomSetPiece& piece) const
{
    ItemTemplate const* source = sObjectMgr->GetItemTemplate(representativeItem);
    AppearanceKey appearance;
    if (!source || !CollectionService::ResolveAppearance(source, appearance) || !SlotAccepts(equipmentSlot, appearance) ||
        !PlayerCanUseSource(player, source) || !CollectionService::Instance().IsCollected(player, appearance))
        return false;
    piece = { equipmentSlot, CustomSetSelectionState::Appearance, appearance };
    return true;
}

CustomSetResult CustomSetService::ValidatePieces(Player const* player,
    std::vector<CustomSetPiece> const& pieces) const
{
    if (pieces.empty())
        return CustomSetResult::EmptySet;
    if (pieces.size() > 14)
        return CustomSetResult::InvalidSlot;
    std::unordered_set<std::uint8_t> slots;
    for (CustomSetPiece const& piece : pieces)
    {
        if (!IsSupportedEquipmentSlot(piece.equipmentSlot))
            return CustomSetResult::InvalidSlot;
        if (!slots.insert(piece.equipmentSlot).second)
            return CustomSetResult::DuplicateSlot;
        if (piece.state == CustomSetSelectionState::Hidden)
        {
            if (!ApplicationService::Instance().CanHide(piece.equipmentSlot))
                return CustomSetResult::HideUnsupported;
            continue;
        }
        if (!piece.appearance.displayId || !SlotAccepts(piece.equipmentSlot, piece.appearance) ||
            !ResolveRepresentative(player, piece))
            return CustomSetResult::SlotMismatch;
        if (!CollectionService::Instance().IsCollected(player, piece.appearance))
            return CustomSetResult::AppearanceNotCollected;
    }
    return CustomSetResult::Ok;
}

std::uint32_t CustomSetService::Count(Player const* player) const
{
    std::uint32_t owner = 0;
    if (!IsEnabled() || !CharacterOwner(player, owner))
        return 0;
    QueryResult result = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM `native_transmog_custom_set` WHERE `owner_guid` = {}", owner);
    return result ? result->Fetch()[0].Get<std::uint32_t>() : 0;
}

std::vector<CustomSet> CustomSetService::List(Player const* player, std::uint32_t offset, std::uint32_t limit) const
{
    std::vector<CustomSet> sets;
    std::uint32_t owner = 0;
    if (!IsEnabled() || !CharacterOwner(player, owner) || !limit)
        return sets;
    limit = std::min<std::uint32_t>(limit, 20);
    if (QueryResult result = CharacterDatabase.Query(
        "SELECT `set_id`, `name`, UNIX_TIMESTAMP(`created_at`), UNIX_TIMESTAMP(`updated_at`) "
        "FROM `native_transmog_custom_set` WHERE `owner_guid` = {} "
        "ORDER BY `updated_at` DESC, `set_id` DESC LIMIT {} OFFSET {}", owner, limit, offset))
    {
        do
        {
            Field* fields = result->Fetch();
            sets.push_back({ fields[0].Get<std::uint32_t>(), owner, fields[1].Get<std::string>(),
                fields[2].Get<std::uint64_t>(), fields[3].Get<std::uint64_t>(), {} });
        } while (result->NextRow());
    }
    return sets;
}

bool CustomSetService::Load(Player const* player, std::uint32_t setId, CustomSet& set) const
{
    std::uint32_t owner = 0;
    if (!IsEnabled() || !setId || !CharacterOwner(player, owner))
        return false;
    QueryResult result = CharacterDatabase.Query(
        "SELECT `name`, UNIX_TIMESTAMP(`created_at`), UNIX_TIMESTAMP(`updated_at`) "
        "FROM `native_transmog_custom_set` WHERE `set_id` = {} AND `owner_guid` = {}", setId, owner);
    if (!result)
        return false;
    Field* head = result->Fetch();
    set = { setId, owner, head[0].Get<std::string>(), head[1].Get<std::uint64_t>(), head[2].Get<std::uint64_t>(), {} };
    if (QueryResult pieces = CharacterDatabase.Query(
        "SELECT `equipment_slot`, `selection_state`, `display_id`, `item_class`, `item_subclass`, `inventory_type` "
        "FROM `native_transmog_custom_set_piece` WHERE `set_id` = {} ORDER BY `equipment_slot`", setId))
    {
        do
        {
            Field* fields = pieces->Fetch();
            std::uint8_t state = fields[1].Get<std::uint8_t>();
            if (state > static_cast<std::uint8_t>(CustomSetSelectionState::Hidden))
                return false;
            set.pieces.push_back({ fields[0].Get<std::uint8_t>(), static_cast<CustomSetSelectionState>(state),
                { fields[2].Get<std::uint32_t>(), fields[3].Get<std::uint8_t>(),
                  fields[4].Get<std::uint8_t>(), fields[5].Get<std::uint8_t>() } });
        } while (pieces->NextRow());
    }
    return true;
}

CustomSetResult CustomSetService::Create(Player* player, std::string name,
    std::vector<CustomSetPiece> const& pieces, std::uint32_t& setId)
{
    setId = 0;
    return Save(player, 0, true, std::move(name), pieces, setId);
}

CustomSetResult CustomSetService::Update(Player* player, std::uint32_t setId, std::string name,
    std::vector<CustomSetPiece> const& pieces)
{
    std::uint32_t savedId = setId;
    return Save(player, setId, false, std::move(name), pieces, savedId);
}

CustomSetResult CustomSetService::Save(Player* player, std::uint32_t setId, bool creating,
    std::string name, std::vector<CustomSetPiece> const& pieces, std::uint32_t& savedId)
{
    std::uint32_t owner = 0;
    if (!_config.enabled)
        return CustomSetResult::Disabled;
    if (!_databaseAvailable)
        return CustomSetResult::DatabaseUnavailable;
    if (!CharacterOwner(player, owner) || !NormalizeName(name, _config.maximumNameBytes))
        return CustomSetResult::InvalidName;
    CustomSetResult valid = ValidatePieces(player, pieces);
    if (valid != CustomSetResult::Ok)
        return valid;
    if (creating && Count(player) >= _config.maximumSets)
        return CustomSetResult::LimitReached;
    if (!creating)
    {
        CustomSet existing;
        if (!Load(player, setId, existing))
            return CustomSetResult::NotFound;
    }
    std::string escaped = name;
    CharacterDatabase.EscapeString(escaped);
    QueryResult duplicate = CharacterDatabase.Query(
        "SELECT `set_id` FROM `native_transmog_custom_set` WHERE `owner_guid` = {} AND `name` = '{}' "
        "AND `set_id` <> {} LIMIT 1", owner, escaped, setId);
    if (duplicate)
        return CustomSetResult::DuplicateName;

    if (creating)
    {
        CharacterDatabase.DirectExecute(
            "INSERT INTO `native_transmog_custom_set` (`owner_guid`, `name`) VALUES ({}, '{}')", owner, escaped);
        QueryResult inserted = CharacterDatabase.Query(
            "SELECT `set_id` FROM `native_transmog_custom_set` WHERE `owner_guid` = {} AND `name` = '{}' LIMIT 1",
            owner, escaped);
        if (!inserted)
            return CustomSetResult::DatabaseUnavailable;
        setId = inserted->Fetch()[0].Get<std::uint32_t>();
    }

    CharacterDatabaseTransaction transaction = CharacterDatabase.BeginTransaction();
    if (!creating)
        transaction->Append("UPDATE `native_transmog_custom_set` SET `name` = '{}', `updated_at` = CURRENT_TIMESTAMP "
            "WHERE `set_id` = {} AND `owner_guid` = {}", escaped, setId, owner);
    transaction->Append("DELETE FROM `native_transmog_custom_set_piece` WHERE `set_id` = {}", setId);
    for (CustomSetPiece const& piece : pieces)
        transaction->Append(
            "INSERT INTO `native_transmog_custom_set_piece` (`set_id`, `equipment_slot`, `selection_state`, "
            "`display_id`, `item_class`, `item_subclass`, `inventory_type`) VALUES ({}, {}, {}, {}, {}, {}, {})",
            setId, static_cast<std::uint32_t>(piece.equipmentSlot), static_cast<std::uint32_t>(piece.state),
            piece.appearance.displayId, static_cast<std::uint32_t>(piece.appearance.itemClass),
            static_cast<std::uint32_t>(piece.appearance.itemSubclass),
            static_cast<std::uint32_t>(piece.appearance.inventoryType));
    CharacterDatabase.DirectCommitTransaction(transaction);
    savedId = setId;
    LOG_INFO("module.native_transmog", "{} custom appearance set {} for character {} with {} selections.",
        creating ? "Created" : "Updated", setId, owner, pieces.size());
    return CustomSetResult::Ok;
}

CustomSetResult CustomSetService::Delete(Player* player, std::uint32_t setId)
{
    CustomSet set;
    if (!Load(player, setId, set))
        return IsEnabled() ? CustomSetResult::NotFound : CustomSetResult::DatabaseUnavailable;
    CharacterDatabase.DirectExecute(
        "DELETE FROM `native_transmog_custom_set` WHERE `set_id` = {} AND `owner_guid` = {}",
        setId, player->GetGUID().GetCounter());
    return CustomSetResult::Ok;
}

char const* CustomSetService::ResultName(CustomSetResult result)
{
    switch (result)
    {
        case CustomSetResult::Ok: return "ok";
        case CustomSetResult::Disabled: return "CUSTOM_DISABLED";
        case CustomSetResult::DatabaseUnavailable: return "CUSTOM_DATABASE_UNAVAILABLE";
        case CustomSetResult::NotFound: return "CUSTOM_NOT_FOUND";
        case CustomSetResult::InvalidName: return "CUSTOM_INVALID_NAME";
        case CustomSetResult::DuplicateName: return "CUSTOM_DUPLICATE_NAME";
        case CustomSetResult::LimitReached: return "CUSTOM_LIMIT_REACHED";
        case CustomSetResult::InvalidSlot: return "CUSTOM_INVALID_SLOT";
        case CustomSetResult::DuplicateSlot: return "CUSTOM_DUPLICATE_SLOT";
        case CustomSetResult::InvalidAppearance: return "CUSTOM_INVALID_APPEARANCE";
        case CustomSetResult::AppearanceNotCollected: return "CUSTOM_NOT_COLLECTED";
        case CustomSetResult::SlotMismatch: return "CUSTOM_SLOT_MISMATCH";
        case CustomSetResult::HideUnsupported: return "CUSTOM_HIDE_UNSUPPORTED";
        case CustomSetResult::EmptySet: return "CUSTOM_EMPTY_SET";
        default: return "CUSTOM_UNKNOWN";
    }
}
}
