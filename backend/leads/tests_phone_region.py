"""P19: the country assumed for numbers typed without a country code is a setting, not Jordan hard-coded."""
from django.test import SimpleTestCase, override_settings

from leads.normalize import normalize_phone


class DefaultRegionTests(SimpleTestCase):
    def test_jordan_is_the_default(self):
        self.assertEqual(normalize_phone("0791234567"), "+962791234567")
        self.assertEqual(normalize_phone("٠٧٩١٢٣٤٥٦٧"), "+962791234567")  # Arabic-Indic digits

    @override_settings(DEFAULT_PHONE_REGION="SA")
    def test_saudi_numbers(self):
        self.assertEqual(normalize_phone("0501234567"), "+966501234567")
        self.assertEqual(normalize_phone("966501234567"), "+966501234567")

    @override_settings(DEFAULT_PHONE_REGION="AE")
    def test_emirati_numbers(self):
        self.assertEqual(normalize_phone("0501234567"), "+971501234567")

    @override_settings(DEFAULT_PHONE_REGION="US")
    def test_us_numbers(self):
        self.assertEqual(normalize_phone("2025550123"), "+12025550123")

    @override_settings(DEFAULT_PHONE_REGION="SA")
    def test_a_country_code_always_wins_over_the_default(self):
        self.assertEqual(normalize_phone("+962791234567"), "+962791234567")
        self.assertEqual(normalize_phone("00962791234567"), "+962791234567")
        self.assertEqual(normalize_phone("+962 79 123 4567"), "+962791234567")

    @override_settings(DEFAULT_PHONE_REGION="sa")
    def test_the_code_is_case_insensitive(self):
        self.assertEqual(normalize_phone("0501234567"), "+966501234567")

    @override_settings(DEFAULT_PHONE_REGION="ZZ")
    def test_an_unknown_code_falls_back_to_jordan_instead_of_breaking(self):
        self.assertEqual(normalize_phone("0791234567"), "+962791234567")

    def test_short_input_is_still_empty(self):
        self.assertEqual(normalize_phone("12345"), "")
