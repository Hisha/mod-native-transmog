#include "NativeTransmogApplication.h"

#include "DatabaseEnv.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Log.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "SharedDefines.h"
#include "UpdateFields.h"
#include "NativeTransmogService.h"

#include <iterator>
#include <vector>

namespace native_transmog
{
bool IsSupportedEquipmentSlot(std::uint8_t equipmentSlot)
{
    switch (equipmentSlot)
    {
        case EQUIPMENT_SLOT_HEAD:
        case EQUIPMENT_SLOT_SHOULDERS:
        case EQUIPMENT_SLOT_BODY:
        case EQUIPMENT_SLOT_CHEST:
        case EQUIPMENT_SLOT_WAIST:
        case EQUIPMENT_SLOT_LEGS:
        case EQUIPMENT_SLOT_FEET:
        case EQUIPMENT_SLOT_WRISTS:
        case EQUIPMENT_SLOT_HANDS:
        case EQUIPMENT_SLOT_BACK:
        case EQUIPMENT_SLOT_MAINHAND:
        case EQUIPMENT_SLOT_OFFHAND:
        case EQUIPMENT_SLOT_RANGED:
        case EQUIPMENT_SLOT_TABARD:
            return true;
        default:
            return false;
    }
}

bool IsWeaponEquipmentSlot(std::uint8_t equipmentSlot)
{
    return equipmentSlot == EQUIPMENT_SLOT_MAINHAND || equipmentSlot == EQUIPMENT_SLOT_OFFHAND ||
        equipmentSlot == EQUIPMENT_SLOT_RANGED;
}

namespace
{
bool ClassAllowed(Player const* player, ItemTemplate const* source)
{
    return player && source && (source->AllowableClass & player->getClassMask()) != 0;
}

bool HasSubclassProficiency(std::uint32_t mask, std::uint32_t subclass)
{
    return subclass < 32 && (mask & (1U << subclass)) != 0;
}

bool IsChest(std::uint32_t inventoryType)
{
    return inventoryType == INVTYPE_CHEST || inventoryType == INVTYPE_ROBE;
}

bool IsOneHand(std::uint32_t inventoryType)
{
    return inventoryType == INVTYPE_WEAPON || inventoryType == INVTYPE_WEAPONMAINHAND ||
        inventoryType == INVTYPE_WEAPONOFFHAND;
}

bool IsTwoHand(std::uint32_t inventoryType)
{
    return inventoryType == INVTYPE_2HWEAPON;
}

bool OneHandSlotCompatible(std::uint32_t targetType, std::uint32_t sourceType, std::uint8_t equipmentSlot)
{
    if (equipmentSlot == EQUIPMENT_SLOT_MAINHAND)
        return sourceType == INVTYPE_WEAPON || sourceType == INVTYPE_WEAPONMAINHAND;
    if (equipmentSlot == EQUIPMENT_SLOT_OFFHAND)
        return sourceType == INVTYPE_WEAPON || sourceType == INVTYPE_WEAPONOFFHAND;
    if (targetType == INVTYPE_WEAPONMAINHAND)
        return sourceType == INVTYPE_WEAPON || sourceType == INVTYPE_WEAPONMAINHAND;
    if (targetType == INVTYPE_WEAPONOFFHAND)
        return sourceType == INVTYPE_WEAPON || sourceType == INVTYPE_WEAPONOFFHAND;
    return targetType == INVTYPE_WEAPON && IsOneHand(sourceType);
}

std::uint32_t WeaponFamily(std::uint32_t subclass)
{
    switch (subclass)
    {
        case ITEM_SUBCLASS_WEAPON_AXE:
        case ITEM_SUBCLASS_WEAPON_AXE2: return ITEM_SUBCLASS_WEAPON_AXE;
        case ITEM_SUBCLASS_WEAPON_MACE:
        case ITEM_SUBCLASS_WEAPON_MACE2: return ITEM_SUBCLASS_WEAPON_MACE;
        case ITEM_SUBCLASS_WEAPON_SWORD:
        case ITEM_SUBCLASS_WEAPON_SWORD2: return ITEM_SUBCLASS_WEAPON_SWORD;
        default: return subclass + 100U;
    }
}
}

ApplicationResult CompatibilityValidator::Validate(Player const* player, ItemTemplate const* target,
    ItemTemplate const* source, ApplicationConfig const& config, std::uint8_t equipmentSlot)
{
    AppearanceKey targetAppearance;
    AppearanceKey sourceAppearance;
    if (!CollectionService::ResolveAppearance(source, sourceAppearance))
        return ApplicationResult::AppearanceIneligible;
    if (!CollectionService::ResolveAppearance(target, targetAppearance))
        return ApplicationResult::TargetMissing;
    if (!ClassAllowed(player, source))
        return ApplicationResult::ClassRestricted;
    if ((source->AllowableRace & player->getRaceMask()) == 0)
        return ApplicationResult::RaceRestricted;
    if (source->RequiredSkill)
    {
        std::uint32_t skillValue = player->GetSkillValue(source->RequiredSkill);
        if (!skillValue || skillValue < source->RequiredSkillRank)
            return ApplicationResult::RequiredSkillRestricted;
    }
    if (source->RequiredSpell && !player->HasSpell(source->RequiredSpell))
        return ApplicationResult::RequiredSpellRestricted;
    if (target->Class != source->Class)
        return ApplicationResult::ItemClassMismatch;

    if (source->Class == ITEM_CLASS_ARMOR)
    {
        if (source->SubClass != target->SubClass)
            return ApplicationResult::ArmorSubclassMismatch;
        std::uint32_t skill = source->GetSkill();
        if (skill && !HasSubclassProficiency(player->GetArmorProficiency(), source->SubClass))
            return ApplicationResult::ArmorProficiencyRestricted;
        if (source->InventoryType != target->InventoryType &&
            !(IsChest(source->InventoryType) && IsChest(target->InventoryType)))
            return ApplicationResult::InventoryTypeMismatch;
        return ApplicationResult::Ok;
    }

    std::uint32_t skill = source->GetSkill();
    if (skill && !HasSubclassProficiency(player->GetWeaponProficiency(), source->SubClass))
        return ApplicationResult::WeaponProficiencyRestricted;
    if (WeaponFamily(source->SubClass) != WeaponFamily(target->SubClass))
        return ApplicationResult::WeaponSubclassMismatch;

    bool targetOneHand = IsOneHand(target->InventoryType);
    bool sourceOneHand = IsOneHand(source->InventoryType);
    bool targetTwoHand = IsTwoHand(target->InventoryType);
    bool sourceTwoHand = IsTwoHand(source->InventoryType);
    if (targetOneHand && sourceTwoHand)
        return config.allowTwoHandAppearanceOnOneHand ? ApplicationResult::Ok :
            ApplicationResult::TwoHandOnOneHandDisabled;
    if (targetTwoHand && sourceOneHand)
    {
        if (source->InventoryType == INVTYPE_WEAPONOFFHAND)
            return ApplicationResult::InventoryTypeMismatch;
        return config.allowOneHandAppearanceOnTwoHand ? ApplicationResult::Ok :
            ApplicationResult::OneHandOnTwoHandDisabled;
    }
    if (targetOneHand && sourceOneHand)
        return OneHandSlotCompatible(target->InventoryType, source->InventoryType, equipmentSlot) ?
            ApplicationResult::Ok : ApplicationResult::InventoryTypeMismatch;
    if (target->InventoryType != source->InventoryType)
        return ApplicationResult::InventoryTypeMismatch;
    return ApplicationResult::Ok;
}

ApplicationService& ApplicationService::Instance()
{
    static ApplicationService service;
    return service;
}

void ApplicationService::Configure(ApplicationConfig const& config)
{
    std::lock_guard<std::mutex> lock(_mutex);
    _config = config;
    if (!_config.enabled)
        _overrides.clear();
}

bool ApplicationService::Initialize()
{
    QueryResult table = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM `information_schema`.`COLUMNS` "
        "WHERE `TABLE_SCHEMA` = DATABASE() AND `TABLE_NAME` = 'native_transmog_item_override' "
        "AND `COLUMN_NAME` IN ('appearance_item', 'override_state')");
    std::lock_guard<std::mutex> lock(_mutex);
    _databaseAvailable = table && table->Fetch()[0].Get<std::uint64_t>() == 2;
    if (!_databaseAvailable)
        LOG_ERROR("module.native_transmog",
            "Application table native_transmog_item_override is missing; appearance application is unavailable.");
    return _databaseAvailable;
}

bool ApplicationService::IsEnabled() const
{
    std::lock_guard<std::mutex> lock(_mutex);
    return _config.enabled;
}

bool ApplicationService::IsDatabaseAvailable() const
{
    std::lock_guard<std::mutex> lock(_mutex);
    return _databaseAvailable;
}

bool ApplicationService::Authorized(Player* player, ApplicationAuthorization authorization) const
{
    return player && player->GetSession() && (authorization == ApplicationAuthorization::GmDiagnostic ||
        Service::Instance().ValidateSession(player));
}

ApplicationResult ApplicationService::Apply(Player* player, std::uint8_t equipmentSlot,
    std::uint32_t appearanceItem, ApplicationAuthorization authorization)
{
    ApplicationConfig config;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_config.enabled)
            return ApplicationResult::Disabled;
        if (!_databaseAvailable)
            return ApplicationResult::DatabaseUnavailable;
        config = _config;
    }
    if (!Authorized(player, authorization))
        return ApplicationResult::Unauthorized;
    if (!IsSupportedEquipmentSlot(equipmentSlot))
        return ApplicationResult::InvalidSlot;
    Item* target = player->GetItemByPos(INVENTORY_SLOT_BAG_0, equipmentSlot);
    if (!target || target->GetOwnerGUID() != player->GetGUID())
        return ApplicationResult::TargetMissing;
    ItemTemplate const* source = sObjectMgr->GetItemTemplate(appearanceItem);
    if (!source)
        return ApplicationResult::SourceMissing;

    AppearanceKey appearance;
    if (!CollectionService::ResolveAppearance(source, appearance))
        return ApplicationResult::AppearanceIneligible;
    if (!CollectionService::Instance().IsCollected(player, appearance))
        return ApplicationResult::AppearanceNotCollected;
    ApplicationResult compatibility = CompatibilityValidator::Validate(
        player, target->GetTemplate(), source, config, equipmentSlot);
    if (compatibility != ApplicationResult::Ok)
        return compatibility;

    AppearanceOverride appearanceOverride{ target->GetGUID().GetCounter(), player->GetGUID().GetCounter(),
        appearanceItem, appearance };
    CharacterDatabase.DirectExecute(
        "INSERT INTO `native_transmog_item_override` "
        "(`item_guid`, `owner_guid`, `override_state`, `appearance_item`, `display_id`, `item_class`, "
        "`item_subclass`, `inventory_type`, `applied_at`) "
        "VALUES ({}, {}, {}, {}, {}, {}, {}, {}, CURRENT_TIMESTAMP) "
        "ON DUPLICATE KEY UPDATE `owner_guid` = VALUES(`owner_guid`), "
        "`override_state` = VALUES(`override_state`), `appearance_item` = VALUES(`appearance_item`), "
        "`display_id` = VALUES(`display_id`), "
        "`item_class` = VALUES(`item_class`), `item_subclass` = VALUES(`item_subclass`), "
        "`inventory_type` = VALUES(`inventory_type`), `applied_at` = CURRENT_TIMESTAMP",
        appearanceOverride.itemGuid, appearanceOverride.ownerGuid,
        static_cast<std::uint32_t>(appearanceOverride.state), appearanceOverride.appearanceItem,
        appearance.displayId, static_cast<std::uint32_t>(appearance.itemClass),
        static_cast<std::uint32_t>(appearance.itemSubclass), static_cast<std::uint32_t>(appearance.inventoryType));
    {
        std::lock_guard<std::mutex> lock(_mutex);
        _overrides[appearanceOverride.itemGuid] = appearanceOverride;
    }
    player->SetVisibleItemSlot(equipmentSlot, target);
    LOG_INFO("module.native_transmog", "Applied collected appearance item {} to item {} owned by character {}.",
        appearanceItem, appearanceOverride.itemGuid, appearanceOverride.ownerGuid);
    return ApplicationResult::Ok;
}

ApplicationResult ApplicationService::Hide(Player* player, std::uint8_t equipmentSlot,
    ApplicationAuthorization authorization)
{
    ApplicationConfig config;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_config.enabled)
            return ApplicationResult::Disabled;
        if (!_databaseAvailable)
            return ApplicationResult::DatabaseUnavailable;
        config = _config;
    }
    if (!Authorized(player, authorization))
        return ApplicationResult::Unauthorized;
    if (!IsSupportedEquipmentSlot(equipmentSlot))
        return ApplicationResult::InvalidSlot;
    if (IsWeaponEquipmentSlot(equipmentSlot) && !config.hideWeapons)
        return ApplicationResult::HideWeaponsDisabled;
    Item* target = player->GetItemByPos(INVENTORY_SLOT_BAG_0, equipmentSlot);
    if (!target || target->GetOwnerGUID() != player->GetGUID())
        return ApplicationResult::TargetMissing;

    AppearanceOverride appearanceOverride{ target->GetGUID().GetCounter(), player->GetGUID().GetCounter(),
        0, {}, OverrideState::Hidden };
    CharacterDatabase.DirectExecute(
        "INSERT INTO `native_transmog_item_override` "
        "(`item_guid`, `owner_guid`, `override_state`, `appearance_item`, `display_id`, `item_class`, "
        "`item_subclass`, `inventory_type`, `applied_at`) VALUES ({}, {}, {}, 0, 0, 0, 0, 0, CURRENT_TIMESTAMP) "
        "ON DUPLICATE KEY UPDATE `owner_guid` = VALUES(`owner_guid`), `override_state` = VALUES(`override_state`), "
        "`appearance_item` = 0, `display_id` = 0, `item_class` = 0, `item_subclass` = 0, "
        "`inventory_type` = 0, `applied_at` = CURRENT_TIMESTAMP",
        appearanceOverride.itemGuid, appearanceOverride.ownerGuid,
        static_cast<std::uint32_t>(appearanceOverride.state));
    {
        std::lock_guard<std::mutex> lock(_mutex);
        _overrides[appearanceOverride.itemGuid] = appearanceOverride;
    }
    player->SetVisibleItemSlot(equipmentSlot, target);
    LOG_INFO("module.native_transmog", "Hid item {} in equipment slot {} for character {}.",
        appearanceOverride.itemGuid, equipmentSlot, appearanceOverride.ownerGuid);
    return ApplicationResult::Ok;
}

ApplicationResult ApplicationService::Remove(Player* player, std::uint8_t equipmentSlot,
    ApplicationAuthorization authorization)
{
    {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_config.enabled)
            return ApplicationResult::Disabled;
        if (!_databaseAvailable)
            return ApplicationResult::DatabaseUnavailable;
    }
    if (!Authorized(player, authorization))
        return ApplicationResult::Unauthorized;
    if (!IsSupportedEquipmentSlot(equipmentSlot))
        return ApplicationResult::InvalidSlot;
    Item* target = player->GetItemByPos(INVENTORY_SLOT_BAG_0, equipmentSlot);
    if (!target || target->GetOwnerGUID() != player->GetGUID())
        return ApplicationResult::TargetMissing;
    ObjectGuid::LowType itemGuid = target->GetGUID().GetCounter();
    {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_overrides.find(itemGuid) == _overrides.end())
            return ApplicationResult::NoOverride;
    }
    CharacterDatabase.DirectExecute(
        "DELETE FROM `native_transmog_item_override` WHERE `item_guid` = {} AND `owner_guid` = {}",
        itemGuid, player->GetGUID().GetCounter());
    EraseCached(itemGuid);
    player->SetVisibleItemSlot(equipmentSlot, target);
    LOG_INFO("module.native_transmog", "Removed appearance override from item {} owned by character {}.",
        itemGuid, player->GetGUID().GetCounter());
    return ApplicationResult::Ok;
}

bool ApplicationService::GetOverride(Item const* item, AppearanceOverride& appearanceOverride) const
{
    if (!item)
        return false;
    std::lock_guard<std::mutex> lock(_mutex);
    auto found = _overrides.find(item->GetGUID().GetCounter());
    if (found == _overrides.end())
        return false;
    appearanceOverride = found->second;
    return true;
}

ApplicationResult ApplicationService::ValidateForTarget(Player const* player, ItemTemplate const* target,
    ItemTemplate const* source, std::uint8_t equipmentSlot) const
{
    ApplicationConfig config;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_config.enabled)
            return ApplicationResult::Disabled;
        config = _config;
    }
    return CompatibilityValidator::Validate(player, target, source, config, equipmentSlot);
}

void ApplicationService::LoadPlayer(Player* player)
{
    if (!player)
        return;
    ApplicationConfig config;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_config.enabled || !_databaseAvailable)
            return;
        config = _config;
    }

    std::vector<ObjectGuid::LowType> invalid;
    std::vector<AppearanceOverride> loaded;
    if (QueryResult result = CharacterDatabase.Query(
        "SELECT `item_guid`, `override_state`, `appearance_item`, `display_id`, `item_class`, `item_subclass`, "
        "`inventory_type` "
        "FROM `native_transmog_item_override` WHERE `owner_guid` = {}", player->GetGUID().GetCounter()))
    {
        do
        {
            Field* fields = result->Fetch();
            AppearanceOverride appearanceOverride;
            appearanceOverride.itemGuid = fields[0].Get<ObjectGuid::LowType>();
            appearanceOverride.ownerGuid = player->GetGUID().GetCounter();
            std::uint8_t state = fields[1].Get<std::uint8_t>();
            if (state > static_cast<std::uint8_t>(OverrideState::Hidden))
            {
                invalid.push_back(appearanceOverride.itemGuid);
                continue;
            }
            appearanceOverride.state = static_cast<OverrideState>(state);
            appearanceOverride.appearanceItem = fields[2].Get<std::uint32_t>();
            appearanceOverride.appearance = { fields[3].Get<std::uint32_t>(), fields[4].Get<std::uint8_t>(),
                fields[5].Get<std::uint8_t>(), fields[6].Get<std::uint8_t>() };
            Item* target = player->GetItemByGuid(ObjectGuid::Create<HighGuid::Item>(appearanceOverride.itemGuid));
            bool valid = target && target->GetOwnerGUID() == player->GetGUID();
            std::uint8_t equipmentSlot = target && target->IsEquipped() ? target->GetSlot() :
                static_cast<std::uint8_t>(NULL_SLOT);
            if (appearanceOverride.state == OverrideState::Appearance)
            {
                ItemTemplate const* source = sObjectMgr->GetItemTemplate(appearanceOverride.appearanceItem);
                AppearanceKey resolved;
                valid = valid && CollectionService::ResolveAppearance(source, resolved) &&
                    resolved == appearanceOverride.appearance &&
                    CompatibilityValidator::Validate(player, target->GetTemplate(), source, config, equipmentSlot) ==
                        ApplicationResult::Ok;
            }
            if (!valid)
            {
                invalid.push_back(appearanceOverride.itemGuid);
                continue;
            }
            loaded.push_back(appearanceOverride);
        } while (result->NextRow());
    }
    {
        std::lock_guard<std::mutex> lock(_mutex);
        for (AppearanceOverride const& appearanceOverride : loaded)
            _overrides[appearanceOverride.itemGuid] = appearanceOverride;
    }
    for (ObjectGuid::LowType itemGuid : invalid)
        CharacterDatabase.DirectExecute("DELETE FROM `native_transmog_item_override` WHERE `item_guid` = {}", itemGuid);
    for (std::uint8_t slot = EQUIPMENT_SLOT_START; slot < EQUIPMENT_SLOT_END; ++slot)
        if (Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
            player->SetVisibleItemSlot(slot, item);
}

void ApplicationService::ReleasePlayer(Player const* player)
{
    if (!player)
        return;
    ObjectGuid::LowType ownerGuid = player->GetGUID().GetCounter();
    std::lock_guard<std::mutex> lock(_mutex);
    for (auto itr = _overrides.begin(); itr != _overrides.end();)
        itr = itr->second.ownerGuid == ownerGuid ? _overrides.erase(itr) : std::next(itr);
}

void ApplicationService::ApplyVisible(Player* player, std::uint8_t equipmentSlot, Item* item) const
{
    if (!player || !item || !IsSupportedEquipmentSlot(equipmentSlot))
        return;
    std::lock_guard<std::mutex> lock(_mutex);
    auto found = _overrides.find(item->GetGUID().GetCounter());
    if (found == _overrides.end() || found->second.ownerGuid != player->GetGUID().GetCounter())
        return;
    if (found->second.state == OverrideState::Hidden)
    {
        if (!IsWeaponEquipmentSlot(equipmentSlot) || _config.hideWeapons)
            player->SetUInt32Value(PLAYER_VISIBLE_ITEM_1_ENTRYID + (equipmentSlot * 2), 0);
        return;
    }
    ItemTemplate const* source = sObjectMgr->GetItemTemplate(found->second.appearanceItem);
    if (CompatibilityValidator::Validate(player, item->GetTemplate(), source, _config, equipmentSlot) ==
        ApplicationResult::Ok)
        player->SetUInt32Value(PLAYER_VISIBLE_ITEM_1_ENTRYID + (equipmentSlot * 2), found->second.appearanceItem);
}

void ApplicationService::EraseCached(ObjectGuid::LowType itemGuid)
{
    std::lock_guard<std::mutex> lock(_mutex);
    _overrides.erase(itemGuid);
}

void ApplicationService::RemoveForTransferredItem(Item const* item)
{
    if (!item)
        return;
    ObjectGuid::LowType itemGuid = item->GetGUID().GetCounter();
    {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_overrides.find(itemGuid) == _overrides.end())
            return;
    }
    CharacterDatabase.DirectExecute("DELETE FROM `native_transmog_item_override` WHERE `item_guid` = {}", itemGuid);
    EraseCached(itemGuid);
}

void ApplicationService::RemoveForDeletedItem(CharacterDatabaseTransaction transaction,
    ObjectGuid::LowType itemGuid)
{
    EraseCached(itemGuid);
    if (transaction)
        transaction->Append("DELETE FROM `native_transmog_item_override` WHERE `item_guid` = {}", itemGuid);
    else
        CharacterDatabase.DirectExecute(
            "DELETE FROM `native_transmog_item_override` WHERE `item_guid` = {}", itemGuid);
}

void ApplicationService::ResolveMirrorImage(Item const* item, std::uint32_t& displayId) const
{
    if (!item || !item->IsEquipped())
        return;
    AppearanceOverride appearanceOverride;
    ApplicationConfig config;
    {
        std::lock_guard<std::mutex> lock(_mutex);
        auto found = _overrides.find(item->GetGUID().GetCounter());
        if (found == _overrides.end())
            return;
        appearanceOverride = found->second;
        config = _config;
    }
    Player* owner = item->GetOwner();
    if (!owner || appearanceOverride.ownerGuid != owner->GetGUID().GetCounter())
        return;
    if (appearanceOverride.state == OverrideState::Hidden)
    {
        if (!IsWeaponEquipmentSlot(item->GetSlot()) || config.hideWeapons)
            displayId = 0;
        return;
    }
    ItemTemplate const* source = sObjectMgr->GetItemTemplate(appearanceOverride.appearanceItem);
    if (CompatibilityValidator::Validate(owner, item->GetTemplate(), source, config, item->GetSlot()) ==
            ApplicationResult::Ok)
        displayId = appearanceOverride.appearance.displayId;
}

char const* ApplicationService::ResultName(ApplicationResult result)
{
    switch (result)
    {
        case ApplicationResult::Ok: return "ok";
        case ApplicationResult::Disabled: return "application disabled";
        case ApplicationResult::DatabaseUnavailable: return "application database unavailable";
        case ApplicationResult::Unauthorized: return "no authorized Transmogrifier session";
        case ApplicationResult::InvalidSlot: return "invalid equipment slot";
        case ApplicationResult::TargetMissing: return "target equipment item missing";
        case ApplicationResult::SourceMissing: return "appearance source item missing";
        case ApplicationResult::AppearanceIneligible: return "appearance source is ineligible";
        case ApplicationResult::AppearanceNotCollected: return "appearance is not collected";
        case ApplicationResult::ClassRestricted: return "appearance is restricted from this class";
        case ApplicationResult::RaceRestricted: return "appearance is restricted from this race";
        case ApplicationResult::RequiredSkillRestricted: return "appearance required skill is missing";
        case ApplicationResult::RequiredSpellRestricted: return "appearance required spell is missing";
        case ApplicationResult::ArmorProficiencyRestricted: return "armor proficiency is missing";
        case ApplicationResult::WeaponProficiencyRestricted: return "weapon proficiency is missing";
        case ApplicationResult::ItemClassMismatch: return "armor/weapon class mismatch";
        case ApplicationResult::ArmorSubclassMismatch: return "armor subclass mismatch";
        case ApplicationResult::InventoryTypeMismatch: return "equipment inventory type mismatch";
        case ApplicationResult::WeaponSubclassMismatch: return "weapon subclass mismatch";
        case ApplicationResult::TwoHandOnOneHandDisabled: return "two-hand appearance on one-hand target is disabled";
        case ApplicationResult::OneHandOnTwoHandDisabled: return "one-hand appearance on two-hand target is disabled";
        case ApplicationResult::HideWeaponsDisabled: return "weapon hiding is disabled";
        case ApplicationResult::NoOverride: return "item has no appearance override";
        default: return "unknown result";
    }
}

bool ApplicationService::CanHide(std::uint8_t equipmentSlot) const
{
    std::lock_guard<std::mutex> lock(_mutex);
    return IsSupportedEquipmentSlot(equipmentSlot) && (!IsWeaponEquipmentSlot(equipmentSlot) || _config.hideWeapons);
}
}
