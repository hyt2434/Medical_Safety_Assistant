import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from auth.db import reset_connection


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        os.environ["AUTH_DB_PATH"] = str(Path(self.directory.name) / "auth.sqlite")
        reset_connection()
        from api.app import app

        self.client = TestClient(app, headers={"origin": "http://127.0.0.1:5173"})

    def tearDown(self) -> None:
        reset_connection()
        self.directory.cleanup()

    def test_login_me_and_logout(self) -> None:
        login = self.client.post(
            "/api/auth/login",
            json={"email": "mai.demo@example.com", "password": "Mai-patient-2026"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["roles"], ["patient"])
        self.assertIn("msa_session", login.cookies)
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["account"]["email"], "mai.demo@example.com")
        logout = self.client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_wrong_password_and_locked_account(self) -> None:
        wrong = self.client.post(
            "/api/auth/login",
            json={"email": "mai.demo@example.com", "password": "nope"},
        )
        self.assertEqual(wrong.status_code, 401)
        locked = self.client.post(
            "/api/auth/login",
            json={"email": "locked.demo@example.com", "password": "Locked-patient-2026"},
        )
        self.assertEqual(locked.status_code, 403)

    def test_single_and_multi_role_payloads(self) -> None:
        admin = self.client.post(
            "/api/auth/login",
            json={"email": "ha.demo@example.com", "password": "Ha-admin-2026"},
        )
        self.assertEqual(admin.json()["roles"], ["admin"])
        multi = self.client.post(
            "/api/auth/login",
            json={"email": "multi.demo@example.com", "password": "Multi-role-2026"},
        )
        self.assertEqual(multi.json()["roles"], ["hcp", "medical_reviewer"])

    def test_admin_guard(self) -> None:
        self.assertEqual(self.client.get("/api/admin/status").status_code, 401)
        self.client.post(
            "/api/auth/login",
            json={"email": "mai.demo@example.com", "password": "Mai-patient-2026"},
        )
        self.assertEqual(self.client.get("/api/admin/status").status_code, 403)
        self.client.post("/api/auth/logout")
        self.client.post(
            "/api/auth/login",
            json={"email": "ha.demo@example.com", "password": "Ha-admin-2026"},
        )
        allowed = self.client.get("/api/admin/status")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["email"], "ha.demo@example.com")
        me = self.client.get("/api/auth/me")
        self.assertIn("admin.roles", me.json()["permissions"])
        denied = self.client.post(
            "/api/v1/ocr/extractions",
            files={"file": ("prescription.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(denied.status_code, 403)
        grant = self.client.post(
            "/api/admin/role-grants",
            json={"userId": "u-support", "roleCode": "hcp", "granted": True},
        )
        self.assertEqual(grant.status_code, 200)
        support = next(item for item in grant.json()["accounts"] if item["id"] == "u-support")
        self.assertIn("hcp", support["roles"])
        self.assertIn("clinical.case_review", support["permissions"])


if __name__ == "__main__":
    unittest.main()
