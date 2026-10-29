#ifndef MOD_NATIVE_TRANSMOG_QUEST_COLLECTION_H
#define MOD_NATIVE_TRANSMOG_QUEST_COLLECTION_H

#include "NativeTransmogCollection.h"

#include <cstdint>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>

class Player;
class Quest;

namespace native_transmog
{
struct QuestCollectionStats
{
    std::uint32_t completedQuestsExamined = 0;
    std::uint32_t eligibleAppearances = 0;
    std::uint32_t alreadyCollected = 0;
    std::uint32_t newAppearances = 0;
    std::uint32_t unresolvedRecords = 0;
    std::uint32_t ineligibleItems = 0;
};

QuestCollectionStats CollectQuestRewardAppearances(Player* player, Quest const* quest,
    AcquisitionSource source, bool preview,
    std::unordered_set<AppearanceKey, AppearanceKeyHash>* seenAppearances = nullptr,
    std::vector<CollectionUnlockRequest>* pendingUnlocks = nullptr);

enum class BackfillState : std::uint8_t
{
    NotStarted,
    Running,
    Complete,
    Failed
};

struct QuestBackfillStatus
{
    BackfillState state = BackfillState::NotStarted;
    bool preview = true;
    std::uint32_t targetCharacter = 0;
    std::string targetName;
    CollectionOwner owner;
    QuestCollectionStats stats;
    std::uint32_t lastQuest = 0;
    std::string error;
};

class QuestBackfillService final
{
public:
    static QuestBackfillService& Instance();

    void Configure(bool enabled);
    bool Start(Player* target, bool preview, std::string& error);
    void Update(Player* player, std::uint32_t diff);
    QuestBackfillStatus Status(Player const* target) const;
    static char const* StateName(BackfillState state);

private:
    struct Job
    {
        QuestBackfillStatus status;
        std::uint32_t updateTimer = 0;
        std::unordered_set<AppearanceKey, AppearanceKeyHash> seenAppearances;
    };

    QuestBackfillService() = default;
    void ProcessBatch(Player* player, Job& job);

    mutable std::mutex _mutex;
    bool _enabled = true;
    std::unordered_map<std::uint32_t, Job> _jobs;
};
}

#endif
