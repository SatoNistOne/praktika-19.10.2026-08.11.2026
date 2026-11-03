import unittest

from validation import ensure_nonnegative, integer, iso_date, text


class ValidationTests(unittest.TestCase):
    def test_positive_quantity(self):
        self.assertEqual(integer(' 15 ', 'Количество', 1), 15)

    def test_bad_quantity(self):
        for value in ('0', '-1', '1.5', 'abc', '2147483648', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                integer(value, 'Количество', 1)

    def test_date(self):
        self.assertEqual(iso_date('2026-10-19'), '2026-10-19')
        for value in ('2026-02-30', '19.10.2026', '20261019', '0999-01-01'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                iso_date(value)

    def test_required_name(self):
        self.assertEqual(text(' Бумага ', 'Название', 150), 'Бумага')
        with self.assertRaises(ValueError):
            text('  ', 'Название', 150)

    def test_balance(self):
        rows = [{'kind': 'IN', 'quantity': 150}, {'kind': 'OUT', 'quantity': 30}]
        self.assertEqual(ensure_nonnegative(rows), 120)

    def test_historical_negative(self):
        rows = [{'kind': 'OUT', 'quantity': 1}, {'kind': 'IN', 'quantity': 10}]
        with self.assertRaises(ValueError):
            ensure_nonnegative(rows)


if __name__ == '__main__':
    unittest.main(verbosity=2)
