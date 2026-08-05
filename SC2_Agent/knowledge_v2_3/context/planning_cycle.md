# V2 Planning Cycle

Use the live observation for match state and the dataset for static facts. For every final queue:

1. Resolve immediate survival and supply risk first.
2. Read the deterministic horizon projection; do not recalculate fields that are already supplied.
3. Read combat_state and attack_layer_profile, then select a compact set of strategy-compatible spending candidates that can directly engage the observed air/ground layers.
4. Check mineral, gas, listed supply, producers, prerequisites, and upgrade sequencing.
5. Scan prerequisites in queue order. Every dependent item needs its producer and direct requirements already visible/committed or earlier in the queue.
6. Use one focused knowledge packet only when a missing fact can change the queue.
7. Preserve the core strategy while making proportional responses to credible enemy evidence.
8. Satisfy the deterministic worker ceiling, resource conversion target, strength investment target, gas-capacity request, and layer-response score.
9. Return a horizon-executable replacement queue, not a complete rest-of-game build order.

The queue may execute affordable later tasks while an earlier task waits. This does not justify placing a large unaffordable technology wish list in the queue. Put urgent executable work first and keep future enabling work explicit.
