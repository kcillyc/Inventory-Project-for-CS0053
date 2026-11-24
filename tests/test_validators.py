"""Regression checks for the validation differences found between team versions."""

import unittest
from backend.validators import (
    MAX_INTEGER,
    normalize_sku,
    validate_adjustment,
    validate_id,
    validate_non_negative_integer,
    validate_reason,
    validate_search,
    validate_text,
)


class ValidatorTests(unittest.TestCase):
    def test_text_types_are_rejected_with_value_error(self):
        for value in (None, True, 1, 1.5, [], {}):
            for operation in (
                lambda: normalize_sku(value),
                lambda: validate_text(value, "Name", 100),
                lambda: validate_reason(value),
                lambda: validate_search(value),
            ):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    operation()

    def test_text_is_trimmed_and_bounded(self):
        self.assertEqual(validate_text(" Notebook ", "Name", 100), "Notebook")
        for value in ("", " ", "x" * 101, "A\nB", "A\x1bB", "A\x7fB"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_text(value, "Name", 100)

    def test_sku_character_and_length_rules(self):
        self.assertEqual(normalize_sku(" st-001_a "), "ST-001_A")
        for sku in ("BAD SKU", "A/B", "_A", "A" * 31, "", "A\nB"):
            with self.subTest(sku=sku), self.assertRaises(ValueError):
                normalize_sku(sku)

    def test_empty_search_intentionally_lists_all(self):
        self.assertEqual(validate_search("  "), "")
        with self.assertRaises(ValueError):
            validate_search("x" * 101)

    def test_identifiers_reject_bool_fraction_null_and_range_errors(self):
        for value in (None, True, False, 0, -1, 1.5, "1", MAX_INTEGER + 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_id(value)
        self.assertEqual(validate_id(1), 1)

    def test_nonnegative_values_have_sqlite_bounds(self):
        self.assertEqual(validate_non_negative_integer(0, "Cost"), 0)
        self.assertEqual(validate_non_negative_integer(MAX_INTEGER, "Cost"), MAX_INTEGER)
        for value in (-1, MAX_INTEGER + 1, True, None, 2.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_non_negative_integer(value, "Cost")

    def test_adjustment_is_signed_and_nonzero(self):
        self.assertEqual(validate_adjustment(-5), -5)
        for value in (0, True, None, 1.5, MAX_INTEGER + 1, -(2**63) - 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_adjustment(value)

    def test_reason_boundaries(self):
        self.assertEqual(validate_reason(" Delivery "), "Delivery")
        self.assertEqual(len(validate_reason("x" * 200)), 200)
        for value in ("ab", "x" * 201, None, "A\nB"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_reason(value)
