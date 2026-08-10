# V2 Resource and Supply Forecast

The Derived Planning Snapshot gives current and no-new-spending projected minerals and gas for the horizon. Use that projection as a budget envelope, not as a promise that all future income is available immediately.

- Keep urgent early items affordable from the current bank.
- Let later items consume projected income, but avoid queue totals far above the projection.
- When minerals are banking, prefer immediately usable army and compatible production capacity.
- When gas is the limiting resource, do not fill the queue with gas-heavy units or unrelated upgrades.
- When mineral and gas ratios do not match the desired composition, adjust the composition, production, or gas infrastructure explicitly.
- Treat `resource_conversion_targets` as acceptance criteria, not suggestions: obey the worker-addition ceiling, meet the minimum mineral commitment, and devote the required share to strength-producing work.
- Meet the mobile-strength target with army units. Static defenses and production infrastructure support conversion but cannot replace mobile combat supply.
- If a gas-capacity gap is flagged, add the recommended gas structure so a mineral advantage can support the strategy's gas-heavy units and upgrades.
- Compare bank trend with `combat_state`. Banking while predicted or actual army advantage is negative requires immediate resource-to-strength conversion, not more workers or passive expansion.

For supply, estimate new listed demand and keep a stage-appropriate buffer. Supply providers add 8 cap each. Do not count a provider under construction as completed capacity, but recognize it as committed incoming supply. Do not duplicate active unit queues merely to account for their supply.

Dataset time fields use game loops. Only a value explicitly converted at 22.4 loops per second may be compared with the horizon in seconds.
