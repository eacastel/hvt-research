"""Shared local HVT research ledger. All balances and cases are experimental."""

import argparse
import json
import sqlite3
from pathlib import Path


RULE = "additional-meal-v1"
CAP = 10
ROLES = ("researcher", "reviewer")
VERDICTS = ("supported", "uncertain", "unsupported")
DEFAULT_LEDGER = Path(__file__).with_name("hvt-trial.sqlite3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    outcome TEXT PRIMARY KEY, giver TEXT NOT NULL, summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    seq INTEGER PRIMARY KEY, reference TEXT UNIQUE NOT NULL,
    outcome TEXT NOT NULL REFERENCES cases(outcome), role TEXT NOT NULL,
    verdict TEXT NOT NULL, reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    seq INTEGER PRIMARY KEY, reference TEXT NOT NULL UNIQUE,
    outcome TEXT UNIQUE REFERENCES cases(outcome), sender TEXT, recipient TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0), rule TEXT,
    research_review TEXT REFERENCES reviews(reference), independent_review TEXT REFERENCES reviews(reference),
    CHECK ((sender IS NULL AND outcome IS NOT NULL AND rule IS NOT NULL AND
            research_review IS NOT NULL AND independent_review IS NOT NULL) OR
           (sender IS NOT NULL AND sender <> recipient AND outcome IS NULL AND rule IS NULL AND
            research_review IS NULL AND independent_review IS NULL))
);
"""


def connect(path):
    db = sqlite3.connect(path, isolation_level=None, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    return db


def rows(db, query, params=()):
    return [dict(row) for row in db.execute(query, params)]


def balances(db):
    return {row["account"]: row["balance"] for row in db.execute("""
        SELECT account, SUM(change) AS balance FROM (
            SELECT recipient AS account, amount AS change FROM entries
            UNION ALL SELECT sender, -amount FROM entries WHERE sender IS NOT NULL
        ) GROUP BY account ORDER BY account
    """)}


def latest_reviews(db, outcome):
    result = {}
    for row in db.execute("SELECT role, verdict, reference FROM reviews WHERE outcome=? ORDER BY seq", (outcome,)):
        result[row["role"]] = dict(row)
    return result


def apply(db, action, *args):
    """Serialize decisions against balances, the issuance cap, and the latest reviews."""
    if any(isinstance(value, str) and not value.strip() for value in args):
        raise ValueError("Supply a nonempty value for each field.")
    db.execute("BEGIN IMMEDIATE")
    try:
        result = action(db, *args)
        db.commit()
        return result
    except BaseException:
        db.rollback()
        raise


def propose(db, outcome, giver, summary):
    old = db.execute("SELECT giver, summary FROM cases WHERE outcome=?", (outcome,)).fetchone()
    if old and tuple(old) != (giver, summary):
        raise ValueError("That outcome already has a case. Record further evidence in a review.")
    if not old:
        db.execute("INSERT INTO cases VALUES (?, ?, ?)", (outcome, giver, summary))
    return {"case": outcome, "giver": giver}


def review(db, reference, outcome, role, verdict, reason):
    if role not in ROLES or verdict not in VERDICTS:
        raise ValueError("Unknown trial role or verdict.")
    if not db.execute("SELECT 1 FROM cases WHERE outcome=?", (outcome,)).fetchone():
        raise ValueError("Propose the case before reviewing it.")
    existing = db.execute("SELECT outcome, role, verdict, reason FROM reviews WHERE reference=?",
                          (reference,)).fetchone()
    details = (outcome, role, verdict, reason)
    if existing and tuple(existing) != details:
        raise ValueError("That review reference already identifies another decision.")
    if not existing:
        db.execute("INSERT INTO reviews(reference, outcome, role, verdict, reason) VALUES (?, ?, ?, ?, ?)",
                   (reference, *details))
    return {"case": outcome, "latest_reviews": latest_reviews(db, outcome)}


def mint(db, outcome):
    reference = "mint:" + outcome
    old = db.execute("SELECT * FROM entries WHERE reference=?", (reference,)).fetchone()
    if old:
        return dict(old)
    case = db.execute("SELECT giver FROM cases WHERE outcome=?", (outcome,)).fetchone()
    if not case:
        raise ValueError("Unknown case.")
    opinions = latest_reviews(db, outcome)
    if any(role not in opinions or opinions[role]["verdict"] != "supported" for role in ROLES):
        raise ValueError("Issuance is pending. Both trial roles must support one additional meal.")
    supply = db.execute("SELECT COALESCE(SUM(amount),0) FROM entries WHERE sender IS NULL").fetchone()[0]
    if supply >= CAP:
        raise ValueError("This trial has reached its issuance cap.")
    db.execute("""INSERT INTO entries(reference, outcome, recipient, amount, rule, research_review, independent_review)
                  VALUES (?, ?, ?, 1, ?, ?, ?)""",
               (reference, outcome, case["giver"], RULE,
                opinions["researcher"]["reference"], opinions["reviewer"]["reference"]))
    return dict(db.execute("SELECT * FROM entries WHERE reference=?", (reference,)).fetchone())


def transfer(db, reference, sender, recipient, amount):
    if sender == recipient or type(amount) is not int or amount <= 0:
        raise ValueError("Choose different accounts and a positive whole number of trial HVT.")
    key = "transfer:" + reference
    old = db.execute("SELECT * FROM entries WHERE reference=?", (key,)).fetchone()
    if old:
        if (old["sender"], old["recipient"], old["amount"]) != (sender, recipient, amount):
            raise ValueError("That transfer reference already identifies another transfer.")
        return dict(old)
    if amount > balances(db).get(sender, 0):
        raise ValueError("Insufficient trial HVT.")
    db.execute("INSERT INTO entries(reference, sender, recipient, amount) VALUES (?, ?, ?, ?)",
               (key, sender, recipient, amount))
    return dict(db.execute("SELECT * FROM entries WHERE reference=?", (key,)).fetchone())


def show(db):
    accounts = balances(db)
    return {"rule": RULE, "trial_cap": CAP, "trial_supply": sum(accounts.values()),
            "balances": accounts, "cases": rows(db, "SELECT * FROM cases ORDER BY outcome"),
            "reviews": rows(db, "SELECT * FROM reviews ORDER BY seq"),
            "entries": rows(db, "SELECT * FROM entries ORDER BY seq")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="SQLite file for this trial")
    commands = parser.add_subparsers(dest="command", required=True)
    operations = {
        "show": (show, ()),
        "propose": (propose, ("outcome", "giver", "summary")),
        "review": (review, ("reference", "outcome", "role", "verdict", "reason")),
        "mint": (mint, ("outcome",)),
        "transfer": (transfer, ("reference", "sender", "recipient", "amount")),
    }
    for cmd, (_, fields) in operations.items():
        sub = commands.add_parser(cmd)
        for field in fields:
            if field == "role":
                sub.add_argument(field, choices=ROLES)
            elif field == "verdict":
                sub.add_argument(field, choices=VERDICTS)
            else:
                sub.add_argument(field, type=int if field == "amount" else str)
    args = parser.parse_args()
    action, fields = operations[args.command]
    try:
        db = connect(args.ledger)
        try:
            result = apply(db, action, *(getattr(args, field) for field in fields))
        finally:
            db.close()
    except (ValueError, sqlite3.Error) as err:
        parser.exit(1, f"{err}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
