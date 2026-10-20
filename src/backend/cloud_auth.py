"""Cognito authentication for the deployed study API."""
import os

import jwt
from flask import g, jsonify, request


def install_auth(app, verifier=None):
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    pool = os.environ["COGNITO_USER_POOL_ID"]
    client = os.environ["COGNITO_CLIENT_ID"]
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool}"
    keys = jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", cache_keys=True)

    def verify(token):
        claims = jwt.decode(token, keys.get_signing_key_from_jwt(token).key,
                            algorithms=["RS256"], audience=client, issuer=issuer,
                            options={"require": ["exp", "iat", "sub", "aud", "iss", "token_use"]})
        if claims["token_use"] != "id":
            raise jwt.InvalidTokenError("An ID token is required")
        return claims

    @app.before_request
    def authenticate():
        if not request.path.startswith("/api/") or request.path == "/api/health":
            return None
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify(error={"code": "UNAUTHORIZED", "message": "Sign in to access the archive."}), 401
        try:
            claims = (verifier or verify)(authorization[7:])
        except (jwt.PyJWTError, ValueError):
            return jsonify(error={"code": "UNAUTHORIZED", "message": "Your session expired. Sign in again."}), 401
        groups = set(claims.get("cognito:groups", []))
        if not groups.intersection({"viewer", "operator", "archive-admin"}):
            return jsonify(error={"code": "FORBIDDEN", "message": "An archive role is required."}), 403
        if request.method not in ("GET", "HEAD", "OPTIONS") and not groups.intersection({"operator", "archive-admin"}):
            return jsonify(error={"code": "FORBIDDEN", "message": "An operator role is required for this action."}), 403
        g.actor = claims["sub"]
