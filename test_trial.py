import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trial import CAP, apply, connect, mint, propose, review, show, transfer


def prepare_case(db, key, giver="River"):
    apply(db, propose, key, giver, "Fictional lunch with one extra meal consumed.")
    for role in ("researcher", "reviewer"):
        apply(db, review, f"{key}-{role}", key, role, "supported", "One additional serving.")


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)

    def test_unknown_correction_mint_retry_and_receipt(self):
        db = self.db
        apply(db, propose, "lunch", "River", "One meal delivered.")
        apply(db, review, "first", "lunch", "researcher", "uncertain", "Outcome unknown.")
        apply(db, review, "check", "lunch", "reviewer", "supported", "One additional serving.")
        with self.assertRaisesRegex(ValueError, "pending"):
            apply(db, mint, "lunch")
        apply(db, review, "update", "lunch", "researcher", "supported", "Outcome clarified.")
        receipt = apply(db, mint, "lunch")
        apply(db, review, "challenge", "lunch", "reviewer", "uncertain", "New uncertainty.")
        self.assertEqual(receipt, apply(db, mint, "lunch"))
        self.assertEqual((receipt["research_review"], receipt["independent_review"]), ("update", "check"))
        self.assertEqual(show(db)["trial_supply"], 1)
        with self.assertRaisesRegex(ValueError, "already identifies"):
            apply(db, review, "check", "lunch", "reviewer", "uncertain", "Overwrite attempt.")

    def test_transfers_caps_and_fairness(self):
        db = self.db
        for i in range(CAP + 1):
            prepare_case(db, f"meal-{i}")
            if i < CAP:
                apply(db, mint, f"meal-{i}")
        with self.assertRaisesRegex(ValueError, "cap"):
            apply(db, mint, f"meal-{CAP}")
        receipt = apply(db, transfer, "tip", "River", "Gardener", 3)
        self.assertEqual(receipt, apply(db, transfer, "tip", "River", "Gardener", 3))
        with self.assertRaisesRegex(ValueError, "another transfer"):
            apply(db, transfer, "tip", "River", "Gardener", 4)
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            apply(db, transfer, "large", "Gardener", "River", 4)
        self.assertEqual(show(db)["balances"], {"Gardener": 3, "River": CAP - 3})
        self.assertEqual(show(db)["trial_supply"], CAP)

    def test_tipping_and_recipient_wealth_do_not_change_issuance(self):
        def world(tipped):
            db = connect(":memory:")
            try:
                owner = "Neighbor" if tipped else "SomeoneElse"
                for i in range(5):
                    prepare_case(db, f"prior-{i}", owner)
                    apply(db, mint, f"prior-{i}")
                if tipped:
                    apply(db, transfer, "thanks", "Neighbor", "River", 5)
                prepare_case(db, "same-benefit")
                award = apply(db, mint, "same-benefit")
                return award["amount"], show(db)["trial_supply"], show(db)["balances"]["River"]
            finally:
                db.close()
        self.assertEqual(world(False), (1, 6, 1))
        self.assertEqual(world(True), (1, 6, 6))

    def test_racing_writers_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "research.sqlite3"
            db = connect(path)
            prepare_case(db, "one")
            db.close()

            def execute(action, *args):
                other = connect(path)
                try:
                    return apply(other, action, *args)
                except ValueError as error:
                    return str(error)
                finally:
                    other.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                awards = list(pool.map(lambda _: execute(mint, "one"), range(2)))
                self.assertEqual(awards[0], awards[1])
                moves = list(pool.map(lambda who: execute(transfer, who, "River", who, 1), ("A", "B")))
                self.assertEqual(sum(isinstance(result, dict) for result in moves), 1)
            reopened = connect(path)
            try:
                state = show(reopened)
                self.assertEqual((state["trial_supply"], state["balances"]["River"], len(state["entries"])), (1, 0, 2))
            finally:
                reopened.close()


if __name__ == "__main__":
    unittest.main()
