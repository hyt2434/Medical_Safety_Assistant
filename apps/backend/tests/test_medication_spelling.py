import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.medication_spelling import suggestions, catalog_rows
from api.routes.reference import router
from api.deps import current_session


class SpellingTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(id="test", name="Desloratadine", strength="5mg", form="tablet", source_record_id="source")]

    def test_typo_and_strength_whitespace(self):
        self.assertEqual(suggestions("Desloratad1ne", "5 mg", self.rows), self.rows)

    def test_accent_and_case_insensitive_candidates(self):
        self.assertEqual(suggestions("DÉSLORATAD1NE", "5 mg", self.rows), self.rows)

    def test_no_guess_for_exact_unknown_short_or_different_strength(self):
        for name, strength in [("desloratadine", "5mg"), ("unknown", ""), ("Des", ""), ("Desloratad1ne", "50mg"), ("Desloratad1ne", "5mcg")]:
            self.assertEqual(suggestions(name, strength, self.rows), [])

    def test_numeric_suffix_not_corrected_and_duplicates_capped(self):
        row = dict(self.rows[0], name="Example 20")
        self.assertEqual(suggestions("Example 10", "", [row]), [])
        self.assertEqual(len(suggestions("Desloratad1ne", "", self.rows * 4)), 1)

    def test_real_catalog_and_authenticated_endpoint(self):
        rows = catalog_rows()
        self.assertGreater(len(rows), 100)
        actual = suggestions("Rechopld 30", "30mg", rows)
        self.assertIn("Rechopid 30", [row["name"] for row in actual])
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        self.assertEqual(client.get("/api/reference/medication-spelling?q=Example").status_code, 401)
        app.dependency_overrides[current_session] = lambda: {"user_id": "test"}
        response = client.get("/api/reference/medication-spelling", params={"q": "Desloratad1ne", "strength": "5mg"})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.json()["suggestions"]), 3)
        self.assertEqual(client.get("/api/reference/medication-spelling", params={"q": "a" * 121}).status_code, 422)
