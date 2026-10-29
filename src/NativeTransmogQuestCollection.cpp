#include "NativeTransmogQuestCollection.h"

#include "DatabaseEnv.h"
#include "ItemTemplate.h"
#include "Log.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QuestDef.h"

#include <vector>

namespace native_transmog
{
namespace
{
constexpr std::uint32_t BackfillBatchSize = 25;
constexpr std::uint32_t BackfillBatchIntervalMs = 100;

void AddReward(Player* player, Quest const* quest, std::uint32_t itemId, AcquisitionSource source,
    bool preview, std::unordered_set<AppearanceKey, AppearanceKeyHash>& seen, QuestCollectionStats& stats,
    std::vector<CollectionUnlockRequest>* pendingUnlocks)
{
    if (!itemId)
        return;

    ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(itemId);
    if (!itemTemplate)
    {
        ++stats.unresolvedRecords;
        return;
    }

    AppearanceKey appearance;
    if (!CollectionService::ResolveAppearance(itemTemplate, appearance))
    {
        ++stats.ineligibleItems;
        return;
    }

    if (!seen.insert(appearance).second)
        return;

    ++stats.eligibleAppearances;
    CollectionService& collection = CollectionService::Instance();
    if (collection.IsCollected(player, appearance))
    {
        ++stats.alreadyCollected;
        return;
    }

    if (preview)
    {
        ++stats.newAppearances;
        return;
    }

    if (pendingUnlocks)
    {
        pendingUnlocks->push_back({ itemTemplate, quest->GetQuestId() });
        return;
    }

    if (collection.Unlock(player, itemTemplate, source, quest->GetQuestId()))
        ++stats.newAppearances;
    else
        ++stats.alreadyCollected;
}
}

QuestCollectionStats CollectQuestRewardAppearances(Player* player, Quest const* quest,
    AcquisitionSource source, bool preview,
    std::unordered_set<AppearanceKey, AppearanceKeyHash>* seenAppearances,
    std::vector<CollectionUnlockRequest>* pendingUnlocks)
{
    QuestCollectionStats stats;
    if (!player || !quest)
    {
        stats.unresolvedRecords = 1;
        return stats;
    }

    std::unordered_set<AppearanceKey, AppearanceKeyHash> localSeen;
    auto& seen = seenAppearances ? *seenAppearances : localSeen;
    for (std::uint32_t itemId : quest->RewardChoiceItemId)
        AddReward(player, quest, itemId, source, preview, seen, stats, pendingUnlocks);
    for (std::uint32_t itemId : quest->RewardItemId)
        AddReward(player, quest, itemId, source, preview, seen, stats, pendingUnlocks);
    return stats;
}

QuestBackfillService& QuestBackfillService::Instance()
{
    static QuestBackfillService service;
    return service;
}

void QuestBackfillService::Configure(bool enabled)
{
    std::lock_guard<std::mutex> lock(_mutex);
    _enabled = enabled;
    // Config reload can change collection scope or source policy. Cancel every
    // in-flight cursor rather than letting one job cross ownership modes.
    _jobs.clear();
}

bool QuestBackfillService::Start(Player* target, bool preview, std::string& error)
{
    if (!target || !target->GetSession())
    {
        error = "The target must be an online, authenticated character.";
        return false;
    }

    CollectionService& collection = CollectionService::Instance();
    if (!collection.IsEnabled() || !collection.IsDatabaseAvailable())
    {
        error = "The Native Transmog collection is disabled or its database table is unavailable.";
        return false;
    }

    std::lock_guard<std::mutex> lock(_mutex);
    if (!_enabled)
    {
        error = "NativeTransmog.Collection.QuestBackfill.Enable is disabled.";
        return false;
    }

    std::uint32_t guid = target->GetGUID().GetCounter();
    auto existing = _jobs.find(guid);
    if (existing != _jobs.end() && existing->second.status.state == BackfillState::Running)
    {
        error = "A quest backfill job is already running for that character.";
        return false;
    }

    Job job;
    job.status.state = BackfillState::Running;
    job.status.preview = preview;
    job.status.targetCharacter = guid;
    job.status.targetName = target->GetName();
    job.status.owner = collection.OwnerFor(target);
    _jobs[guid] = std::move(job);
    return true;
}

void QuestBackfillService::Update(Player* player, std::uint32_t diff)
{
    if (!player)
        return;

    std::lock_guard<std::mutex> lock(_mutex);
    auto found = _jobs.find(player->GetGUID().GetCounter());
    if (found == _jobs.end() || found->second.status.state != BackfillState::Running)
        return;

    Job& job = found->second;
    if (job.updateTimer > diff)
    {
        job.updateTimer -= diff;
        return;
    }
    job.updateTimer = BackfillBatchIntervalMs;
    ProcessBatch(player, job);
}

void QuestBackfillService::ProcessBatch(Player* player, Job& job)
{
    QueryResult result = CharacterDatabase.Query(
        "SELECT `quest` FROM `character_queststatus_rewarded` "
        "WHERE `guid` = {} AND `active` = 1 AND `quest` > {} ORDER BY `quest` LIMIT {}",
        job.status.targetCharacter, job.status.lastQuest, BackfillBatchSize);
    if (!result)
    {
        job.status.state = BackfillState::Complete;
        return;
    }

    std::uint32_t rows = 0;
    std::vector<CollectionUnlockRequest> pendingUnlocks;
    pendingUnlocks.reserve(BackfillBatchSize * (QUEST_REWARD_CHOICES_COUNT + QUEST_REWARDS_COUNT));
    do
    {
        std::uint32_t questId = result->Fetch()[0].Get<std::uint32_t>();
        job.status.lastQuest = questId;
        ++job.status.stats.completedQuestsExamined;
        ++rows;

        Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
        if (!quest)
        {
            ++job.status.stats.unresolvedRecords;
            continue;
        }

        QuestCollectionStats batchStats = CollectQuestRewardAppearances(player, quest,
            AcquisitionSource::QuestBackfill, job.status.preview, &job.seenAppearances,
            job.status.preview ? nullptr : &pendingUnlocks);
        job.status.stats.eligibleAppearances += batchStats.eligibleAppearances;
        job.status.stats.alreadyCollected += batchStats.alreadyCollected;
        job.status.stats.newAppearances += batchStats.newAppearances;
        job.status.stats.unresolvedRecords += batchStats.unresolvedRecords;
        job.status.stats.ineligibleItems += batchStats.ineligibleItems;
    } while (result->NextRow());

    if (!job.status.preview)
        job.status.stats.newAppearances += CollectionService::Instance().UnlockBatch(
            player, pendingUnlocks, AcquisitionSource::QuestBackfill);

    if (rows < BackfillBatchSize)
        job.status.state = BackfillState::Complete;
}

QuestBackfillStatus QuestBackfillService::Status(Player const* target) const
{
    QuestBackfillStatus status;
    if (!target)
        return status;

    std::lock_guard<std::mutex> lock(_mutex);
    auto found = _jobs.find(target->GetGUID().GetCounter());
    return found == _jobs.end() ? status : found->second.status;
}

char const* QuestBackfillService::StateName(BackfillState state)
{
    switch (state)
    {
        case BackfillState::NotStarted: return "not-started";
        case BackfillState::Running: return "running";
        case BackfillState::Complete: return "complete";
        case BackfillState::Failed: return "failed";
        default: return "unknown";
    }
}
}
