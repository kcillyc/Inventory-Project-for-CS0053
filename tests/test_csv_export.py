"""Inventory export is exact, complete, and safe to open in a spreadsheet."""

import csv
import io
import tempfile
import unittest
from pathlib import Path
from application_connection import create_application


class CsvExportTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.connection = create_application(Path(self.folder.name) / "stock.db")
        self.service = self.connection.service

    def rows(self):
        result = self.connection.execute("export_csv")
        self.assertTrue(result.ok, result.error)
        return list(csv.reader(io.StringIO(result.data)))

    def test_empty_export_contains_headers(self):
        self.assertEqual(len(self.rows()), 1)

    def test_export_escapes_formulas_commas_and_quotes(self):
        self.service.create_product("P-1", "=SUM(1,2)", "@School", 3, 125, 2)
        self.service.create_product("P-2", 'A "quoted" name', "Office", 2, 250, 1)
        rows = self.rows()
        self.assertEqual(rows[1][1], "'=SUM(1,2)")
        self.assertEqual(rows[1][2], "'@School")
        self.assertEqual(rows[1][-1], "3.75")
        self.assertEqual(rows[2][1], 'A "quoted" name')

    def test_export_excludes_archived_and_preserves_large_exact_values(self):
        archived = self.service.create_product("OLD-1", "Old", "School", 0, 100, 0)
        self.service.archive_product(archived.id)
        self.service.create_product("BIG-1", "Big", "School", 1234567, 999999999999999999, 0)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        total = 1234567 * 999999999999999999
        self.assertEqual(rows[1][-1], f"{total//100}.{total%100:02d}")
