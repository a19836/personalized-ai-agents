from __future__ import annotations

import unittest
from pathlib import Path
import sys
from typing import Any, cast

from flask import Flask, request as flask_request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.http import normalize_json_payload, parse_json_request  # noqa: E402


class HttpHelpersTest(unittest.TestCase):
    def test_normalize_json_payload_decodes_stringified_json(self) -> None:
        payload = '{"title":"bbbb1","body":"bb b b  b12"}'
        normalized = normalize_json_payload(payload)
        self.assertEqual(normalized["title"], "bbbb1")

    def test_parse_json_request_accepts_stringified_json_body(self) -> None:
        flask_app = Flask(__name__)
        with flask_app.test_request_context(
            "/login",
            method="POST",
            data='"{\\"email\\":\\"test@test.com\\",\\"password\\":\\"secret\\"}"',
            content_type="application/json",
        ):
            parsed = parse_json_request(cast(Any, flask_request)._get_current_object())

        self.assertEqual(parsed["email"], "test@test.com")


if __name__ == "__main__":
    unittest.main()
