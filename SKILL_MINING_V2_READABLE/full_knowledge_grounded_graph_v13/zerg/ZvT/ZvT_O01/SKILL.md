# ZvT_O01 Economy / Expansion / Ground

## Skill Identity

- Skill ID: ZvT_O01
- Matchup: Zerg vs Terran
- Opening Family: economy / expansion / ground opening
- Method: Knowledge-Grounded Full V13

## Opening Strategy

This opening prioritizes a robust economy and early expansion, with a ground-leaning army composition and moderate production. It is designed as a flexible strategic template, not a fixed build order, allowing adaptation based on live observation of the opponent's actions.

Develop a economy / expansion / ground posture while preserving flexibility for live observation-driven adaptation.

This is a strategic template, not a fixed build order.

## Strategic Characteristics

- Economy: heavy
- Production: moderate
- Technology: light_or_uncertain
- Army direction: ground-leaning

## Strategic Priorities

- Preserve the opening's strategic identity without reproducing a fixed sequence.
- Check current Completed, Under Construction, Active Queues, resources, supply, and prerequisites before choosing exact macro actions.
- Match any adaptation against partial Enemy Intelligence and current Threat Flags.
- Re-evaluate economy, production, technology, and army trade-offs at every decision.

## Decision Nodes

### [POSITIVE] N001 — ZvT Economy/Expansion Ground Opening

**Trigger situation:**  
Early game with heavy economy and expansion posture, ground-oriented army, moderate production, light/uncertain tech. Enemy observed with Marine and Reaper cues, ground posture, heavy tech investment.

**Direction:**  
Continue economy and expansion development, strengthen ground army, maintain production and defense, continue tech investment, with safety checks against early pressure.

**Read for details:** `N001`

---

### [NEGATIVE] N002 — Economy/Expansion Ground Posture with Heavy Tech Investment

**Trigger situation:**  
Early game with heavy economy and expansion posture, moderate production, ground-oriented army, and light/uncertain own technology investment. Opponent shows ground posture with heavy technology investment and possible pressure.

**Risk direction:**  
Avoid neglecting ground army strength in favor of pure economy; avoid over-committing to technology without sufficient army to defend.

**Read for details:** `N002`

---

### [DEFAULT] N003 — ZvT Early Game Ground Macro with Heavy Economy

**Trigger situation:**  
Early game phase with both sides showing ground-oriented, heavy economy postures. Enemy intelligence suggests possible Marine and Reaper presence, while own forces include Zergling and Queen. Production is moderate, technology investment is heavy for opponent and light/uncertain for self.

**Direction:**  
Strengthen ground army while increasing economy. Maintain expansion, production, defense, and air direction. Continue technology and upgrades. Tempo is develop with safety checks.

**Read for details:** `N003`

---

### [DEFAULT] N004 — ZvT Economy/Expansion Ground Posture with Light Tech

**Trigger situation:**  
Early-midgame phase where both sides show a heavy economy and expansion posture, with ground-oriented armies. Enemy intelligence suggests a ground macro posture with possible early pressure from Marine and Reaper cues. Your own posture is ground-oriented with moderate production and light or uncertain technology investment.

**Direction:**  
Strengthen ground army, increase economy and expansion, maintain production and defense, continue technology and upgrades, with a tempo of develop with safety checks.

**Read for details:** `N004`

---

### [POSITIVE] N005 — Zerg Economy/Expansion Ground Opening vs Terran

**Trigger situation:**  
Early game with heavy economy and expansion posture, ground-oriented army, moderate production, light or uncertain technology. Enemy intelligence shows unknown army posture, heavy economy and expansion, moderate production, heavy technology investment.

**Direction:**  
Increase economy and expansion, strengthen ground army, maintain production and defense, continue technology and upgrades, with safety checks.

**Read for details:** `N005`

---

### [DEFAULT] N006 — ZvT Late Midgame Ground Macro Posture

**Trigger situation:**  
Both sides are in late midgame with heavy economy, production, and technology. Enemy intelligence suggests a ground-oriented Terran posture with possible SiegeTank, Marine, Reaper, and Hellion cues. Own posture is ground-oriented with heavy production and technology, including Zergling, Queen, and Roach cues.

**Direction:**  
Strengthen ground army while continuing economy and expansion development. Maintain defense and air presence, increase technology and upgrades, and continue production with safety checks.

**Read for details:** `N006`

---

### [DEFAULT] N007 — ZvT Midgame Ground Macro with Heavy Economy

**Trigger situation:**  
Midgame phase with heavy economy and expansion posture for both sides; opponent shows ground-leaning army with moderate air presence; own posture is ground-oriented with heavy production and technology.

**Direction:**  
Continue expanding and increasing economy while strengthening ground forces and maintaining defense. Maintain air presence and continue technology and upgrade development.

**Read for details:** `N007`

---

### [DEFAULT] N008 — ZvT Economy/Expansion Ground Posture with Safety Checks

**Trigger situation:**  
Early-midgame phase where both sides show heavy economy and expansion, ground-oriented armies, and moderate-to-heavy production. Enemy intelligence suggests a ground posture with possible Marine, Reaper, Hellion cues. Own posture is ground macro with Zergling and Queen cues.

**Direction:**  
Continue expanding and increasing economy while strengthening ground army and increasing technology. Maintain defense and air direction with live safety checks.

**Read for details:** `N008`

---

### [NEGATIVE] N009 — Resource-to-Army Conversion Failure

**Trigger situation:**  
The agent is in a negative node where the primary failure signal is resource-to-army conversion failure, indicating that despite a heavy economy, the army is not being produced effectively.

**Risk direction:**  
Avoid continuing to expand or invest in technology without also increasing army production. Do not neglect army composition or fail to respond to the opponent's ground forces.

**Read for details:** `N009`

---

### [DEFAULT] N010 — ZvT Economy/Expansion Ground Opening - Early-Midgame Development

**Trigger situation:**  
Early-midgame phase with heavy economy and expansion posture, ground-oriented army, moderate production, light/uncertain technology. Opponent shows heavy production and technology with ground macro posture, possible pressure.

**Direction:**  
Increase economy and expansion, strengthen ground army, continue technology, maintain air and defense, develop with safety checks.

**Read for details:** `N010`

---

### [NEGATIVE] N011 — Ground Macro Posture with Heavy Economy and Production

**Trigger situation:**  
Late midgame phase with both sides showing heavy economy, expansion, production, and technology investment. Enemy intelligence is consistent with a ground posture, with representative cues including SiegeTank, Marine, Reaper, and Hellion. Own posture is ground-oriented with heavy production and technology, and representative cues include Zergling and Queen. Trajectory actions include Zergling, Overlord, Drone, Queen, Roach,…

**Risk direction:**  
Avoid resource-to-army conversion failure, where resources accumulate without being converted into army strength. Avoid feedback not changing repeated failed posture, where the same unsuccessful approach is repeated despite negative outcomes.

**Read for details:** `N011`

---

### [NEGATIVE] N012 — Resource-to-army conversion failure in a heavy-economy ground posture

**Trigger situation:**  
The agent has committed to a heavy economy and expansion posture while maintaining a ground-oriented army, but the trajectory shows a failure to convert accumulated resources into sufficient combat strength. The opponent's heavy production and technology investment, combined with a possible pressure posture, exposes the agent's defensive gaps.

**Risk direction:**  
Avoid over-investing in economy and technology at the expense of army production. Do not neglect scouting and defensive positioning. Avoid committing to a composition that is vulnerable to the opponent's known units, such as relying solely on light units against…

**Read for details:** `N012`

---
