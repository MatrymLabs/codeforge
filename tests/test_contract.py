"""Test twin for contract.py. Acceptance AND refusal cases, including hostile
input and the tolerant-reader property (extra provider fields are fine; missing
or retyped required fields fail).

Run:  python3 -m unittest test_contract   (or pytest test_contract.py)
"""

from __future__ import annotations

import unittest

from kernel.shelf.contract import (
    Contract,
    ContractError,
    ContractRegistry,
    ContractViolation,
    Field,
    ListOf,
    check,
    verify,
    verify_all,
)

# a consumer that reads a hero object with nested stats and a list of tags
STATS = Contract("hero.stats", "web-client", (Field("level", int), Field("hp", float)))
HERO = Contract(
    "GET /characters item",
    "web-client",
    (
        Field("name", str),
        Field("job", str),
        Field("stats", STATS),
        Field("tags", ListOf(str)),
        Field("guild", str, required=False),
    ),
)


def good_hero() -> dict:
    return {
        "name": "Vael",
        "job": "engineer",
        "stats": {"level": 7, "hp": 42.0},
        "tags": ["veteran", "smith"],
        "extra_field_provider_added": True,  # tolerated
    }


class Declaration(unittest.TestCase):
    def test_valid_contract(self):
        self.assertEqual(HERO.consumer, "web-client")
        self.assertEqual(len(HERO.fields), 5)

    def test_reject_empty_contract_name(self):
        with self.assertRaises(ContractError):
            Contract("", "c", (Field("x", str),))

    def test_reject_empty_consumer(self):
        with self.assertRaises(ContractError):
            Contract("i", "", (Field("x", str),))

    def test_reject_no_fields(self):
        with self.assertRaises(ContractError):
            Contract("i", "c", ())

    def test_reject_empty_field_name(self):
        with self.assertRaises(ContractError):
            Field("", str)

    def test_reject_bad_field_type(self):
        with self.assertRaises(ContractError):
            Field("x", object)  # object is not a supported scalar/Contract/ListOf


class Verify(unittest.TestCase):
    def test_good_sample_satisfies(self):
        self.assertEqual(verify(HERO, good_hero()), [])

    def test_extra_provider_field_is_tolerated(self):
        # the tolerant-reader principle: the extra field above does not fail
        self.assertEqual(verify(HERO, good_hero()), [])

    def test_missing_required_field_fails(self):
        sample = good_hero()
        del sample["job"]
        violations = verify(HERO, sample)
        self.assertEqual(violations, ["job: required field missing"])

    def test_optional_field_absent_is_ok(self):
        sample = good_hero()  # no "guild"
        self.assertEqual(verify(HERO, sample), [])

    def test_wrong_scalar_type_fails_with_path(self):
        sample = good_hero()
        sample["name"] = 123
        self.assertIn("name: expected str, got int", verify(HERO, sample))

    def test_nested_violation_reports_path(self):
        sample = good_hero()
        sample["stats"]["level"] = "seven"
        self.assertIn("stats.level: expected int, got str", verify(HERO, sample))

    def test_bool_is_not_int(self):
        sample = good_hero()
        sample["stats"]["level"] = True  # bool must not satisfy int
        self.assertIn("stats.level: expected int, got bool", verify(HERO, sample))

    def test_int_satisfies_float(self):
        sample = good_hero()
        sample["stats"]["hp"] = 42  # JSON number as int is fine for float
        self.assertEqual(verify(HERO, sample), [])

    def test_list_element_type_checked(self):
        sample = good_hero()
        sample["tags"] = ["ok", 5]
        self.assertIn("tags[1]: expected str, got int", verify(HERO, sample))

    def test_list_field_given_non_list(self):
        sample = good_hero()
        sample["tags"] = "not-a-list"
        self.assertIn("tags: expected a list, got str", verify(HERO, sample))

    def test_non_dict_sample_fails(self):
        self.assertIn("expected an object", verify(HERO, ["not", "a", "dict"])[0])

    def test_list_of_nested_contract(self):
        party = Contract("party", "web-client", (Field("members", ListOf(STATS)),))
        ok = {"members": [{"level": 1, "hp": 1.0}, {"level": 2, "hp": 2.0}]}
        self.assertEqual(verify(party, ok), [])
        bad = {"members": [{"level": 1, "hp": 1.0}, {"hp": 2.0}]}
        self.assertIn("members[1].level: required field missing", verify(party, bad))


class Check(unittest.TestCase):
    def test_check_passes_silently(self):
        check(HERO, good_hero())  # no raise

    def test_check_raises_on_violation(self):
        sample = good_hero()
        del sample["name"]
        with self.assertRaises(ContractViolation):
            check(HERO, sample)


class Registry(unittest.TestCase):
    def test_provider_verifies_all_consumers(self):
        reg = ContractRegistry()
        mobile = Contract(
            "GET /characters item", "mobile-client", (Field("name", str), Field("rank", str))
        )
        reg.register(HERO)
        reg.register(mobile)
        sample = good_hero()  # has no "rank" that the mobile client needs
        violations = verify_all(reg, "GET /characters item", sample)
        # web-client is satisfied; mobile-client is not -> the provider test fails
        self.assertEqual(violations, ["[mobile-client] rank: required field missing"])

    def test_interactions_listed(self):
        reg = ContractRegistry()
        reg.register(HERO)
        self.assertEqual(reg.interactions(), ["GET /characters item"])

    def test_register_rejects_non_contract(self):
        with self.assertRaises(ContractError):
            ContractRegistry().register("not a contract")

    def test_unknown_interaction_is_empty(self):
        self.assertEqual(verify_all(ContractRegistry(), "nope", {}), [])


if __name__ == "__main__":
    unittest.main()
