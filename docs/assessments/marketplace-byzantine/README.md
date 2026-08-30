# Byzantine agents in the marketplace: the validators never look at what was received

**Scenario:** `marketplace` · **Setting changed:** `failures.byzantine_agents: 0.0 → 0.10`

## The change

[`scenarios/marketplace_byzantine.yaml`](../../../scenarios/marketplace_byzantine.yaml)
is `scenarios/marketplace.yaml` with one setting added:

```diff
  failures:
    message_drop: 0.0
+   byzantine_agents: 0.10
```

`byzantine_agents` defaults to `0.0`, so setting it to `0.10` is a single
change. `message_drop` stays at `0.0`. (`output.trace` is retargeted so the run
does not overwrite the baseline — bookkeeping, not a second variable.)

10 of the 100 agents are flagged byzantine. Every message they send is XOR'd
byte-by-byte with random noise at delivery, so their signatures no longer
verify and the receiver discards the message.

## Why I chose it, and what I predicted

I checked which settings actually do anything before choosing. `catalog_size`
appears in the scenario file but `grep -rn catalog_size` over the installed
package finds no read site — nothing consumes it, and changing it produces an
identical trace. That left `rounds` (a workload dial) and the two failure
settings.

I picked `byzantine_agents` over `message_drop` because it is a different and
harder threat model: not "the network is unreliable" but "some of these agents
are actively dishonest." For a marketplace that eventually has to move money,
that is the case that matters.

**My prediction, written down before running (`PREDICTION.md`):**

| | predicted | actual |
|---|---|---|
| Sales | ~240 (−10%) | **166 (−38%)** ✗ |
| `all_responded` | FAIL | **FAIL** ✓ |
| `price_agreement` | FAIL | **PASS** ✗ |
| `no_double_sell` | PASS | **PASS** ✓ |

My reasoning was that 10% garbage traffic costs 10% of deals, and that a
scrambled price would leave buyer and seller disagreeing. Both were wrong, and
both were wrong for reasons worth understanding.

## What happened

| | baseline | byzantine 10% |
|---|---|---|
| buy requests sent | 500 | **273** |
| sales | 266 | **166** |
| `deal_rate` | 0.532 | **0.608** |
| `delivery_rate` | 1.000 | **1.000** |
| `dropped_count` | 0 | **0** |
| messages | 2000 | 1086 |
| `no_double_sell` | PASS | PASS |
| `all_responded` | PASS | **FAIL — 3 unanswered** |
| `price_agreement` | PASS | PASS |

**Sales fell 38%, not 10%, because the failure cascades.** Buyers sent 273
requests instead of 500 — 227 requests were never issued at all. `BuyerAgent`
sends round N+1 only after a reply to round N arrives, so corrupting one reply
stalls that buyer permanently. Bad agents don't cost you their share of the
traffic, they cost you everything downstream of it.

**`deal_rate` went up, from 0.532 to 0.608**, while a third of the sales
disappeared. It is `sold / buy` over *sent* messages, and the cascade shrinks
both together.

**`delivery_rate` stayed at exactly 1.000 and `dropped_count` at 0.** Nothing
was lost — every message arrived. It just arrived as noise. The delivery
metrics measure transmission, not intelligibility, so corruption is invisible
to them by definition.

Comparing sent against received messages is where the damage actually shows:

| | sent | arrived intact | corrupted |
|---|---|---|---|
| `buy` | 273 | 270 | 3 |
| `sold` | 166 | **147** | **19** |
| `reject` | 104 | 88 | 16 |

## What surprised me, and how I investigated it

`all_responded` reported only **3** unanswered requests. But 100 sales had
vanished. Three missing answers cannot explain a hundred missing sales, so
either the validator or my understanding was wrong.

I read `validators.py`. All three marketplace validators begin the same way:

```python
for ev in events:
    if ev.get("kind") != "send":
        continue
```

**Every validator reads only `send` events. None of them look at what was
received.** Corruption is applied at delivery, so the `send` record is always
clean. That explains both misses at once: `price_agreement` can never fail
under corruption, because it compares sent prices against sent prices; and
`all_responded` counts a request as answered if a reply was *emitted*,
regardless of whether it arrived.

So I wrote `investigate.py` to do the comparison the validators don't: collect
every `sold:` that was sent, collect every `sold:` that arrived, and subtract.

```
sold: emitted by sellers    166
sold: arrived intact        147
ORPHANED SALES              19
unpaid value                1253 credits
```

On the baseline trace the same script reports **0** — so the effect is caused
by the one setting I changed.

Those 19 are the real finding. The seller has added the product to its
`_sold_products` set and will never offer it again. The buyer never received
the confirmation, and since `BuyerAgent` pays only on receiving `sold:`, never
paid. **1,253 credits of goods marked sold and never paid for, and every
safety validator passes.**

## What I take away

The gap is between what agents *said* and what agents *heard*. These validators
audit the first and never the second, so a whole class of settlement failure
lives in the blind spot — inventory committed against payment that never
happens, with a green board.

That is not an argument against validators; `all_responded` was still the only
signal that fired at all, and it is what sent me looking. It is an argument
that a validator over a marketplace has to reconcile both sides of every
exchange, not just the outbound half.

## Reproduce

```bash
nest run scenarios/marketplace_byzantine.yaml
python -c "from pathlib import Path; from nest_core.validators import validate_trace; [print('PASS' if r.passed else 'FAIL', r.name, '-', r.detail) for r in validate_trace(Path('traces/marketplace_byzantine.jsonl'),'marketplace')]"
python docs/assessments/marketplace-byzantine/investigate.py traces/marketplace_byzantine.jsonl
```

## Tools and help

Claude Code (Opus 5), working in a terminal on my own machine. I ran every
command myself and read every output. I chose the setting, wrote the prediction
before running, and was wrong about two of four calls. Claude Code found the
`send`-only line in `validators.py` when I asked why the numbers didn't
reconcile, and wrote `investigate.py` once I understood what comparison was
missing. NANDA Town Quickstart for the CLI; `nest_core` source
(`validators.py`, `simulator.py`, `scenarios_builtin/marketplace.py`) read
directly. No human help.
