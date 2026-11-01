# Stale-DM-replay loops: break them on the board, never in the DM

A bot DM relay can deliver a snapshot minutes old, and repeated crossings can make another lane
re-assert a premise you already corrected (e.g. a merged PR described as "still running"). Each reply
you send back into the crossing feeds the loop.

Rule:

1. Reply ONCE with the measured facts and the head sha. Do not re-explain on the next replay.
2. Put the durable answer where the other lane says authority lives — usually a comment ON THE
   ISSUE/PR (board), or the finding issue itself (body + addendum + audit-complete record).
3. Then STOP. A further identical DM is ping-pong, and discipline forbids it. If the lane named
   "the board is the authority", your board comment already answers it under any stale wedge.
4. Never re-file or re-run to satisfy a loop (e.g. do not open a second audit issue, #824). If the
   finding is filed, cite its number + comment id and end the turn.

Signals you are in a loop: the same premise arrives a 2nd/3rd/4th time despite your correction; the
lane's message quotes a timestamp older than your last measurement; the lane says "I will not repeat
this again" while still repeating it. Treat a background `--run-delivery` notification as the lane's
own action log — no reply owed.
