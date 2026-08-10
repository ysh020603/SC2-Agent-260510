# Decision-Oriented Data Use

The current match observation and the deterministic dataset have different authority boundaries.

- The observation is authoritative for current resources, supply, completed assets, construction, active queues, enemy sightings, map control, and timing.
- The dataset is authoritative for static entity fields, canonical identifiers, production and research links, prerequisites, technology paths, morph direction, typed relations, ontology membership, and documented evidence.
- A dataset entity is not automatically an allowed macro action. The visible Allowed Macro Outputs list is the only executable output vocabulary.
- DataSubAgent replies are evidence summaries, not macro decisions. MainAgent must perform the final prioritization.
- DataSubAgent use is optional per decision. Query when an uncertain production source, prerequisite, counter, morph, upgrade, cost, or identifier could materially change the queue. Skip it when the live observation and visible policy already support a routine decision.

Useful focused questions name one relation or field set, for example:

- "For Terran, what exact prerequisites and producer are required to train SiegeTank?"
- "Which structure researches Stimpack, and what prerequisite or add-on does it require?"
- "What typed counter relations are recorded for the observed enemy unit Mutalisk?"
- "Verify the forward morph chain from Hydralisk to LurkerMP and its enabling requirements."

Do not send the entire decision event to DataSubAgent or ask it to choose the queue. Include only the static fact needed by MainAgent. Never issue a token-consuming query solely to satisfy a fixed call count.
