# Florbin Case

### Florbin Case {: #peacetime-remastered-florbin-case}

#### The Florbin Affair {: #peacetime-remastered-florbin-case-florbin}

| Fact | Value |
|---|---|
| Scope | shared |
| Starts when | at once |

!!! abstract "Author note"

    The spine of the map. Four steps, each one a different console's problem.

Ambassador Florbin has been kidnapped and smuggled out in a cargo container. Follow the cargo trail, find him, and bring him home to DS 1 - alive.

##### Take the Case {: #peacetime-remastered-florbin-case-florbin-brief}

| Fact | Value |
|---|---|
| Starts when | revealed |
| Then | `reveal` [Identify the Kidnapper](#peacetime-remastered-florbin-case-florbin-trail) |
| Action | \- ds1 hails ds1_brief |
| Scope | shared |

!!! abstract "Author note"

    Opening. DS 1 hails the CREW; nothing else is revealed until this lands.  \`Starts when: revealed\` rather than \`at once\` because \`Action:\` fires the moment a beat goes active, and the call has to land AFTER the Admiral explains why anyone would be calling. florbin_case.mast reveals this step when that message has been read.

DS 1 is calling. Answer the incoming hail on comms to open the investigation.

##### Identify the Kidnapper {: #peacetime-remastered-florbin-case-florbin-trail}

| Fact | Value |
|---|---|
| Done when | signal suspect_identified |
| Starts when | revealed |
| Then | `reveal` [Subdue the Kidnapper](#peacetime-remastered-florbin-case-florbin-subdue) |
| Scope | shared |

!!! abstract "Author note"

    Midpoint. Science work - the crew learns Florbin is alive and aboard.

Follow the cargo trail: interview stations and bio-scan suspect holds to find which ship is hiding the ambassador.

##### Subdue the Kidnapper {: #peacetime-remastered-florbin-case-florbin-subdue}

| Fact | Value |
|---|---|
| Done when | signal kidnapper_subdued |
| Starts when | revealed |
| Then | `reveal` [Recover and Return Florbin](#peacetime-remastered-florbin-case-florbin-recover) |
| Scope | shared |

!!! abstract "Author note"

    The trap. Weapons must NOT solve this the usual way; that is the whole beat.

Do NOT destroy the ship - the ambassador is aboard. Drop its shields below 50% (or use a secret codecase) to force its surrender.

##### Recover and Return Florbin {: #peacetime-remastered-florbin-case-florbin-recover}

| Fact | Value |
|---|---|
| Done when | signal florbin_delivered |
| Starts when | revealed |
| Scope | shared |

!!! abstract "Author note"

    Payoff. Helm and docking; deliberately quiet after the standoff.

Collect the escape pod and dock it at DS 1.

##### Keep Florbin Alive {: #peacetime-remastered-florbin-case-florbin-alive}

| Fact | Value |
|---|---|
| Starts when | at once |
| Scope | shared |
| Fail on signal | `florbin_killed` |

!!! abstract "Author note"

    The stake, running underneath all four steps. Never listed as a task.

The case is lost if the ship carrying the ambassador is destroyed before he escapes.
