#ifndef MOD_NATIVE_TRANSMOG_APPLICATION_H
#define MOD_NATIVE_TRANSMOG_APPLICATION_H

#include "NativeTransmogCollection.h"
#include "DatabaseEnvFwd.h"
#include "ObjectGuid.h"

#include <cstdint>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

class Item;
class Player;
struct ItemTemplate;

namespace native_transmog
{
struct ApplicationConfig
{
    bool enabled = true;
    bool allowTwoHandAppearanceOnOneHand = false;
    bool allowOneHandAppearanceOnTwoHand = false;
    bool hideWeapons = false;
};

enum class OverrideState : std::uint8_t
{
    Appearance = 0,
    Hidden = 1
};

enum class ApplicationAuthorization : std::uint8_t
{
    NpcSession,
    GmDiagnostic
};

enum class ApplicationResult : std::uint8_t
{
    Ok,
    Disabled,
    DatabaseUnavailable,
    Unauthorized,
    InvalidSlot,
    TargetMissing,
    SourceMissing,
    AppearanceIneligible,
    AppearanceNotCollected,
    ClassRestricted,
    RaceRestricted,
    RequiredSkillRestricted,
    RequiredSpellRestricted,
    ArmorProficiencyRestricted,
    WeaponProficiencyRestricted,
    ItemClassMismatch,
    ArmorSubclassMismatch,
    InventoryTypeMismatch,
    WeaponSubclassMismatch,
    TwoHandOnOneHandDisabled,
    OneHandOnTwoHandDisabled,
    HideWeaponsDisabled,
    NoOverride
};

struct AppearanceOverride
{
    ObjectGuid::LowType itemGuid = 0;
    ObjectGuid::LowType ownerGuid = 0;
    std::uint32_t appearanceItem = 0;
    AppearanceKey appearance;
    OverrideState state = OverrideState::Appearance;
};

struct BatchAppearanceSelection
{
    std::uint8_t equipmentSlot = 0;
    OverrideState state = OverrideState::Appearance;
    std::uint32_t appearanceItem = 0;
};

struct BatchValidation
{
    std::uint8_t equipmentSlot = 0;
    ApplicationResult result = ApplicationResult::Ok;
};

bool IsSupportedEquipmentSlot(std::uint8_t equipmentSlot);
bool IsWeaponEquipmentSlot(std::uint8_t equipmentSlot);
std::vector<std::uint8_t> CompatibleWeaponSubclasses(ItemTemplate const* target);

class CompatibilityValidator final
{
public:
    static ApplicationResult Validate(Player const* player, ItemTemplate const* target,
        ItemTemplate const* source, ApplicationConfig const& config, std::uint8_t equipmentSlot = 0xFF);
};

class ApplicationService final
{
public:
    static ApplicationService& Instance();

    void Configure(ApplicationConfig const& config);
    bool Initialize();
    bool IsEnabled() const;
    bool IsDatabaseAvailable() const;

    ApplicationResult Apply(Player* player, std::uint8_t equipmentSlot, std::uint32_t appearanceItem,
        ApplicationAuthorization authorization);
    ApplicationResult Hide(Player* player, std::uint8_t equipmentSlot,
        ApplicationAuthorization authorization);
    ApplicationResult Remove(Player* player, std::uint8_t equipmentSlot,
        ApplicationAuthorization authorization);
    bool GetOverride(Item const* item, AppearanceOverride& appearanceOverride) const;
    ApplicationResult ValidateForTarget(Player const* player, ItemTemplate const* target,
        ItemTemplate const* source, std::uint8_t equipmentSlot) const;
    std::vector<BatchValidation> ValidateBatch(Player* player,
        std::vector<BatchAppearanceSelection> const& selections,
        ApplicationAuthorization authorization) const;
    ApplicationResult ApplyBatch(Player* player,
        std::vector<BatchAppearanceSelection> const& selections,
        ApplicationAuthorization authorization);

    void LoadPlayer(Player* player);
    void ReleasePlayer(Player const* player);
    void ApplyVisible(Player* player, std::uint8_t equipmentSlot, Item* item) const;
    void RemoveForTransferredItem(Item const* item);
    void RemoveForDeletedItem(CharacterDatabaseTransaction transaction, ObjectGuid::LowType itemGuid);
    void ResolveMirrorImage(Item const* item, std::uint32_t& displayId) const;
    bool CanHide(std::uint8_t equipmentSlot) const;

    static char const* ResultName(ApplicationResult result);

private:
    ApplicationService() = default;
    bool Authorized(Player* player, ApplicationAuthorization authorization) const;
    void EraseCached(ObjectGuid::LowType itemGuid);

    mutable std::mutex _mutex;
    ApplicationConfig _config;
    bool _databaseAvailable = false;
    std::unordered_map<ObjectGuid::LowType, AppearanceOverride> _overrides;
};
}

#endif
