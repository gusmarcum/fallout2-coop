#ifndef FALLOUT_SERVER_TRADE_H_
#define FALLOUT_SERVER_TRADE_H_

namespace fallout {

struct Object;

// Player-to-player trade (co-op). Server-owned, like a merchant barter, with two
// differences that shape everything below:
//
//   * BOTH sides are players, so nobody prices anything. Each party puts goods on
//     its own table, locks the table with the Offer button, and when both are
//     locked the server asks each of them, in vanilla's yes/no box, whether they
//     accept exactly what is on the two tables. Two yeses swap the tables; one no
//     ends the trade with everything back where it came from. A locked table
//     cannot be changed, and nothing at all can change once the question is out,
//     so what a player reads in the box is what they get.
//
//   * The world is NOT parked. A merchant trade nests inside the dialog
//     interpreter's call stack and has to block the tick; this one is a small
//     state machine driven by verbs and serviced once per drain, so the other
//     players keep playing while two of them shop. The price of that freedom is a
//     set of bail conditions the tick watches (combat, a leaver, a death, a map
//     change, a reload, another modal claiming the server) — every one of them
//     sweeps the tables back to their owners before closing.
//
// Entry: TALK on another player (server_control.cc) walks the proposer over and
// calls serverTradePropose; the target gets an addressed prompt and answers with
// the `answer` verb. The trade's own verbs are the barter verbs (boffer / bunoffer
// / bcommit / bdone / bcancel), which is what lets the viewer reuse the vanilla
// trade screen unchanged; `btake` is refused, the other side has to offer.

// TALK on a player fired (the proposer is adjacent). Sends the target the
// invitation, or tells the proposer why not.
void serverTradePropose(Object* proposer, Object* target);

// A barter verb from `actor`. Returns true if a player trade consumed it (or
// refused it on the trade's behalf); false when no player trade involves this
// actor, so the caller can fall through to the merchant-barter handling.
bool serverTradeVerb(Object* actor, int sessionId, const char* verb, int pid, int quantity);

// `answer <promptId> <0|1>` from `actor`. Returns true if a live prompt of the
// trade's matched (invitation or accept); false for anything stale.
bool serverTradeAnswer(Object* actor, int promptId, bool yes);

// True while two players have the trade screen open (tables hold goods, so the
// world must not be saved or reloaded around it).
bool serverTradeActive();

// True while an invitation is waiting for its answer.
bool serverTradePending();

// True if `actor` is a party to the open trade or the pending invitation.
bool serverTradeInvolves(Object* actor);

// Service the trade: timeouts, liveness, bail conditions. Called from
// serverControlBeginDrain, which runs every main-phase beat AND inside every
// modal pump — the latter is what lets a conversation or a cutscene that starts
// under an open trade end it promptly (the tables go back, the screens close).
void serverTradeTick();

// End whatever is open, sweeping the tables back. `why` is shown to the parties.
// Used before a world reload and by the modal entry points.
void serverTradeCancel(const char* why);

} // namespace fallout

#endif /* FALLOUT_SERVER_TRADE_H_ */
