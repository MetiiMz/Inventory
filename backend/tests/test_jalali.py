# -*- coding: utf-8 -*-
"""Tests for inventory.jalali — Jalali↔Gregorian conversion and formatting."""
import datetime

from django.test import TestCase

from inventory.jalali import (
    fa_num, gregorian_to_jalali, is_jalali_leap, jalali_month_length,
    jalali_to_gregorian, parse_jalali_date, today_jalali,
)

ROUND_TRIP_DATES = [
    (2026, 1, 1), (2026, 9, 10), (2024, 2, 29), (2025, 12, 31),
    (2026, 3, 21), (2026, 6, 15), (2000, 3, 20), (1999, 12, 31),
]


class GregorianJalaliConversionTests(TestCase):
    """Core conversion math — known pairs plus round-trips."""

    def test_known_gregorian_to_jalali(self):
        """Documented anchor dates convert to the expected Jalali dates."""
        self.assertEqual(gregorian_to_jalali(2026, 3, 21), (1405, 1, 1))
        self.assertEqual(gregorian_to_jalali(2026, 9, 10), (1405, 6, 19))
        self.assertEqual(gregorian_to_jalali(2024, 3, 20), (1403, 1, 1))

    def test_known_jalali_to_gregorian(self):
        """Nowruz and end-of-year Jalali dates map to the right Gregorian day."""
        self.assertEqual(jalali_to_gregorian(1405, 1, 1), (2026, 3, 21))
        self.assertEqual(jalali_to_gregorian(1404, 12, 29), (2026, 3, 20))
        self.assertEqual(jalali_to_gregorian(1403, 1, 1), (2024, 3, 20))

    def test_round_trip_both_directions(self):
        """g→j→g and j→g→j are identity for a spread of real dates."""
        for gy, gm, gd in ROUND_TRIP_DATES:
            jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
            self.assertEqual(jalali_to_gregorian(jy, jm, jd), (gy, gm, gd))
        for jy, jm, jd in [(1400, 1, 1), (1403, 12, 30), (1405, 6, 19)]:
            gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
            self.assertEqual(gregorian_to_jalali(gy, gm, gd), (jy, jm, jd))

    def test_leap_year_and_month_lengths(self):
        """Leap detection matches month lengths; Esfand is 29/30."""
        self.assertEqual(jalali_month_length(1405, 1), 31)
        self.assertEqual(jalali_month_length(1405, 6), 31)
        self.assertEqual(jalali_month_length(1405, 7), 30)
        self.assertEqual(jalali_month_length(1405, 11), 30)
        self.assertIn(jalali_month_length(1405, 12), (29, 30))
        self.assertEqual(jalali_month_length(1403, 12), 30)  # 1403 is a leap year
        self.assertTrue(is_jalali_leap(1403))
        self.assertFalse(is_jalali_leap(1405))

    def test_today_jalali_matches_today(self):
        """today_jalali() round-trips to the actual today."""
        jy, jm, jd = today_jalali()
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        self.assertEqual((gy, gm, gd), datetime.date.today().timetuple()[:3])


class FaNumTests(TestCase):
    """Latin→Persian digit translation."""

    def test_digits(self):
        self.assertEqual(fa_num("0123456789"), "۰۱۲۳۴۵۶۷۸۹")

    def test_mixed_and_non_digits_untouched(self):
        self.assertEqual(fa_num("TT-1405-0001"), "TT-۱۴۰۵-۰۰۰۱")
        self.assertEqual(fa_num("abc"), "abc")


class ParseJalaliDateTests(TestCase):
    """Accepts Persian/Latin digits, several separators, ISO and 8-digit."""

    def test_persian_digits_with_slashes(self):
        self.assertEqual(parse_jalali_date("۱۴۰۵/۰۶/۱۹"), "2026-09-10")

    def test_latin_digits_and_dashes(self):
        self.assertEqual(parse_jalali_date("1405-6-19"), "2026-09-10")

    def test_iso_gregorian_passthrough(self):
        self.assertEqual(parse_jalali_date("2026-09-10"), "2026-09-10")

    def test_compact_8_digit(self):
        self.assertEqual(parse_jalali_date("14050619"), "2026-09-10")
        self.assertEqual(parse_jalali_date("20260910"), "2026-09-10")

    def test_dot_and_space_separators(self):
        self.assertEqual(parse_jalali_date("1405.06.19"), "2026-09-10")
        self.assertEqual(parse_jalali_date("1405 06 19"), "2026-09-10")

    def test_invalid_inputs_return_none(self):
        for bad in ("", "  ", "abc", "1405/13/01", "1405/00/10",
                    "1405/06/32", "12/34", "۱"):
            self.assertIsNone(parse_jalali_date(bad), bad)

    def test_none_returns_none(self):
        self.assertIsNone(parse_jalali_date(None))
