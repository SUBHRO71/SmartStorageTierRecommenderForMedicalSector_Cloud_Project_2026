"""Small HTTPS Lambda URL gateway; source files upload directly to private S3."""
import base64
import os
import urllib.error
import urllib.request


def handler(event, _context):
    path = event.get("rawPath", "/")
    query = event.get("rawQueryString", "")
    url = "http://" + os.environ["SERVER_IP"] + path + ("?" + query if query else "")
    headers = {k: v for k, v in event.get("headers", {}).items()
               if k.lower() in ("authorization", "content-type", "accept", "user-agent")}
    body = event.get("body")
    data = base64.b64decode(body) if body and event.get("isBase64Encoded") else body.encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=event["requestContext"]["http"]["method"])
    try:
        response = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as error:
        response = error
    except (urllib.error.URLError, TimeoutError):
        return {"statusCode": 503, "headers": {"content-type": "application/json", "cache-control": "no-store"},
                "body": '{"error":{"message":"The archive server is starting or unavailable. Try again shortly."}}'}
    with response:
        content = response.read(4 * 1024 * 1024 + 1)
        if len(content) > 4 * 1024 * 1024:
            return {"statusCode": 502, "body": "Response too large for the pilot gateway"}
        return {"statusCode": response.status, "headers": {k: v for k, v in response.headers.items()
                if k.lower() in ("content-type", "cache-control", "x-content-type-options", "referrer-policy", "x-frame-options")},
                "isBase64Encoded": True, "body": base64.b64encode(content).decode()}
