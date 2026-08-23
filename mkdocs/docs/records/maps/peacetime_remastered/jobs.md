# Jobs

### Jobs {: #peacetime-remastered-jobs}

#### Gunnery Qualification {: #peacetime-remastered-jobs-job-gunnery}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Gunnery Qualification |
| On complete | toast Job complete: Gunnery Qualification |
| Done when | signal 5 drone_down |
| Reward | 200 credits |

Weapons drill: clear all the condemned hulks off the gunnery range. Destroying one qualifies it - so does talking one down: knock a hulk's shields below half and Comms can hail it and demand its surrender, which counts the same.

#### Rock Breakers {: #peacetime-remastered-jobs-job-rocks}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Rock Breakers |
| On complete | toast Job complete: Rock Breakers |
| Done when | signal 4 rock_cleared |
| Reward | 150 credits |

Clear the hazard asteroids from the shipping lane. The field is marked on the map as Hazard Rock Field - Science can select the marker at its centre to put the crew on it.

#### Board the Poacher {: #peacetime-remastered-jobs-job-poacher}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Board the Poacher |
| On complete | toast Job complete: Board the Poacher |
| Done when | signal poacher_boarded |
| Fail on signal | poacher_killed |
| Reward | 300 credits |

The trawler J19 Jenny is working the belt unregistered. Disable her (drop her shields below 50%) and demand her surrender. Do NOT destroy her.

#### Mercy Run {: #peacetime-remastered-jobs-job-mercy}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Mercy Run |
| On complete | toast Job complete: Mercy Run |
| Done when | signal mercy_reached |
| Fails when | 6 minutes |
| Speaker | mercy_lm |
| Signal says | MAYDAY - AUTOMATED BEACON. LIFE SUPPORT {time} FROM FAILURE. |
| Reward | 250 credits |
| Penalty | 100 credits |

A shuttle is adrift and losing life support. Reach it before the clock runs out.

#### Customs Patrol {: #peacetime-remastered-jobs-job-customs}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Customs Patrol |
| On complete | toast Job complete: Customs Patrol |
| Done when | signal 4 customs_cleared |
| Reward | 120 credits |

Hail and clear the civilian traders for transit. They keep to the Shipping Lane, marked on the map.

#### Anomaly Survey {: #peacetime-remastered-jobs-job-survey}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Anomaly Survey |
| On complete | toast Job complete: Anomaly Survey |
| Done when | scan 3 anomaly |
| Scan says | Survey logged: a stable subspace distortion. No threat - filed with the science log. |
| Reward | 130 credits |

Have Science scan the sensor anomalies and log them.

#### Sensor Net {: #peacetime-remastered-jobs-job-sensor-net}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Sensor Net |
| On complete | toast Job complete: Sensor Net |
| Done when | signal 3 sensor_deployed |
| Reward | 220 credits |

Establish a sensor picket. Each Sensor Beacon costs 8 salvage: tow a hulk to the Refinery Platform and it pays out in processed material, or shoot open a wreck and collect the cache. A station market will sell you salvage too, at a price. Engineering fabricates the beacons on the Fabricate tab and delivers them to Weapons, who deploys three across the patrol lanes.

#### Recover Lost Probes {: #peacetime-remastered-jobs-job-probes}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Recover Lost Probes |
| On complete | toast Job complete: Recover Lost Probes |
| Done when | signal 3 probe_recovered |
| Reward | 160 credits |

Three old survey probes have gone adrift in the sector. Fly your ship over each one to bring it aboard - a recovered probe also tops up your beacon tube.

#### Clear the Grazing Herd {: #peacetime-remastered-jobs-job-herd}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Clear the Grazing Herd |
| On complete | toast Job complete: Clear the Grazing Herd |
| Done when | signal herd_cleared |
| Reward | 180 credits |

A pod of grazers has drifted into a shipping lane. Do NOT fire on them - they turn hostile if provoked. A Bio Beacon costs 5 salvage and 1 bio sample. Salvage comes from the Refinery Platform, from wrecks, or from a station market; a bio sample is recovered from a dead space creature - a station will sell you one if the lane is quiet. Set the beacon to REPEL grazers, deploy it among the pod, and drive them clear.

#### Bait the Ravener {: #peacetime-remastered-jobs-job-ravener}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Bait the Ravener |
| On complete | toast Job complete: Bait the Ravener |
| Done when | signal predator_baited |
| Reward | 350 credits |

A Ravener is loose in the lanes. It FEEDS on weapon fire - shooting only heals it - so do not engage. A Bio Beacon costs 5 salvage and 1 bio sample (see Salvage Sweep, or open a wreck). Set it to ATTRACT the ravener, deploy it beside the black hole, and let the hole do the rest.

#### Tow the Barge {: #peacetime-remastered-jobs-job-barge}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Tow the Barge |
| On complete | toast Job complete: Tow the Barge |
| Done when | signal barge_delivered |
| Reward | 300 credits |

A power-dead ore barge is adrift in the shipping lane with no drive of its own. Grav-tether it and tow it back to DS 1.

#### Salvage Sweep {: #peacetime-remastered-jobs-job-salvage}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Salvage Sweep |
| On complete | toast Job complete: Salvage Sweep |
| Done when | signal 3 salvage_delivered |
| Reward | 240 credits |

Wrecked hulls are cluttering the lane. Grav-tether each salvage hulk and tow it to the Refinery Platform for processing - the refinery pays in credits AND in salvage, which is what Engineering's Fabricator runs on.

#### Rescue the Lifepod {: #peacetime-remastered-jobs-job-lifepod}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Rescue the Lifepod |
| On complete | toast Job complete: Rescue the Lifepod |
| Done when | signal lifepod_delivered |
| Fails when | 5 minutes |
| Reward | 320 credits |
| Penalty | 150 credits |

A lifepod is tumbling out of a wreck field with its beacon failing. Grav-tether it and tow it to DS 1 before life support runs out.

#### Reposition the Relay {: #peacetime-remastered-jobs-job-relay}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Reposition the Relay |
| On complete | toast Job complete: Reposition the Relay |
| Done when | signal relay_placed |
| Reward | 200 credits |

A comms relay has drifted off station. Grav-tether it and tow it to its marked position in the lane, then let it settle.

#### Picket Line {: #peacetime-remastered-jobs-job-picket}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Picket Line |
| On complete | toast Job complete: Picket Line |
| Done when | signal 3 picket_placed |
| Reward | 320 credits |

DS 1 wants the lane junction covered by automated guns. Fleet drops turret kits alongside you - grav-tether each crate, tow it into the marked Picket Line zone, release it, and unfold it there. Any turret kind counts; a kit deployed outside the zone does not. The picket is only finished while the guns are still standing.

#### The Ghost Freighter {: #peacetime-remastered-jobs-job-ghost}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: The Ghost Freighter |
| On complete | toast Job complete: The Ghost Freighter |
| Reward | 400 credits |

The freighter SS Meridian has gone silent and is drifting toward a black hole. Work the steps in order - the case pays on completion.

##### Hail the Meridian {: #peacetime-remastered-jobs-job-ghost-hail}

| Fact | Value |
|---|---|
| Starts when | revealed |

COMMS: hail the silent freighter.

##### Scan the Derelict {: #peacetime-remastered-jobs-job-ghost-scan}

| Fact | Value |
|---|---|
| Starts when | revealed |

SCIENCE: scan her to assess the situation.

##### Tow Clear of the Hole {: #peacetime-remastered-jobs-job-ghost-clear}

| Fact | Value |
|---|---|
| Starts when | revealed |

WEAPONS / HELM: grav-tether her and tow her clear of the black hole.

##### Tow Her Home {: #peacetime-remastered-jobs-job-ghost-home}

| Fact | Value |
|---|---|
| Starts when | revealed |

WEAPONS / HELM: tow her back to DS 1.

#### Sweep and Recover {: #peacetime-remastered-jobs-job-sweep}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Sweep and Recover |
| On complete | toast Job complete: Sweep and Recover |
| Reward | 380 credits |

Run a sensor sweep and recover what it finds. Work the steps in order.

##### Deploy the Picket {: #peacetime-remastered-jobs-job-sweep-deploy}

| Fact | Value |
|---|---|
| Starts when | revealed |

ENGINEERING / WEAPONS: fabricate a Sensor Beacon on the Fabricate tab and deploy it.

##### Scan the Contact {: #peacetime-remastered-jobs-job-sweep-scan}

| Fact | Value |
|---|---|
| Starts when | revealed |

SCIENCE: scan the contact the picket flags.

##### Recover the Find {: #peacetime-remastered-jobs-job-sweep-recover}

| Fact | Value |
|---|---|
| Starts when | revealed |

WEAPONS / HELM: grav-tether the find and tow it to DS 1.

#### Cache in the Rocks {: #peacetime-remastered-jobs-job-cache}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Cache in the Rocks |
| On complete | toast Job complete: Cache in the Rocks |
| Reward | 360 credits |

A tipster says contraband is stashed in an asteroid cluster. Work the steps in order.

##### Get the Tip {: #peacetime-remastered-jobs-job-cache-tip}

| Fact | Value |
|---|---|
| Starts when | revealed |

COMMS: hail the loitering tipster for the drop location.

##### Find the Cache {: #peacetime-remastered-jobs-job-cache-find}

| Fact | Value |
|---|---|
| Starts when | revealed |

SCIENCE: scan the rock cluster to find the loaded one.

##### Recover the Pod {: #peacetime-remastered-jobs-job-cache-recover}

| Fact | Value |
|---|---|
| Starts when | revealed |

WEAPONS / HELM: grav-tether the shielded pod out and tow it to DS 1.

#### Herd on the Lane {: #peacetime-remastered-jobs-job-herd-arc}

| Fact | Value |
|---|---|
| On accept | toast Job accepted: Herd on the Lane |
| On complete | toast Job complete: Herd on the Lane |
| Reward | 340 credits |

A grazer pod has drifted into a shipping lane. Work the steps in order. Do NOT fire on the grazers - they retaliate if provoked.

##### Scan the Pod {: #peacetime-remastered-jobs-job-herd-arc-scan}

| Fact | Value |
|---|---|
| Starts when | revealed |

SCIENCE: scan the grazer pod.

##### Warn the Convoy {: #peacetime-remastered-jobs-job-herd-arc-warn}

| Fact | Value |
|---|---|
| Starts when | revealed |

COMMS: warn the civilian convoy to hold.

##### Deploy a Repel Beacon {: #peacetime-remastered-jobs-job-herd-arc-repel}

| Fact | Value |
|---|---|
| Starts when | revealed |

ENGINEERING / WEAPONS: fabricate a Bio Beacon set to REPEL and deploy it to drive the pod clear.

##### Free the Snared Grazer {: #peacetime-remastered-jobs-job-herd-arc-free}

| Fact | Value |
|---|---|
| Starts when | revealed |

WEAPONS / HELM: grav-tether the drift netting off the snared grazer to free it.
