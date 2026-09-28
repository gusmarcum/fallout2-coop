#ifndef STAT_H
#define STAT_H

#include "db.h"
#include "obj_types.h"
#include "proto_types.h"
#include "stat_defs.h"

namespace fallout {

#define STAT_ERR_INVALID_STAT (-5)

int statsInit();
int statsReset();
int statsExit();
int statsLoad(File* stream);
int statsSave(File* stream);
int critterGetStat(Object* critter, int stat);
int critterGetBaseStatWithTraitModifier(Object* critter, int stat);
int critterGetBaseStat(Object* critter, int stat);
int critterGetBonusStat(Object* critter, int stat);
int critterSetBaseStat(Object* critter, int stat, int value);
int critterIncBaseStat(Object* critter, int stat);
int critterDecBaseStat(Object* critter, int stat);
int critterSetBonusStat(Object* critter, int stat, int value);
void protoCritterDataResetStats(CritterProtoData* data);
void critterUpdateDerivedStats(Object* critter);
char* statGetName(int stat);
char* statGetDescription(int stat);
char* statGetValueDescription(int value);
// The PC-STAT API (XP, level, karma, unspent skill points). `subject` is the
// player actor whose sheet this reads or writes; nullptr means gDude, which is
// today's behavior and why the ~45 existing call sites need no change. Pass one
// wherever the caller genuinely knows WHOSE experience it is
// (PLAYER_SHEET_DESIGN.md §4 — the subject comes from the call site, never from
// geometry).
int pcGetStat(int pcStat, Object* subject = nullptr);
int pcSetStat(int pcStat, int value, Object* subject = nullptr);
// The level-up award for ONE actor: skill points for the levels in
// (fromLevel, toLevel], and true when the range crossed the free-perk cadence.
// `subject` follows the usual convention — nullptr means gDude.
//
// Called by the XP funnel for whoever earned the levels; the character screen no
// longer awards (it only reconciles a level raised by some other path).
bool pcLevelUpApply(int fromLevel, int toLevel, Object* subject = nullptr);
void pcStatsReset();

// RE-DERIVE the level-up badge (DUDE_STATE_LEVEL_UP_AVAILABLE, the flashing
// character-screen button) for one actor from what it actually MEANS: unspent skill
// points, or a free perk pick still owed.
//
// It is derived and not event-set because vanilla's only clear path is "the player
// closed the character screen" (character_editor.cc) — and a dedicated server has no
// character screen, so a badge switched on at level-up would light that player's
// indicator bar forever. Call it after anything that spends or grants an entitlement.
// [[no-re-derivation-path-bug-class]]
void pcLevelUpBadgeRefresh(Object* subject = nullptr);

// Copy the host's XP / level / karma / unspent skill points into every extra
// player actor's row. Call WITH protoPlayerActorSheetsSeed and
// perkPlayerActorSeedRanks — the three are one operation.
void pcPlayerActorSeedStats();
// ONE slot, for spawn-at-login (see ACCOUNT_IDENTITY_DESIGN.md trap 1).
void pcPlayerActorSeedStatsSlot(int slot);

// One actor's XP / level / karma / unspent skill points
// (PLAYER_SHEET_DESIGN.md §5). Slot 0 is the host's row.
int pcPlayerActorRowWrite(File* stream, int slot);
int pcPlayerActorRowRead(File* stream, int slot);
int pcGetExperienceForNextLevel(Object* subject = nullptr);
int pcGetExperienceForLevel(int level);
char* pcStatGetName(int pcStat);
char* pcStatGetDescription(int pcStat);
int statGetFrmId(int stat);
int statRoll(Object* critter, int stat, int modifier, int* howMuch);
int pcAddExperience(int xp, int* xpGained = nullptr, Object* subject = nullptr);
int pcAddExperienceWithOptions(int xp, bool a2, int* xpGained = nullptr, Object* subject = nullptr);
int pcSetExperience(int a1, Object* subject = nullptr);

// ---- PARTY EXPERIENCE (owner ruling 2026-09-27) -----------------------------
// The party earns as ONE ENTITY: whatever one player earns, every player who is
// playing right now is paid in full. Nothing is split. Each share goes through
// the funnel above for its own actor, so Swift Learner, the level-up award and
// the streamed sheet row stay per player.
//
// This does not replace the subject ruling (PLAYER_SHEET_DESIGN.md section 4).
// The call site still names the earner, because the earner's line is worded
// differently from a teammate's and the steal cap reads the thief's own skill.
// What changes is who is PAID: the sites that award play (kills, give_exp_points,
// skill use, stealing, spotting an encounter) hand the award to pcPartyXpAward,
// which pays everyone who is playing, and then word a line for each share.
//
// Deliberately NOT shared, because they are one character's own business:
// Here and Now (perk.cc), the operator's `xp <slot>` verb and the probe's `xp`.

// True when awards are shared: a dedicated server with more than one player
// actor, unless the operator set F2_PARTY_XP=0. Always false in single-player,
// on a viewer and under the headless probe, so every golden is unchanged.
bool pcPartyXpActive();

// Who is paid for an award that `earner` brought in. Fills `recipients` (room for
// kMaxPlayerActors) and returns how many.
//
// Shared: every seat with a connected player and a body in the world. A downed
// player is included (a teammate revives them, and leaving them out is how two
// characters drift apart); a body whose owner is not connected is not. If nobody
// is connected the earner keeps the award, so XP is never dropped.
//
// Not shared: exactly one entry, `earner` AS GIVEN. nullptr stays nullptr, which
// the funnel reads as gDude and the message layer reads as a broadcast, so a
// caller that loops over the result behaves byte for byte as it did before.
int pcPartyXpRecipients(Object* earner, Object** recipients);

// One player's share of one award: who was paid, and what the funnel actually
// added for them (their own Swift Learner included).
typedef struct PartyXpShare {
    Object* actor;
    int gained;
} PartyXpShare;

// THE pay-out. Every award site that shares calls this and nothing else, so an
// award is paid in exactly one place: ONCE to each recipient, the earner
// included. The earner's own award is not made separately and then topped up
// for the others; it IS one of these shares, which is why nobody can be paid
// twice for the same award.
//
// Fills `shares` (room for kMaxPlayerActors) in slot order and returns how many.
// `what` names the source for the server console, which prints one line per
// award with every share on it.
int pcPartyXpAward(int xp, Object* earner, const char* what, PartyXpShare* shares);

static inline bool statIsValid(int stat)
{
    return stat >= 0 && stat < STAT_COUNT;
}

static inline bool pcStatIsValid(int pcStat)
{
    return pcStat >= 0 && pcStat < PC_STAT_COUNT;
}

} // namespace fallout

#endif /* STAT_H */
