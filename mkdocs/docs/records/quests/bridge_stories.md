# Bridge Stories

## Patrol Briefing {: #story-patrol}

| Fact | Value |
|---|---|
| At start | active |
| Reward | { credits: 100 } |
| On scan | { role: station } |
| Reveal | [Patrol Sweep](#story-patrol-b) |

!!! abstract "Author note"

    Step 1 of 3. Teaches the scan verb before anything depends on it.

Have Science scan this starbase to download the patrol briefing, then proceed to your sweep.

## Patrol Sweep {: #story-patrol-b}

| Fact | Value |
|---|---|
| At start | secret |
| On kill | { role: raider, count: 3 } |
| Reveal | [Report In](#story-patrol-c) |

!!! abstract "Author note"

    Step 2 of 3. The only combat beat; count is low on purpose.

Raiders are working the shipping lanes. Destroy three of them.

## Report In {: #story-patrol-c}

| Fact | Value |
|---|---|
| At start | secret |
| Reward | { credits: 500 } |
| On dock | {} |

!!! abstract "Author note"

    Step 3 of 3. Docking, and the payout that closes the chain.

Dock at a friendly station to file your report and collect the bounty.
