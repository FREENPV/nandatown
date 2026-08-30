# Prediction — written before running

**Experiment:** marketplace scenario, `failures.byzantine_agents: 0.0 -> 0.10`
(10% of the 100 agents send corrupted messages; every byte XOR'd with a random
value, so their signatures no longer verify.)

**Baseline to beat:** 500 buy requests, 266 sales, `deal_rate` 0.532,
all three validators PASS.

## 1. Sales

About 10% lower — roughly 240. If 10% of the traffic is garbage, then 10% of
the deals that would have happened don't.

## 2. Validators

| Validator | Prediction |
|---|---|
| `marketplace_all_responded` | **FAIL** |
| `marketplace_price_agreement` | **FAIL** |
| `marketplace_no_double_sell` | **PASS** |

## 3. Reasoning

A garbage message means no deal happens. Some agents won't know another agent
wants to buy, because the request arrived as garbage and never gets an answer —
so `all_responded` should fail.

`price_agreement` could fail because a request might arrive intact while the
price field is scrambled, leaving buyer and seller disagreeing about what was
actually paid.

`no_double_sell` should be unaffected. Corruption stops deals from happening;
it shouldn't cause the same item to be sold twice.
