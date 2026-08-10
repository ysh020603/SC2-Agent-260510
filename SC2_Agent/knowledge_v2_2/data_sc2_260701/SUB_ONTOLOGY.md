# SC2 Unit SubOntology — 2026-07-01

This document describes the 109 canonical Unit sub-ontologies embedded in `data_base_sc2_260701.json`.

## 1. Hierarchy

```text
Unit (204 canonical entities)
├── Dimension A classes (28)
├── Race classes (3)
└── Non-empty Race × Dimension intersections (78)
```

SubOntologies are Unit classes, not new Units. Their `members` arrays contain canonical Unit names.

## 2. Relation Use and Expansion

Semantic extraction may use a SubOntology as a subject or object in the source assertion. The entity-expanded graph materializes such an assertion over the class members. Every generated entity relation records `source.kind = subontology_expansion`, the original class-level relation, the involved SubOntology names, the selected member binding, and the original Markdown facts.

If several class-level assertions or a direct entity assertion produce the same concrete triple, the triple is stored once while all sources, facts, and descriptions remain attached. The deferred generic-group policy was not used, and no new composite SubOntologies were added.

## 3. Invariants

- Exactly 109 SubOntology records exist.
- Every member is one of the 204 canonical Units.
- `GroundUnits` and `AirUnits` are disjoint and together contain all Units.
- Secondary classes are non-empty race/class intersections.
- Ontology-scope relations use the same list-valued description/source/fact schema as all other relations.

## Dimension A Classes (28)

### AirAttackers — 34 members

- Parents: `Unit`
- Members: `InfestorTerran`, `Mothership`, `ChangelingMarineShield`, `ChangelingMarine`, `MissileTurret`, `AutoTurret`, `VikingFighter`, `Marine`, `Ghost`, `Thor`, `Battlecruiser`, `PhotonCannon`, `Stalker`, `Phoenix`, `VoidRay`, `Interceptor`, `SporeCrawler`, `Hydralisk`, `Mutalisk`, `Corruptor`, `Queen`, `Archon`, `GhostNova`, `NydusCanalAttacker`, `Tempest`, `WidowMineBurrowed`, `Liberator`, `ThorAP`, `Cyclone`, `DevourerMP`, `CorsairMP`, `ScoutMP`, `ArbiterMP`, `ScourgeMP`
- Ontology-scope subject relations: 0

### AirUnits — 51 members

- Parents: `Unit`
- Members: `Mothership`, `PointDefenseDrone`, `VikingFighter`, `CommandCenterFlying`, `FactoryFlying`, `StarportFlying`, `BarracksFlying`, `Medivac`, `Banshee`, `Raven`, `Battlecruiser`, `Nuke`, `Phoenix`, `Carrier`, `VoidRay`, `WarpPrism`, `Observer`, `Interceptor`, `Overlord`, `Mutalisk`, `Corruptor`, `BroodLordCocoon`, `BroodLord`, `OverlordCocoon`, `Overseer`, `OrbitalCommandFlying`, `WarpPrismPhasing`, `MothershipCore`, `Oracle`, `Tempest`, `Viper`, `TowerMine`, `Liberator`, `LocustMPFlying`, `GuardianCocoonMP`, `GuardianMP`, `DevourerCocoonMP`, `DevourerMP`, `LiberatorAG`, `ReleaseInterceptorsBeacon`, `CorsairMP`, `ScoutMP`, `ArbiterMP`, `ScourgeMP`, `QueenMP`, `TransportOverlordCocoon`, `OverlordTransport`, `BypassArmorDrone`, `ObserverSiegeMode`, `OverseerSiegeMode`, `RavenRepairDrone`
- Ontology-scope subject relations: 2

### Armored — 123 members

- Parents: `Unit`
- Members: `Colossus`, `TechLab`, `Reactor`, `Mothership`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `VikingFighter`, `CommandCenterFlying`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `FactoryFlying`, `StarportFlying`, `BarracksFlying`, `SupplyDepotLowered`, `Marauder`, `Thor`, `Medivac`, `Battlecruiser`, `Nexus`, `Pylon`, `Assimilator`, `Gateway`, `Forge`, `FleetBeacon`, `TwilightCouncil`, `PhotonCannon`, `Stargate`, `TemplarArchive`, `DarkShrine`, `RoboticsBay`, `RoboticsFacility`, `CyberneticsCore`, `Stalker`, `Carrier`, `VoidRay`, `WarpPrism`, `Immortal`, `Hatchery`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `Overlord`, `Ultralisk`, `Roach`, `Infestor`, `Corruptor`, `BroodLord`, `RoachBurrowed`, `InfestorBurrowed`, `Overseer`, `PlanetaryFortress`, `UltraliskBurrowed`, `OrbitalCommand`, `WarpGate`, `OrbitalCommandFlying`, `WarpPrismPhasing`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `NydusCanal`, `MothershipCore`, `NydusCanalAttacker`, `NydusCanalCreeper`, `SwarmHostBurrowedMP`, `SwarmHostMP`, `Oracle`, `Tempest`, `WarHound`, `Viper`, `LurkerMP`, `LurkerMPBurrowed`, `LurkerDenMP`, `Liberator`, `ThorAP`, `Cyclone`, `Disruptor`, `VoidMPImmortalReviveCorpse`, `GuardianMP`, `DevourerMP`, `DisruptorPhased`, `LiberatorAG`, `HERCPlacement`, `HERC`, `ScoutMP`, `ArbiterMP`, `Elsecaro_Colonist_Hut`, `OverlordTransport`, `PylonOvercharged`, `ShieldBattery`, `OverseerSiegeMode`, `RefineryRich`, `AssimilatorRich`, `ExtractorRich`
- Ontology-scope subject relations: 1

### Biological — 99 members

- Parents: `Unit`
- Members: `InfestorTerran`, `BanelingCocoon`, `Baneling`, `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `SCV`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `Zealot`, `HighTemplar`, `DarkTemplar`, `Hatchery`, `CreepTumor`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `Egg`, `Drone`, `Zergling`, `Overlord`, `Hydralisk`, `Mutalisk`, `Ultralisk`, `Roach`, `Infestor`, `Corruptor`, `BroodLordCocoon`, `BroodLord`, `BanelingBurrowed`, `DroneBurrowed`, `HydraliskBurrowed`, `RoachBurrowed`, `ZerglingBurrowed`, `InfestorTerranBurrowed`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `OverlordCocoon`, `Overseer`, `UltraliskBurrowed`, `CreepTumorBurrowed`, `CreepTumorQueen`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `NydusCanal`, `GhostNova`, `InfestedTerransEgg`, `Larva`, `Broodling`, `Adept`, `HellionTank`, `LocustMP`, `NydusCanalAttacker`, `NydusCanalCreeper`, `SwarmHostBurrowedMP`, `SwarmHostMP`, `Viper`, `LurkerMPEgg`, `LurkerMP`, `LurkerMPBurrowed`, `LurkerDenMP`, `RavagerCocoon`, `Ravager`, `RavagerBurrowed`, `LocustMPFlying`, `GuardianCocoonMP`, `GuardianMP`, `DevourerCocoonMP`, `DevourerMP`, `DefilerMPBurrowed`, `DefilerMP`, `AdeptPhaseShift`, `HERCPlacement`, `HERC`, `Replicant`, `ScourgeMP`, `QueenMP`, `TransportOverlordCocoon`, `OverlordTransport`, `OverseerSiegeMode`, `ExtractorRich`
- Ontology-scope subject relations: 0

### CapitalShips — 6 members

- Parents: `Unit`
- Members: `Mothership`, `Battlecruiser`, `BroodLord`, `Tempest`, `GuardianMP`, `DevourerMP`
- Ontology-scope subject relations: 0

### Detectors — 8 members

- Parents: `Unit`
- Members: `MissileTurret`, `Raven`, `PhotonCannon`, `Observer`, `SporeCrawler`, `Overseer`, `ObserverSiegeMode`, `OverseerSiegeMode`
- Ontology-scope subject relations: 1

### GroundAttackers — 64 members

- Parents: `Unit`
- Members: `Colossus`, `InfestorTerran`, `Baneling`, `Mothership`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `SCV`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `Thor`, `Hellion`, `Banshee`, `Battlecruiser`, `PhotonCannon`, `Zealot`, `Stalker`, `HighTemplar`, `DarkTemplar`, `Sentry`, `VoidRay`, `Immortal`, `Probe`, `Interceptor`, `SpineCrawler`, `Drone`, `Zergling`, `Hydralisk`, `Mutalisk`, `Ultralisk`, `Roach`, `BroodLord`, `Queen`, `PlanetaryFortress`, `Archon`, `GhostNova`, `Broodling`, `Adept`, `HellionTank`, `MothershipCore`, `LocustMP`, `NydusCanalAttacker`, `Oracle`, `Tempest`, `WarHound`, `LurkerMP`, `LurkerMPBurrowed`, `Ravager`, `ThorAP`, `Cyclone`, `GuardianMP`, `LiberatorAG`, `HERCPlacement`, `HERC`, `ScoutMP`, `ArbiterMP`
- Ontology-scope subject relations: 0

### GroundUnits — 153 members

- Parents: `Unit`
- Members: `Colossus`, `TechLab`, `Reactor`, `InfestorTerran`, `BanelingCocoon`, `Baneling`, `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `SCV`, `SupplyDepotLowered`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `Thor`, `Hellion`, `Nexus`, `Pylon`, `Assimilator`, `Gateway`, `Forge`, `FleetBeacon`, `TwilightCouncil`, `PhotonCannon`, `Stargate`, `TemplarArchive`, `DarkShrine`, `RoboticsBay`, `RoboticsFacility`, `CyberneticsCore`, `Zealot`, `Stalker`, `HighTemplar`, `DarkTemplar`, `Sentry`, `Immortal`, `Probe`, `Hatchery`, `CreepTumor`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `Egg`, `Drone`, `Zergling`, `Hydralisk`, `Ultralisk`, `Roach`, `Infestor`, `BanelingBurrowed`, `DroneBurrowed`, `HydraliskBurrowed`, `RoachBurrowed`, `ZerglingBurrowed`, `InfestorTerranBurrowed`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `PlanetaryFortress`, `UltraliskBurrowed`, `OrbitalCommand`, `WarpGate`, `CreepTumorBurrowed`, `CreepTumorQueen`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `Archon`, `NydusCanal`, `GhostNova`, `InfestedTerransEgg`, `Larva`, `MULE`, `Broodling`, `Adept`, `InfestedTerransEggPlacement`, `HellionTank`, `LocustMP`, `NydusCanalAttacker`, `NydusCanalCreeper`, `SwarmHostBurrowedMP`, `SwarmHostMP`, `WarHound`, `WidowMine`, `WidowMineBurrowed`, `LurkerMPEgg`, `LurkerMP`, `LurkerMPBurrowed`, `LurkerDenMP`, `ResourceBlocker`, `IceProtossCrates`, `ProtossCrates`, `RavagerCocoon`, `Ravager`, `RavagerBurrowed`, `ThorAP`, `Cyclone`, `Disruptor`, `VoidMPImmortalReviveCorpse`, `DefilerMPBurrowed`, `DefilerMP`, `OracleStasisTrap`, `DisruptorPhased`, `AdeptPhaseShift`, `ThorAALance`, `HERCPlacement`, `HERC`, `Replicant`, `Elsecaro_Colonist_Hut`, `PylonOvercharged`, `ShieldBattery`, `Viking`, `RefineryRich`, `AssimilatorRich`, `ExtractorRich`
- Ontology-scope subject relations: 2

### Harassers — 15 members

- Parents: `Unit`
- Members: `InfestorTerran`, `Baneling`, `VikingAssault`, `VikingFighter`, `Marine`, `Reaper`, `Banshee`, `Battlecruiser`, `Zealot`, `Stalker`, `DarkTemplar`, `Probe`, `Zergling`, `Mutalisk`, `Adept`
- Ontology-scope subject relations: 0

### Heroic — 1 members

- Parents: `Unit`
- Members: `Mothership`
- Ontology-scope subject relations: 0

### Light — 49 members

- Parents: `Unit`
- Members: `InfestorTerran`, `PointDefenseDrone`, `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `SCV`, `Marine`, `Reaper`, `Hellion`, `Banshee`, `Raven`, `Zealot`, `HighTemplar`, `DarkTemplar`, `Phoenix`, `Observer`, `Probe`, `Interceptor`, `CreepTumor`, `Drone`, `Zergling`, `Hydralisk`, `Mutalisk`, `DroneBurrowed`, `HydraliskBurrowed`, `ZerglingBurrowed`, `InfestorTerranBurrowed`, `CreepTumorBurrowed`, `CreepTumorQueen`, `Larva`, `MULE`, `Broodling`, `Adept`, `HellionTank`, `LocustMP`, `WidowMine`, `WidowMineBurrowed`, `LocustMPFlying`, `OracleStasisTrap`, `AdeptPhaseShift`, `Replicant`, `CorsairMP`, `ScourgeMP`, `BypassArmorDrone`, `ObserverSiegeMode`, `RavenRepairDrone`
- Ontology-scope subject relations: 0

### Massive — 16 members

- Parents: `Unit`
- Members: `Colossus`, `Mothership`, `Thor`, `Battlecruiser`, `Carrier`, `Ultralisk`, `BroodLordCocoon`, `BroodLord`, `UltraliskBurrowed`, `Archon`, `Tempest`, `ThorAP`, `GuardianCocoonMP`, `GuardianMP`, `DevourerCocoonMP`, `DevourerMP`
- Ontology-scope subject relations: 0

### Mechanical — 78 members

- Parents: `Unit`
- Members: `Colossus`, `TechLab`, `Reactor`, `Mothership`, `PointDefenseDrone`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `VikingFighter`, `CommandCenterFlying`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `FactoryFlying`, `StarportFlying`, `SCV`, `BarracksFlying`, `SupplyDepotLowered`, `Thor`, `Hellion`, `Medivac`, `Banshee`, `Raven`, `Battlecruiser`, `Stalker`, `Sentry`, `Phoenix`, `Carrier`, `VoidRay`, `WarpPrism`, `Observer`, `Immortal`, `Probe`, `Interceptor`, `PlanetaryFortress`, `OrbitalCommand`, `OrbitalCommandFlying`, `WarpPrismPhasing`, `MULE`, `HellionTank`, `MothershipCore`, `Oracle`, `Tempest`, `WarHound`, `WidowMine`, `WidowMineBurrowed`, `Liberator`, `ThorAP`, `Cyclone`, `Disruptor`, `VoidMPImmortalReviveCorpse`, `DisruptorPhased`, `LiberatorAG`, `CorsairMP`, `ScoutMP`, `ArbiterMP`, `Elsecaro_Colonist_Hut`, `BypassArmorDrone`, `ObserverSiegeMode`, `RavenRepairDrone`, `RefineryRich`
- Ontology-scope subject relations: 0

### MeleeUnits — 12 members

- Parents: `Unit`
- Members: `ChangelingZealot`, `ChangelingZerglingWings`, `ChangelingZergling`, `SCV`, `Zealot`, `DarkTemplar`, `Probe`, `Drone`, `Zergling`, `Ultralisk`, `Broodling`, `ScourgeMP`
- Ontology-scope subject relations: 0

### Psionic — 18 members

- Parents: `Unit`
- Members: `Mothership`, `Ghost`, `HighTemplar`, `DarkTemplar`, `Sentry`, `WarpPrism`, `Infestor`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `WarpPrismPhasing`, `Archon`, `GhostNova`, `MothershipCore`, `Oracle`, `Viper`, `DefilerMPBurrowed`, `DefilerMP`
- Ontology-scope subject relations: 0

### RangedUnits — 48 members

- Parents: `Unit`
- Members: `Colossus`, `InfestorTerran`, `Mothership`, `ChangelingMarineShield`, `ChangelingMarine`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `VikingFighter`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `Thor`, `Hellion`, `Banshee`, `Stalker`, `HighTemplar`, `Phoenix`, `Immortal`, `Interceptor`, `Hydralisk`, `Mutalisk`, `Roach`, `Corruptor`, `BroodLord`, `Queen`, `Archon`, `GhostNova`, `Adept`, `HellionTank`, `MothershipCore`, `LocustMP`, `Tempest`, `WarHound`, `LurkerMPBurrowed`, `Ravager`, `Liberator`, `ThorAP`, `Cyclone`, `GuardianMP`, `DevourerMP`, `LiberatorAG`, `HERCPlacement`, `HERC`, `CorsairMP`, `ScoutMP`, `ArbiterMP`
- Ontology-scope subject relations: 0

### Scouts — 19 members

- Parents: `Unit`
- Members: `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `VikingFighter`, `Reaper`, `Hellion`, `Sentry`, `Phoenix`, `Observer`, `Probe`, `Zergling`, `Mutalisk`, `Overseer`, `Oracle`, `ObserverSiegeMode`, `OverseerSiegeMode`
- Ontology-scope subject relations: 0

### Spellcasters — 21 members

- Parents: `Unit`
- Members: `Ghost`, `Medivac`, `Banshee`, `Raven`, `HighTemplar`, `Sentry`, `Phoenix`, `Infestor`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `Overseer`, `GhostNova`, `MothershipCore`, `Oracle`, `Viper`, `DefilerMPBurrowed`, `DefilerMP`, `ArbiterMP`, `QueenMP`, `OverseerSiegeMode`
- Ontology-scope subject relations: 0

### SplashDamageDealers — 20 members

- Parents: `Unit`
- Members: `Colossus`, `Baneling`, `Thor`, `Hellion`, `Raven`, `HighTemplar`, `Ultralisk`, `BanelingBurrowed`, `PlanetaryFortress`, `UltraliskBurrowed`, `Archon`, `HellionTank`, `WidowMine`, `WidowMineBurrowed`, `LurkerMP`, `LurkerMPBurrowed`, `Liberator`, `ThorAP`, `Disruptor`, `LiberatorAG`
- Ontology-scope subject relations: 0

### StaticDefenses — 7 members

- Parents: `Unit`
- Members: `MissileTurret`, `AutoTurret`, `PhotonCannon`, `SpineCrawler`, `SporeCrawler`, `PlanetaryFortress`, `ShieldBattery`
- Ontology-scope subject relations: 0

### StealthUnits — 6 members

- Parents: `Unit`
- Members: `Ghost`, `Banshee`, `DarkTemplar`, `Observer`, `GhostNova`, `ObserverSiegeMode`
- Ontology-scope subject relations: 0

### Structure — 81 members

- Parents: `Unit`
- Members: `TechLab`, `Reactor`, `PointDefenseDrone`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `CommandCenterFlying`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `FactoryFlying`, `StarportFlying`, `BarracksFlying`, `SupplyDepotLowered`, `Nexus`, `Pylon`, `Assimilator`, `Gateway`, `Forge`, `FleetBeacon`, `TwilightCouncil`, `PhotonCannon`, `Stargate`, `TemplarArchive`, `DarkShrine`, `RoboticsBay`, `RoboticsFacility`, `CyberneticsCore`, `Hatchery`, `CreepTumor`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `PlanetaryFortress`, `OrbitalCommand`, `WarpGate`, `OrbitalCommandFlying`, `CreepTumorBurrowed`, `CreepTumorQueen`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `NydusCanal`, `NydusCanalAttacker`, `NydusCanalCreeper`, `LurkerDenMP`, `ResourceBlocker`, `OracleStasisTrap`, `Elsecaro_Colonist_Hut`, `PylonOvercharged`, `BypassArmorDrone`, `ShieldBattery`, `RavenRepairDrone`, `RefineryRich`, `AssimilatorRich`, `ExtractorRich`
- Ontology-scope subject relations: 0

### Summoned — 1 members

- Parents: `Unit`
- Members: `RavenRepairDrone`
- Ontology-scope subject relations: 0

### SupportUnits — 14 members

- Parents: `Unit`
- Members: `Colossus`, `VikingAssault`, `VikingFighter`, `Ghost`, `Thor`, `Medivac`, `Raven`, `Sentry`, `Archon`, `MothershipCore`, `Oracle`, `Viper`, `ThorAP`, `Disruptor`
- Ontology-scope subject relations: 0

### TimedLifeUnits — 13 members

- Parents: `Unit`
- Members: `PointDefenseDrone`, `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `AutoTurret`, `MULE`, `Broodling`, `LocustMP`, `LocustMPFlying`, `OracleStasisTrap`
- Ontology-scope subject relations: 0

### TransportUnits — 4 members

- Parents: `Unit`
- Members: `Medivac`, `WarpPrism`, `WarpPrismPhasing`, `OverlordTransport`
- Ontology-scope subject relations: 0

### UnitProducingStructures — 14 members

- Parents: `Unit`
- Members: `CommandCenter`, `Barracks`, `Factory`, `Starport`, `Nexus`, `Gateway`, `Stargate`, `RoboticsFacility`, `Hatchery`, `Lair`, `Hive`, `PlanetaryFortress`, `OrbitalCommand`, `WarpGate`
- Ontology-scope subject relations: 0

### Workers — 3 members

- Parents: `Unit`
- Members: `SCV`, `Probe`, `Drone`
- Ontology-scope subject relations: 0

## Race Classes (3)

### Protoss — 53 members

- Parents: `Unit`
- Members: `Colossus`, `Mothership`, `Nexus`, `Pylon`, `Assimilator`, `Gateway`, `Forge`, `FleetBeacon`, `TwilightCouncil`, `PhotonCannon`, `Stargate`, `TemplarArchive`, `DarkShrine`, `RoboticsBay`, `RoboticsFacility`, `CyberneticsCore`, `Zealot`, `Stalker`, `HighTemplar`, `DarkTemplar`, `Sentry`, `Phoenix`, `Carrier`, `VoidRay`, `WarpPrism`, `Observer`, `Immortal`, `Probe`, `Interceptor`, `WarpGate`, `WarpPrismPhasing`, `Archon`, `Adept`, `MothershipCore`, `Oracle`, `Tempest`, `ResourceBlocker`, `IceProtossCrates`, `ProtossCrates`, `Disruptor`, `VoidMPImmortalReviveCorpse`, `OracleStasisTrap`, `DisruptorPhased`, `ReleaseInterceptorsBeacon`, `AdeptPhaseShift`, `Replicant`, `CorsairMP`, `ScoutMP`, `ArbiterMP`, `PylonOvercharged`, `ShieldBattery`, `ObserverSiegeMode`, `AssimilatorRich`
- Ontology-scope subject relations: 0

### Terran — 66 members

- Parents: `Unit`
- Members: `TechLab`, `Reactor`, `PointDefenseDrone`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `VikingFighter`, `CommandCenterFlying`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `FactoryFlying`, `StarportFlying`, `SCV`, `BarracksFlying`, `SupplyDepotLowered`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `Thor`, `Hellion`, `Medivac`, `Banshee`, `Raven`, `Battlecruiser`, `Nuke`, `PlanetaryFortress`, `OrbitalCommand`, `OrbitalCommandFlying`, `GhostNova`, `MULE`, `HellionTank`, `WarHound`, `WidowMine`, `WidowMineBurrowed`, `TowerMine`, `Liberator`, `ThorAP`, `Cyclone`, `LiberatorAG`, `ThorAALance`, `HERCPlacement`, `HERC`, `Elsecaro_Colonist_Hut`, `BypassArmorDrone`, `RavenRepairDrone`, `Viking`, `RefineryRich`
- Ontology-scope subject relations: 0

### Zerg — 85 members

- Parents: `Unit`
- Members: `InfestorTerran`, `BanelingCocoon`, `Baneling`, `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `Hatchery`, `CreepTumor`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `Egg`, `Drone`, `Zergling`, `Overlord`, `Hydralisk`, `Mutalisk`, `Ultralisk`, `Roach`, `Infestor`, `Corruptor`, `BroodLordCocoon`, `BroodLord`, `BanelingBurrowed`, `DroneBurrowed`, `HydraliskBurrowed`, `RoachBurrowed`, `ZerglingBurrowed`, `InfestorTerranBurrowed`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `OverlordCocoon`, `Overseer`, `UltraliskBurrowed`, `CreepTumorBurrowed`, `CreepTumorQueen`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `NydusCanal`, `InfestedTerransEgg`, `Larva`, `Broodling`, `InfestedTerransEggPlacement`, `LocustMP`, `NydusCanalAttacker`, `NydusCanalCreeper`, `SwarmHostBurrowedMP`, `SwarmHostMP`, `Viper`, `LurkerMPEgg`, `LurkerMP`, `LurkerMPBurrowed`, `LurkerDenMP`, `RavagerCocoon`, `Ravager`, `RavagerBurrowed`, `LocustMPFlying`, `GuardianCocoonMP`, `GuardianMP`, `DevourerCocoonMP`, `DevourerMP`, `DefilerMPBurrowed`, `DefilerMP`, `ScourgeMP`, `QueenMP`, `TransportOverlordCocoon`, `OverlordTransport`, `OverseerSiegeMode`, `ExtractorRich`
- Ontology-scope subject relations: 0

## Secondary Race × Dimension Classes (78)

### Protoss_AirAttackers — 11 members

- Parents: `Protoss`, `AirAttackers`
- Members: `Mothership`, `PhotonCannon`, `Stalker`, `Phoenix`, `VoidRay`, `Interceptor`, `Archon`, `Tempest`, `CorsairMP`, `ScoutMP`, `ArbiterMP`
- Ontology-scope subject relations: 0

### Protoss_AirUnits — 16 members

- Parents: `Protoss`, `AirUnits`
- Members: `Mothership`, `Phoenix`, `Carrier`, `VoidRay`, `WarpPrism`, `Observer`, `Interceptor`, `WarpPrismPhasing`, `MothershipCore`, `Oracle`, `Tempest`, `ReleaseInterceptorsBeacon`, `CorsairMP`, `ScoutMP`, `ArbiterMP`, `ObserverSiegeMode`
- Ontology-scope subject relations: 0

### Protoss_Armored — 34 members

- Parents: `Protoss`, `Armored`
- Members: `Colossus`, `Mothership`, `Nexus`, `Pylon`, `Assimilator`, `Gateway`, `Forge`, `FleetBeacon`, `TwilightCouncil`, `PhotonCannon`, `Stargate`, `TemplarArchive`, `DarkShrine`, `RoboticsBay`, `RoboticsFacility`, `CyberneticsCore`, `Stalker`, `Carrier`, `VoidRay`, `WarpPrism`, `Immortal`, `WarpGate`, `WarpPrismPhasing`, `MothershipCore`, `Oracle`, `Tempest`, `Disruptor`, `VoidMPImmortalReviveCorpse`, `DisruptorPhased`, `ScoutMP`, `ArbiterMP`, `PylonOvercharged`, `ShieldBattery`, `AssimilatorRich`
- Ontology-scope subject relations: 0

### Protoss_Biological — 6 members

- Parents: `Protoss`, `Biological`
- Members: `Zealot`, `HighTemplar`, `DarkTemplar`, `Adept`, `AdeptPhaseShift`, `Replicant`
- Ontology-scope subject relations: 0

### Protoss_CapitalShips — 2 members

- Parents: `Protoss`, `CapitalShips`
- Members: `Mothership`, `Tempest`
- Ontology-scope subject relations: 0

### Protoss_Detectors — 3 members

- Parents: `Protoss`, `Detectors`
- Members: `PhotonCannon`, `Observer`, `ObserverSiegeMode`
- Ontology-scope subject relations: 0

### Protoss_GroundAttackers — 19 members

- Parents: `Protoss`, `GroundAttackers`
- Members: `Colossus`, `Mothership`, `PhotonCannon`, `Zealot`, `Stalker`, `HighTemplar`, `DarkTemplar`, `Sentry`, `VoidRay`, `Immortal`, `Probe`, `Interceptor`, `Archon`, `Adept`, `MothershipCore`, `Oracle`, `Tempest`, `ScoutMP`, `ArbiterMP`
- Ontology-scope subject relations: 0

### Protoss_GroundUnits — 37 members

- Parents: `Protoss`, `GroundUnits`
- Members: `Colossus`, `Nexus`, `Pylon`, `Assimilator`, `Gateway`, `Forge`, `FleetBeacon`, `TwilightCouncil`, `PhotonCannon`, `Stargate`, `TemplarArchive`, `DarkShrine`, `RoboticsBay`, `RoboticsFacility`, `CyberneticsCore`, `Zealot`, `Stalker`, `HighTemplar`, `DarkTemplar`, `Sentry`, `Immortal`, `Probe`, `WarpGate`, `Archon`, `Adept`, `ResourceBlocker`, `IceProtossCrates`, `ProtossCrates`, `Disruptor`, `VoidMPImmortalReviveCorpse`, `OracleStasisTrap`, `DisruptorPhased`, `AdeptPhaseShift`, `Replicant`, `PylonOvercharged`, `ShieldBattery`, `AssimilatorRich`
- Ontology-scope subject relations: 0

### Protoss_Harassers — 5 members

- Parents: `Protoss`, `Harassers`
- Members: `Zealot`, `Stalker`, `DarkTemplar`, `Probe`, `Adept`
- Ontology-scope subject relations: 0

### Protoss_Heroic — 1 members

- Parents: `Protoss`, `Heroic`
- Members: `Mothership`
- Ontology-scope subject relations: 0

### Protoss_Light — 13 members

- Parents: `Protoss`, `Light`
- Members: `Zealot`, `HighTemplar`, `DarkTemplar`, `Phoenix`, `Observer`, `Probe`, `Interceptor`, `Adept`, `OracleStasisTrap`, `AdeptPhaseShift`, `Replicant`, `CorsairMP`, `ObserverSiegeMode`
- Ontology-scope subject relations: 0

### Protoss_Massive — 5 members

- Parents: `Protoss`, `Massive`
- Members: `Colossus`, `Mothership`, `Carrier`, `Archon`, `Tempest`
- Ontology-scope subject relations: 0

### Protoss_Mechanical — 23 members

- Parents: `Protoss`, `Mechanical`
- Members: `Colossus`, `Mothership`, `Stalker`, `Sentry`, `Phoenix`, `Carrier`, `VoidRay`, `WarpPrism`, `Observer`, `Immortal`, `Probe`, `Interceptor`, `WarpPrismPhasing`, `MothershipCore`, `Oracle`, `Tempest`, `Disruptor`, `VoidMPImmortalReviveCorpse`, `DisruptorPhased`, `CorsairMP`, `ScoutMP`, `ArbiterMP`, `ObserverSiegeMode`
- Ontology-scope subject relations: 0

### Protoss_MeleeUnits — 3 members

- Parents: `Protoss`, `MeleeUnits`
- Members: `Zealot`, `DarkTemplar`, `Probe`
- Ontology-scope subject relations: 0

### Protoss_Psionic — 9 members

- Parents: `Protoss`, `Psionic`
- Members: `Mothership`, `HighTemplar`, `DarkTemplar`, `Sentry`, `WarpPrism`, `WarpPrismPhasing`, `Archon`, `MothershipCore`, `Oracle`
- Ontology-scope subject relations: 0

### Protoss_RangedUnits — 14 members

- Parents: `Protoss`, `RangedUnits`
- Members: `Colossus`, `Mothership`, `Stalker`, `HighTemplar`, `Phoenix`, `Immortal`, `Interceptor`, `Archon`, `Adept`, `MothershipCore`, `Tempest`, `CorsairMP`, `ScoutMP`, `ArbiterMP`
- Ontology-scope subject relations: 0

### Protoss_Scouts — 6 members

- Parents: `Protoss`, `Scouts`
- Members: `Sentry`, `Phoenix`, `Observer`, `Probe`, `Oracle`, `ObserverSiegeMode`
- Ontology-scope subject relations: 0

### Protoss_Spellcasters — 6 members

- Parents: `Protoss`, `Spellcasters`
- Members: `HighTemplar`, `Sentry`, `Phoenix`, `MothershipCore`, `Oracle`, `ArbiterMP`
- Ontology-scope subject relations: 0

### Protoss_SplashDamageDealers — 4 members

- Parents: `Protoss`, `SplashDamageDealers`
- Members: `Colossus`, `HighTemplar`, `Archon`, `Disruptor`
- Ontology-scope subject relations: 0

### Protoss_StaticDefenses — 2 members

- Parents: `Protoss`, `StaticDefenses`
- Members: `PhotonCannon`, `ShieldBattery`
- Ontology-scope subject relations: 0

### Protoss_StealthUnits — 3 members

- Parents: `Protoss`, `StealthUnits`
- Members: `DarkTemplar`, `Observer`, `ObserverSiegeMode`
- Ontology-scope subject relations: 0

### Protoss_Structure — 20 members

- Parents: `Protoss`, `Structure`
- Members: `Nexus`, `Pylon`, `Assimilator`, `Gateway`, `Forge`, `FleetBeacon`, `TwilightCouncil`, `PhotonCannon`, `Stargate`, `TemplarArchive`, `DarkShrine`, `RoboticsBay`, `RoboticsFacility`, `CyberneticsCore`, `WarpGate`, `ResourceBlocker`, `OracleStasisTrap`, `PylonOvercharged`, `ShieldBattery`, `AssimilatorRich`
- Ontology-scope subject relations: 0

### Protoss_SupportUnits — 6 members

- Parents: `Protoss`, `SupportUnits`
- Members: `Colossus`, `Sentry`, `Archon`, `MothershipCore`, `Oracle`, `Disruptor`
- Ontology-scope subject relations: 0

### Protoss_TimedLifeUnits — 1 members

- Parents: `Protoss`, `TimedLifeUnits`
- Members: `OracleStasisTrap`
- Ontology-scope subject relations: 0

### Protoss_TransportUnits — 2 members

- Parents: `Protoss`, `TransportUnits`
- Members: `WarpPrism`, `WarpPrismPhasing`
- Ontology-scope subject relations: 0

### Protoss_UnitProducingStructures — 5 members

- Parents: `Protoss`, `UnitProducingStructures`
- Members: `Nexus`, `Gateway`, `Stargate`, `RoboticsFacility`, `WarpGate`
- Ontology-scope subject relations: 0

### Protoss_Workers — 1 members

- Parents: `Protoss`, `Workers`
- Members: `Probe`
- Ontology-scope subject relations: 0

### Terran_AirAttackers — 12 members

- Parents: `Terran`, `AirAttackers`
- Members: `MissileTurret`, `AutoTurret`, `VikingFighter`, `Marine`, `Ghost`, `Thor`, `Battlecruiser`, `GhostNova`, `WidowMineBurrowed`, `Liberator`, `ThorAP`, `Cyclone`
- Ontology-scope subject relations: 0

### Terran_AirUnits — 17 members

- Parents: `Terran`, `AirUnits`
- Members: `PointDefenseDrone`, `VikingFighter`, `CommandCenterFlying`, `FactoryFlying`, `StarportFlying`, `BarracksFlying`, `Medivac`, `Banshee`, `Raven`, `Battlecruiser`, `Nuke`, `OrbitalCommandFlying`, `TowerMine`, `Liberator`, `LiberatorAG`, `BypassArmorDrone`, `RavenRepairDrone`
- Ontology-scope subject relations: 0

### Terran_Armored — 47 members

- Parents: `Terran`, `Armored`
- Members: `TechLab`, `Reactor`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `VikingFighter`, `CommandCenterFlying`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `FactoryFlying`, `StarportFlying`, `BarracksFlying`, `SupplyDepotLowered`, `Marauder`, `Thor`, `Medivac`, `Battlecruiser`, `PlanetaryFortress`, `OrbitalCommand`, `OrbitalCommandFlying`, `WarHound`, `Liberator`, `ThorAP`, `Cyclone`, `LiberatorAG`, `HERCPlacement`, `HERC`, `Elsecaro_Colonist_Hut`, `RefineryRich`
- Ontology-scope subject relations: 0

### Terran_Biological — 9 members

- Parents: `Terran`, `Biological`
- Members: `SCV`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `GhostNova`, `HellionTank`, `HERCPlacement`, `HERC`
- Ontology-scope subject relations: 0

### Terran_CapitalShips — 1 members

- Parents: `Terran`, `CapitalShips`
- Members: `Battlecruiser`
- Ontology-scope subject relations: 0

### Terran_Detectors — 2 members

- Parents: `Terran`, `Detectors`
- Members: `MissileTurret`, `Raven`
- Ontology-scope subject relations: 0

### Terran_GroundAttackers — 22 members

- Parents: `Terran`, `GroundAttackers`
- Members: `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `SCV`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `Thor`, `Hellion`, `Banshee`, `Battlecruiser`, `PlanetaryFortress`, `GhostNova`, `HellionTank`, `WarHound`, `ThorAP`, `Cyclone`, `LiberatorAG`, `HERCPlacement`, `HERC`
- Ontology-scope subject relations: 0

### Terran_GroundUnits — 49 members

- Parents: `Terran`, `GroundUnits`
- Members: `TechLab`, `Reactor`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `SCV`, `SupplyDepotLowered`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `Thor`, `Hellion`, `PlanetaryFortress`, `OrbitalCommand`, `GhostNova`, `MULE`, `HellionTank`, `WarHound`, `WidowMine`, `WidowMineBurrowed`, `ThorAP`, `Cyclone`, `ThorAALance`, `HERCPlacement`, `HERC`, `Elsecaro_Colonist_Hut`, `Viking`, `RefineryRich`
- Ontology-scope subject relations: 0

### Terran_Harassers — 6 members

- Parents: `Terran`, `Harassers`
- Members: `VikingAssault`, `VikingFighter`, `Marine`, `Reaper`, `Banshee`, `Battlecruiser`
- Ontology-scope subject relations: 0

### Terran_Light — 13 members

- Parents: `Terran`, `Light`
- Members: `PointDefenseDrone`, `SCV`, `Marine`, `Reaper`, `Hellion`, `Banshee`, `Raven`, `MULE`, `HellionTank`, `WidowMine`, `WidowMineBurrowed`, `BypassArmorDrone`, `RavenRepairDrone`
- Ontology-scope subject relations: 0

### Terran_Massive — 3 members

- Parents: `Terran`, `Massive`
- Members: `Thor`, `Battlecruiser`, `ThorAP`
- Ontology-scope subject relations: 0

### Terran_Mechanical — 55 members

- Parents: `Terran`, `Mechanical`
- Members: `TechLab`, `Reactor`, `PointDefenseDrone`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `VikingFighter`, `CommandCenterFlying`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `FactoryFlying`, `StarportFlying`, `SCV`, `BarracksFlying`, `SupplyDepotLowered`, `Thor`, `Hellion`, `Medivac`, `Banshee`, `Raven`, `Battlecruiser`, `PlanetaryFortress`, `OrbitalCommand`, `OrbitalCommandFlying`, `MULE`, `HellionTank`, `WarHound`, `WidowMine`, `WidowMineBurrowed`, `Liberator`, `ThorAP`, `Cyclone`, `LiberatorAG`, `Elsecaro_Colonist_Hut`, `BypassArmorDrone`, `RavenRepairDrone`, `RefineryRich`
- Ontology-scope subject relations: 0

### Terran_MeleeUnits — 1 members

- Parents: `Terran`, `MeleeUnits`
- Members: `SCV`
- Ontology-scope subject relations: 0

### Terran_Psionic — 2 members

- Parents: `Terran`, `Psionic`
- Members: `Ghost`, `GhostNova`
- Ontology-scope subject relations: 0

### Terran_RangedUnits — 20 members

- Parents: `Terran`, `RangedUnits`
- Members: `SiegeTankSieged`, `SiegeTank`, `VikingAssault`, `VikingFighter`, `Marine`, `Reaper`, `Ghost`, `Marauder`, `Thor`, `Hellion`, `Banshee`, `GhostNova`, `HellionTank`, `WarHound`, `Liberator`, `ThorAP`, `Cyclone`, `LiberatorAG`, `HERCPlacement`, `HERC`
- Ontology-scope subject relations: 0

### Terran_Scouts — 3 members

- Parents: `Terran`, `Scouts`
- Members: `VikingFighter`, `Reaper`, `Hellion`
- Ontology-scope subject relations: 0

### Terran_Spellcasters — 5 members

- Parents: `Terran`, `Spellcasters`
- Members: `Ghost`, `Medivac`, `Banshee`, `Raven`, `GhostNova`
- Ontology-scope subject relations: 0

### Terran_SplashDamageDealers — 10 members

- Parents: `Terran`, `SplashDamageDealers`
- Members: `Thor`, `Hellion`, `Raven`, `PlanetaryFortress`, `HellionTank`, `WidowMine`, `WidowMineBurrowed`, `Liberator`, `ThorAP`, `LiberatorAG`
- Ontology-scope subject relations: 0

### Terran_StaticDefenses — 3 members

- Parents: `Terran`, `StaticDefenses`
- Members: `MissileTurret`, `AutoTurret`, `PlanetaryFortress`
- Ontology-scope subject relations: 0

### Terran_StealthUnits — 3 members

- Parents: `Terran`, `StealthUnits`
- Members: `Ghost`, `Banshee`, `GhostNova`
- Ontology-scope subject relations: 0

### Terran_Structure — 35 members

- Parents: `Terran`, `Structure`
- Members: `TechLab`, `Reactor`, `PointDefenseDrone`, `CommandCenter`, `SupplyDepot`, `Refinery`, `Barracks`, `EngineeringBay`, `MissileTurret`, `Bunker`, `SensorTower`, `GhostAcademy`, `Factory`, `Starport`, `Armory`, `FusionCore`, `AutoTurret`, `CommandCenterFlying`, `BarracksTechLab`, `BarracksReactor`, `FactoryTechLab`, `FactoryReactor`, `StarportTechLab`, `StarportReactor`, `FactoryFlying`, `StarportFlying`, `BarracksFlying`, `SupplyDepotLowered`, `PlanetaryFortress`, `OrbitalCommand`, `OrbitalCommandFlying`, `Elsecaro_Colonist_Hut`, `BypassArmorDrone`, `RavenRepairDrone`, `RefineryRich`
- Ontology-scope subject relations: 0

### Terran_Summoned — 1 members

- Parents: `Terran`, `Summoned`
- Members: `RavenRepairDrone`
- Ontology-scope subject relations: 0

### Terran_SupportUnits — 7 members

- Parents: `Terran`, `SupportUnits`
- Members: `VikingAssault`, `VikingFighter`, `Ghost`, `Thor`, `Medivac`, `Raven`, `ThorAP`
- Ontology-scope subject relations: 0

### Terran_TimedLifeUnits — 3 members

- Parents: `Terran`, `TimedLifeUnits`
- Members: `PointDefenseDrone`, `AutoTurret`, `MULE`
- Ontology-scope subject relations: 0

### Terran_TransportUnits — 1 members

- Parents: `Terran`, `TransportUnits`
- Members: `Medivac`
- Ontology-scope subject relations: 0

### Terran_UnitProducingStructures — 6 members

- Parents: `Terran`, `UnitProducingStructures`
- Members: `CommandCenter`, `Barracks`, `Factory`, `Starport`, `PlanetaryFortress`, `OrbitalCommand`
- Ontology-scope subject relations: 0

### Terran_Workers — 1 members

- Parents: `Terran`, `Workers`
- Members: `SCV`
- Ontology-scope subject relations: 0

### Zerg_AirAttackers — 11 members

- Parents: `Zerg`, `AirAttackers`
- Members: `InfestorTerran`, `ChangelingMarineShield`, `ChangelingMarine`, `SporeCrawler`, `Hydralisk`, `Mutalisk`, `Corruptor`, `Queen`, `NydusCanalAttacker`, `DevourerMP`, `ScourgeMP`
- Ontology-scope subject relations: 0

### Zerg_AirUnits — 18 members

- Parents: `Zerg`, `AirUnits`
- Members: `Overlord`, `Mutalisk`, `Corruptor`, `BroodLordCocoon`, `BroodLord`, `OverlordCocoon`, `Overseer`, `Viper`, `LocustMPFlying`, `GuardianCocoonMP`, `GuardianMP`, `DevourerCocoonMP`, `DevourerMP`, `ScourgeMP`, `QueenMP`, `TransportOverlordCocoon`, `OverlordTransport`, `OverseerSiegeMode`
- Ontology-scope subject relations: 0

### Zerg_Armored — 42 members

- Parents: `Zerg`, `Armored`
- Members: `Hatchery`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `Overlord`, `Ultralisk`, `Roach`, `Infestor`, `Corruptor`, `BroodLord`, `RoachBurrowed`, `InfestorBurrowed`, `Overseer`, `UltraliskBurrowed`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `NydusCanal`, `NydusCanalAttacker`, `NydusCanalCreeper`, `SwarmHostBurrowedMP`, `SwarmHostMP`, `Viper`, `LurkerMP`, `LurkerMPBurrowed`, `LurkerDenMP`, `GuardianMP`, `DevourerMP`, `OverlordTransport`, `OverseerSiegeMode`, `ExtractorRich`
- Ontology-scope subject relations: 0

### Zerg_Biological — 84 members

- Parents: `Zerg`, `Biological`
- Members: `InfestorTerran`, `BanelingCocoon`, `Baneling`, `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `Hatchery`, `CreepTumor`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `Egg`, `Drone`, `Zergling`, `Overlord`, `Hydralisk`, `Mutalisk`, `Ultralisk`, `Roach`, `Infestor`, `Corruptor`, `BroodLordCocoon`, `BroodLord`, `BanelingBurrowed`, `DroneBurrowed`, `HydraliskBurrowed`, `RoachBurrowed`, `ZerglingBurrowed`, `InfestorTerranBurrowed`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `OverlordCocoon`, `Overseer`, `UltraliskBurrowed`, `CreepTumorBurrowed`, `CreepTumorQueen`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `NydusCanal`, `InfestedTerransEgg`, `Larva`, `Broodling`, `LocustMP`, `NydusCanalAttacker`, `NydusCanalCreeper`, `SwarmHostBurrowedMP`, `SwarmHostMP`, `Viper`, `LurkerMPEgg`, `LurkerMP`, `LurkerMPBurrowed`, `LurkerDenMP`, `RavagerCocoon`, `Ravager`, `RavagerBurrowed`, `LocustMPFlying`, `GuardianCocoonMP`, `GuardianMP`, `DevourerCocoonMP`, `DevourerMP`, `DefilerMPBurrowed`, `DefilerMP`, `ScourgeMP`, `QueenMP`, `TransportOverlordCocoon`, `OverlordTransport`, `OverseerSiegeMode`, `ExtractorRich`
- Ontology-scope subject relations: 0

### Zerg_CapitalShips — 3 members

- Parents: `Zerg`, `CapitalShips`
- Members: `BroodLord`, `GuardianMP`, `DevourerMP`
- Ontology-scope subject relations: 0

### Zerg_Detectors — 3 members

- Parents: `Zerg`, `Detectors`
- Members: `SporeCrawler`, `Overseer`, `OverseerSiegeMode`
- Ontology-scope subject relations: 0

### Zerg_GroundAttackers — 23 members

- Parents: `Zerg`, `GroundAttackers`
- Members: `InfestorTerran`, `Baneling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `SpineCrawler`, `Drone`, `Zergling`, `Hydralisk`, `Mutalisk`, `Ultralisk`, `Roach`, `BroodLord`, `Queen`, `Broodling`, `LocustMP`, `NydusCanalAttacker`, `LurkerMP`, `LurkerMPBurrowed`, `Ravager`, `GuardianMP`
- Ontology-scope subject relations: 0

### Zerg_GroundUnits — 67 members

- Parents: `Zerg`, `GroundUnits`
- Members: `InfestorTerran`, `BanelingCocoon`, `Baneling`, `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `Hatchery`, `CreepTumor`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `Egg`, `Drone`, `Zergling`, `Hydralisk`, `Ultralisk`, `Roach`, `Infestor`, `BanelingBurrowed`, `DroneBurrowed`, `HydraliskBurrowed`, `RoachBurrowed`, `ZerglingBurrowed`, `InfestorTerranBurrowed`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `UltraliskBurrowed`, `CreepTumorBurrowed`, `CreepTumorQueen`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `NydusCanal`, `InfestedTerransEgg`, `Larva`, `Broodling`, `InfestedTerransEggPlacement`, `LocustMP`, `NydusCanalAttacker`, `NydusCanalCreeper`, `SwarmHostBurrowedMP`, `SwarmHostMP`, `LurkerMPEgg`, `LurkerMP`, `LurkerMPBurrowed`, `LurkerDenMP`, `RavagerCocoon`, `Ravager`, `RavagerBurrowed`, `DefilerMPBurrowed`, `DefilerMP`, `ExtractorRich`
- Ontology-scope subject relations: 0

### Zerg_Harassers — 4 members

- Parents: `Zerg`, `Harassers`
- Members: `InfestorTerran`, `Baneling`, `Zergling`, `Mutalisk`
- Ontology-scope subject relations: 0

### Zerg_Light — 23 members

- Parents: `Zerg`, `Light`
- Members: `InfestorTerran`, `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `CreepTumor`, `Drone`, `Zergling`, `Hydralisk`, `Mutalisk`, `DroneBurrowed`, `HydraliskBurrowed`, `ZerglingBurrowed`, `InfestorTerranBurrowed`, `CreepTumorBurrowed`, `CreepTumorQueen`, `Larva`, `Broodling`, `LocustMP`, `LocustMPFlying`, `ScourgeMP`
- Ontology-scope subject relations: 0

### Zerg_Massive — 8 members

- Parents: `Zerg`, `Massive`
- Members: `Ultralisk`, `BroodLordCocoon`, `BroodLord`, `UltraliskBurrowed`, `GuardianCocoonMP`, `GuardianMP`, `DevourerCocoonMP`, `DevourerMP`
- Ontology-scope subject relations: 0

### Zerg_MeleeUnits — 8 members

- Parents: `Zerg`, `MeleeUnits`
- Members: `ChangelingZealot`, `ChangelingZerglingWings`, `ChangelingZergling`, `Drone`, `Zergling`, `Ultralisk`, `Broodling`, `ScourgeMP`
- Ontology-scope subject relations: 0

### Zerg_Psionic — 7 members

- Parents: `Zerg`, `Psionic`
- Members: `Infestor`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `Viper`, `DefilerMPBurrowed`, `DefilerMP`
- Ontology-scope subject relations: 0

### Zerg_RangedUnits — 14 members

- Parents: `Zerg`, `RangedUnits`
- Members: `InfestorTerran`, `ChangelingMarineShield`, `ChangelingMarine`, `Hydralisk`, `Mutalisk`, `Roach`, `Corruptor`, `BroodLord`, `Queen`, `LocustMP`, `LurkerMPBurrowed`, `Ravager`, `GuardianMP`, `DevourerMP`
- Ontology-scope subject relations: 0

### Zerg_Scouts — 10 members

- Parents: `Zerg`, `Scouts`
- Members: `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `Zergling`, `Mutalisk`, `Overseer`, `OverseerSiegeMode`
- Ontology-scope subject relations: 0

### Zerg_Spellcasters — 10 members

- Parents: `Zerg`, `Spellcasters`
- Members: `Infestor`, `QueenBurrowed`, `Queen`, `InfestorBurrowed`, `Overseer`, `Viper`, `DefilerMPBurrowed`, `DefilerMP`, `QueenMP`, `OverseerSiegeMode`
- Ontology-scope subject relations: 0

### Zerg_SplashDamageDealers — 6 members

- Parents: `Zerg`, `SplashDamageDealers`
- Members: `Baneling`, `Ultralisk`, `BanelingBurrowed`, `UltraliskBurrowed`, `LurkerMP`, `LurkerMPBurrowed`
- Ontology-scope subject relations: 0

### Zerg_StaticDefenses — 2 members

- Parents: `Zerg`, `StaticDefenses`
- Members: `SpineCrawler`, `SporeCrawler`
- Ontology-scope subject relations: 0

### Zerg_Structure — 26 members

- Parents: `Zerg`, `Structure`
- Members: `Hatchery`, `CreepTumor`, `Extractor`, `SpawningPool`, `EvolutionChamber`, `HydraliskDen`, `Spire`, `UltraliskCavern`, `InfestationPit`, `NydusNetwork`, `BanelingNest`, `RoachWarren`, `SpineCrawler`, `SporeCrawler`, `Lair`, `Hive`, `GreaterSpire`, `CreepTumorBurrowed`, `CreepTumorQueen`, `SpineCrawlerUprooted`, `SporeCrawlerUprooted`, `NydusCanal`, `NydusCanalAttacker`, `NydusCanalCreeper`, `LurkerDenMP`, `ExtractorRich`
- Ontology-scope subject relations: 0

### Zerg_SupportUnits — 1 members

- Parents: `Zerg`, `SupportUnits`
- Members: `Viper`
- Ontology-scope subject relations: 0

### Zerg_TimedLifeUnits — 9 members

- Parents: `Zerg`, `TimedLifeUnits`
- Members: `Changeling`, `ChangelingZealot`, `ChangelingMarineShield`, `ChangelingMarine`, `ChangelingZerglingWings`, `ChangelingZergling`, `Broodling`, `LocustMP`, `LocustMPFlying`
- Ontology-scope subject relations: 0

### Zerg_TransportUnits — 1 members

- Parents: `Zerg`, `TransportUnits`
- Members: `OverlordTransport`
- Ontology-scope subject relations: 0

### Zerg_UnitProducingStructures — 3 members

- Parents: `Zerg`, `UnitProducingStructures`
- Members: `Hatchery`, `Lair`, `Hive`
- Ontology-scope subject relations: 0

### Zerg_Workers — 1 members

- Parents: `Zerg`, `Workers`
- Members: `Drone`
- Ontology-scope subject relations: 0
