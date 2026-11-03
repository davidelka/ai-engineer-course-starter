"""Exercise 7b: a SQL tool that the model calls with an argument it chose.

The model's argument is untrusted (an injected ticket comment can choose it). Compare the
f-string version with the parameterized one, on a normal name and on injection payloads.

    python labs/24-ai-security/sql_demo.py
"""

from __future__ import annotations

import _common  # noqa: F401

from guardkit.render import find_customer_tickets, find_tickets_unsafe, open_readonly  # noqa: E402

NAMES = ["Pine Systems", "x' OR '1'='1", "Pine Systems' UNION SELECT id, name, plan, region, currency FROM customers --"]


def main() -> None:
    con = open_readonly()
    impls = [("unsafe f-string", find_tickets_unsafe), ("reference parameterized", find_customer_tickets)]
    try:
        import mine
        mine.find_customer_tickets(con, "Pine Systems")
        impls.append(("YOUR mine.find_customer_tickets", mine.find_customer_tickets))
    except NotImplementedError:
        pass
    for name in NAMES:
        print(f"\ncustomer_name = {name!r}")
        for label, fn in impls:
            try:
                rows = fn(con, name)
                print(f"   {label:<32} {len(rows):>3} rows   e.g. {rows[0] if rows else '-'}")
            except Exception as exc:  # noqa: BLE001
                print(f"   {label:<32} ERROR {type(exc).__name__}: {exc}")
    try:
        con.execute("DELETE FROM tickets")
    except Exception as exc:  # noqa: BLE001
        print(f"\nread-only connection, DELETE refused: {exc}")


if __name__ == "__main__":
    main()
