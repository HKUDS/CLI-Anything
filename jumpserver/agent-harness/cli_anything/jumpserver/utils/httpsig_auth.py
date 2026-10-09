"""HTTP Signature auth for JumpServer AccessKey (v4 REST API).

Implements the draft-cavage HTTP Signatures scheme JMS uses
(common/auth/signature.py + httpsig HeaderVerifier on the server):

    Authorization: Signature keyId="...",algorithm="hmac-sha256",
                   headers="(request-target) date",signature="base64(...)"

No third-party deps: plain hmac/hashlib/base64 from stdlib.
"""
import base64
import hashlib
import hmac
from email.utils import formatdate


def rfc1123_now():
    """UTC Date header in RFC1123 format, as httpsig expects."""
    return formatdate(usegmt=True)


def sign(method, path_with_query, key_id, secret, date=None,
         extra_headers=None):
    """Return dict of headers to attach to the request.

    method: lowercase http method
    path_with_query: e.g. /api/v1/assets/hosts/?limit=10
    """
    date = date or rfc1123_now()
    headers_order = ["(request-target)", "date"]
    lines = ["(request-target): %s %s" % (method.lower(), path_with_query),
             "date: %s" % date]
    signing_string = "\n".join(lines)
    digest = hmac.new(secret.encode("utf-8"),
                      signing_string.encode("utf-8"),
                      hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("ascii")
    auth = ('Signature keyId="%s",algorithm="hmac-sha256",'
            'headers="%s",signature="%s"'
            % (key_id, " ".join(headers_order), signature))
    out = {"Authorization": auth, "Date": date}
    if extra_headers:
        out.update(extra_headers)
    return out
