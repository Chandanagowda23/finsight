"""Synthetic customer/account generator — no real PII, ever."""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass


FIRST = ["Alex", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Taylor", "Quinn"]
LAST = ["Rivera", "Lee", "Patel", "Nguyen", "Brooks", "Hayes", "Coleman", "Diaz"]


@dataclass
class SyntheticCustomer:
    customer_id: str
    name: str
    email: str
    accounts: list[str]


def _stable_rng(seed: str) -> random.Random:
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    return random.Random(h)


def generate_customers(n: int = 20, seed: str = "finsight") -> list[SyntheticCustomer]:
    rng = _stable_rng(seed)
    out: list[SyntheticCustomer] = []
    for i in range(1, n + 1):
        first = rng.choice(FIRST)
        last = rng.choice(LAST)
        cid = f"CUST-{1000 + i}"
        email = f"{first.lower()}.{last.lower()}.{i}@example.com"
        accounts = [f"ACC-CHK-{1000 + i}"]
        if rng.random() > 0.3:
            accounts.append(f"ACC-SAV-{1000 + i}")
        if rng.random() > 0.5:
            accounts.append(f"ACC-CRD-{1000 + i}")
        out.append(SyntheticCustomer(customer_id=cid, name=f"{first} {last}", email=email, accounts=accounts))
    return out


if __name__ == "__main__":
    import json

    print(json.dumps([asdict(c) for c in generate_customers()], indent=2))
