# Legacy Tactical Strategy Tools Inventory

Generated from the frozen pre-migration strategy tool files. These files remain for baseline compatibility;
the Human Skill Agent no longer imports them.

| Race | Strategy | Threshold declarations | PlanZoneAttack args | Gates | Special markers |
| --- | --- | --- | --- | --- | --- |
| protoss | adept_allin | 8 | — | — | — |
| protoss | dark_templar_rush | 12 | — | — | — |
| protoss | disruptor | 18 | — | — | — |
| protoss | four_gate | 10 | — | — | — |
| protoss | macro_stalkers | 18 | — | — | — |
| protoss | one_base_tempests | 6 | — | — | — |
| protoss | protoss_silver | 24 | — | — | — |
| protoss | robo | 20 | — | — | — |
| protoss | voidray | 12 | — | — | — |
| terran | banshees | — | attack_value | UnitExists | — |
| terran | battle_cruisers | — | attack_value | UnitExists | TacticalJump |
| terran | bio | 26 | attack_value | UnitExists | — |
| terran | bio_mine_macro | — | attack_value | TechReady, UnitExists | — |
| terran | blueflame_locks | 50 | attack_value | TechReady, UnitExists | — |
| terran | cyclones | — | attack_value | TechReady, UnitExists | — |
| terran | marine_rush | 3 | — | UnitExists | DodgeRamp |
| terran | old_rusty_anvil | — | attack_value | UnitExists | — |
| terran | one_base_turtle | — | attack_value | UnitExists | — |
| terran | raven_liberator_tank | — | attack_value | UnitExists | — |
| terran | raven_screams | — | attack_value | UnitExists | — |
| terran | rusty | — | attack_value | UnitExists | — |
| terran | rusty_bio_mines | — | attack_value | UnitExists | — |
| terran | safe_211_mine | — | attack_value | TechReady, UnitExists | — |
| terran | safe_tvt_raven | — | attack_value | TechReady | — |
| terran | stim_rush_relay | — | 50 | TechReady, UnitExists | DodgeRamp |
| terran | tank_thor_mech | — | attack_value | UnitExists | — |
| terran | terran_silver_bio | — | — | — | — |
| terran | three_rax_stim | — | attack_value | TechReady, UnitExists | — |
| terran | two_base_matrix_tanks | 60 | attack_value | TechReady, UnitExists | — |
| terran | two_base_tanks | — | attack_value | UnitExists | — |
| terran | yamato_rust_fleet | 50 | attack_value | UnitExists | TacticalJump |
| zerg | lings | 14 | — | — | — |
| zerg | lurkers | 45 | — | UnitReady, attack_requirement | — |
| zerg | macro_roach | 32 | — | — | — |
| zerg | macro_zerg | 36 | — | — | — |
| zerg | mutalisk | 24 | — | — | — |
| zerg | roach_burrow | 20 | — | — | — |
| zerg | roach_hydra | 28 | — | — | — |
| zerg | twelve_pool | 2 | — | — | — |
| zerg | worker_rush | 2 | — | — | — |
| zerg | zerg_silver | 34 | — | — | — |

## V1 migration boundary

- All thresholds and gates above are legacy-only and are not loaded by `UniversalLLMBot`.
- Strategy-specific combat helpers remain untouched for reproducible baselines.
- New runs use the one frozen `UNIVERSAL_TACTICS_V1_CONFIG.json` configuration.
