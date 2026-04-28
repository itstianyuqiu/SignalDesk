import unittest

from fastapi.testclient import TestClient

from app.main import create_app


class MainMiddlewareTests(unittest.TestCase):
    def test_unhandled_exceptions_are_sanitized(self) -> None:
        app = create_app()

        @app.get("/_test/boom")
        def boom() -> None:
            raise RuntimeError("top secret failure")

        with TestClient(app) as client:
            response = client.get("/_test/boom")

        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["detail"], "Internal server error.")
        self.assertIn("request_id", body)
        self.assertNotIn("top secret failure", response.text)
        self.assertEqual(response.headers["X-Request-ID"], body["request_id"])
