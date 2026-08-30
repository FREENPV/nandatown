"""Find sales where the seller committed but the buyer never learned.

The simulator corrupts messages from byzantine agents at DELIVERY time, so the
'send' record in the trace is clean and the 'receive' record is garbage. Every
marketplace validator reads only 'send' events, so this failure is invisible
to all of them. This script reads both sides and compares.
"""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "traces/marketplace_byzantine.jsonl"
events = [json.loads(line) for line in open(path) if line.strip()]

emitted = {}   # correlation id -> (seller, buyer, price)
arrived = set()

for e in events:
    msg = e.get("msg", "")
    if e.get("kind") == "send" and msg.startswith("sold:"):
        price = msg.split(":")[2].split("|")[0]
        emitted[e.get("corr")] = (e.get("agent"), e.get("to"), price)
    elif e.get("kind") == "receive" and msg.startswith("sold:"):
        arrived.add(e.get("corr"))

orphans = [v for corr, v in emitted.items() if corr not in arrived]

print(f"sold: emitted by sellers    {len(emitted)}")
print(f"sold: arrived intact        {len(arrived)}")
print(f"ORPHANED SALES              {len(orphans)}")
print(f"unpaid value                {sum(int(p) for _, _, p in orphans)} credits")
print()
for seller, buyer, price in orphans[:5]:
    print(f"  {seller} sold to {buyer} for {price} - {buyer} never got the message, never paid")
