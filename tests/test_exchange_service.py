"""Repeatable adapter tests with controlled responses; no internet needed."""

import io
import json
import unittest
from http.client import BadStatusLine, IncompleteRead
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from backend.exchange_service import fetch_exchange_rate

QUOTE = {"base": "PHP", "quote": "USD", "rate": 0.015754, "date": "2026-11-12"}


def response(data=QUOTE, raw=None, status=200):
    result = io.BytesIO(json.dumps(data).encode() if raw is None else raw)
    result.status = status
    return result


class ExchangeServiceTests(unittest.TestCase):
    @patch("backend.exchange_service.urlopen")
    def test_real_request_contract_and_response_fields(self, transport):
        transport.return_value = response()
        result = fetch_exchange_rate()
        request = transport.call_args.args[0]
        self.assertEqual(
            request.full_url, "https://api.frankfurter.dev/v2/rate/php/usd"
        )
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(transport.call_args.kwargs["timeout"], 8)
        self.assertEqual(
            result, {**QUOTE, "rate": "0.015754", "provider": "Frankfurter"}
        )

    @patch("backend.exchange_service.urlopen")
    def test_supported_targets_are_normalized(self, transport):
        for code in ("USD", "EUR", "SGD", "JPY", "GBP"):
            with self.subTest(code=code):
                transport.return_value = response({**QUOTE, "quote": code})
                self.assertEqual(
                    fetch_exchange_rate(f" {code.lower()} ")["quote"], code
                )

    @patch("backend.exchange_service.urlopen")
    def test_invalid_input_never_sends_request(self, transport):
        for target in (None, 1, "", "ABC", "../../usd", "PHP"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                fetch_exchange_rate(target)
        transport.assert_not_called()

    @patch("backend.exchange_service.urlopen")
    def test_numeric_precision_is_preserved(self, transport):
        transport.return_value = response(
            raw=b'{"base":"PHP","quote":"USD","rate":0.015754123456789123,"date":"2026-11-12"}'
        )
        self.assertEqual(fetch_exchange_rate()["rate"], "0.015754123456789123")

    @patch("backend.exchange_service.urlopen")
    def test_http_errors_include_status(self, transport):
        for status in (404, 500):
            transport.side_effect = HTTPError(
                "https://example.invalid", status, "Error", {}, None
            )
            with self.subTest(status=status), self.assertRaisesRegex(
                RuntimeError, str(status)
            ):
                fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_rate_limit_error_explains_wait(self, transport):
        transport.side_effect = HTTPError(
            "https://example.invalid", 429, "Error", {}, None
        )
        with self.assertRaisesRegex(RuntimeError, "Wait"):
            fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_network_and_timeout_errors_are_useful(self, transport):
        for error in (URLError("Offline"), TimeoutError("Timed out")):
            transport.side_effect = error
            with self.subTest(error=error), self.assertRaisesRegex(
                RuntimeError, "internet"
            ):
                fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_interrupted_response_body_has_useful_error(self, transport):
        interrupted = response()
        transport.return_value = interrupted
        with patch.object(
            interrupted, "read", side_effect=IncompleteRead(b'{"base":"PHP",', 20)
        ), self.assertRaisesRegex(RuntimeError, "internet"):
            fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_malformed_http_status_has_useful_error(self, transport):
        transport.side_effect = BadStatusLine("Invalid HTTP status")
        with self.assertRaisesRegex(RuntimeError, "internet"):
            fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_empty_and_malformed_responses_are_rejected(self, transport):
        for raw in (b"", b"{}", b"[]", b"null", b"not JSON", b"\xff"):
            transport.return_value = response(raw=raw)
            with self.subTest(raw=raw), self.assertRaisesRegex(
                RuntimeError, "invalid data"
            ):
                fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_oversized_response_is_rejected(self, transport):
        transport.return_value = response(raw=b"x" * 65537)
        with self.assertRaisesRegex(RuntimeError, "invalid data"):
            fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_wrong_pair_is_rejected(self, transport):
        for changes in ({"base": "EUR"}, {"quote": "GBP"}):
            transport.return_value = response({**QUOTE, **changes})
            with self.subTest(changes=changes), self.assertRaisesRegex(
                RuntimeError, "invalid data"
            ):
                fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_invalid_rates_are_rejected(self, transport):
        for rate in (
            0,
            -1,
            True,
            None,
            "0.015754",
            1000000,
            float("nan"),
            float("inf"),
        ):
            transport.return_value = response({**QUOTE, "rate": rate})
            with self.subTest(rate=rate), self.assertRaisesRegex(
                RuntimeError, "invalid data"
            ):
                fetch_exchange_rate()

    @patch("backend.exchange_service.urlopen")
    def test_invalid_dates_are_rejected(self, transport):
        for observed in (None, "", "2026-02-30", "20261112", "today"):
            transport.return_value = response({**QUOTE, "date": observed})
            with self.subTest(observed=observed), self.assertRaisesRegex(
                RuntimeError, "invalid data"
            ):
                fetch_exchange_rate()


if __name__ == "__main__":
    unittest.main()
