import base64
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location("https_gateway", Path(__file__).resolve().parents[1] / "aws/https_gateway.py")
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "image/png", "Cache-Control": "no-store"}


class GatewayTests(unittest.TestCase):
    def event(self):
        return {"rawPath": "/api/archive/studies/x/preview/T1", "rawQueryString": "slice=.5", "requestContext": {"http": {"method": "GET"}},
                "headers": {"authorization": "Bearer test-token", "host": "public.lambda-url.test", "cookie": "unrelated"}}

    @patch.dict(os.environ, {"SERVER_IP": "172.31.0.10"})
    def test_private_gateway_forwards_auth_and_binary_response(self):
        with patch.object(gateway.urllib.request, "urlopen", return_value=Response(b"\x89PNG")) as upstream:
            result = gateway.handler(self.event(), None)
            req = upstream.call_args.args[0]
            self.assertEqual(req.full_url, "http://172.31.0.10/api/archive/studies/x/preview/T1?slice=.5")
            self.assertEqual(req.get_header("Authorization"), "Bearer test-token")
            self.assertIsNone(req.get_header("Cookie"))
        self.assertEqual(base64.b64decode(result["body"]), b"\x89PNG")
        self.assertEqual(result["statusCode"], 200)

    @patch.dict(os.environ, {"SERVER_IP": "172.31.0.10"})
    def test_api_error_status_is_preserved(self):
        error = urllib.error.HTTPError("http://upstream", 401, "Unauthorized", {"Content-Type": "application/json"}, io.BytesIO(b'{"error":"sign in"}'))
        with patch.object(gateway.urllib.request, "urlopen", side_effect=error):
            result = gateway.handler(self.event(), None)
        self.assertEqual(result["statusCode"], 401)

    @patch.dict(os.environ, {"SERVER_IP": "172.31.0.10"})
    def test_stopped_server_reports_recoverable_unavailability(self):
        with patch.object(gateway.urllib.request, "urlopen", side_effect=urllib.error.URLError("connection refused")):
            result = gateway.handler(self.event(), None)
        self.assertEqual(result["statusCode"], 503)
