"""Explicit, allowlisted public citation retrieval. No private text leaves the host."""
import json
import re
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

class WebLookupUnavailable(RuntimeError):
    pass

class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise WebLookupUnavailable("Public citation service redirected the request.")

TOPICS = (
    (r"\b(?:aes|advanced encryption standard)\b", "Advanced Encryption Standard"),
    (r"\b(?:rsa|rivest.shamir.adleman)\b", "RSA (cryptosystem)"),
    (r"\b(?:diffie.hellman)\b", "Diffie–Hellman key exchange"),
    (r"\b(?:tls|transport layer security)\b", "Transport Layer Security"),
    (r"\bhmac\b", "HMAC"),
    (r"\b(?:message authentication code|mac)\b", "Message authentication code"),
    (r"\bdigital signature\b", "Digital signature"),
    (r"\b(?:hash function|cryptographic hash)\b", "Cryptographic hash function"),
    (r"\b(?:data encryption standard|des)\b", "Data Encryption Standard"),
)
API = "https://en.wikipedia.org/w/api.php"
BASE = "https://en.wikipedia.org/wiki/"

def _fetch(request):
    opener = build_opener(ProxyHandler({}), _NoRedirects())
    with opener.open(request, timeout=8) as response:
        raw = response.read(50001)
    if len(raw) > 50000:
        raise ValueError("Response too large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid provider JSON")
    return data

def lookup_public_sources(question: str) -> list[dict]:
    """The outbound HTTPS URL is derived from a fixed article title, never raw input."""
    if not isinstance(question, str):
        raise WebLookupUnavailable("No public topic selected.")
    title = next((article for pattern, article in TOPICS
                  if re.search(pattern, question, flags=re.I)), None)
    if title is None:
        raise WebLookupUnavailable("No approved public lookup topic matched this question.")
    query = urlencode({"action": "query", "prop": "extracts", "exintro": "1",
                       "explaintext": "1", "redirects": "1",
                       "format": "json", "titles": title})
    request = Request(API + "?" + query, headers={
        "Accept": "application/json",
        "User-Agent": "TutorBot-CS5342-Prototype/1.0 (educational citation lookup)",
    })
    try:
        result = _fetch(request)
        pages = result["query"]["pages"]
        if not isinstance(pages, dict) or len(pages) != 1:
            raise ValueError("Invalid encyclopedia pages")
        page = next(iter(pages.values()))
        content = page.get("extract", "")
        if not isinstance(content, str) or not content.strip() or "missing" in page:
            raise ValueError("Missing public article")
        return [{
            "id": "web:wikipedia:" + title.replace(" ", "_"),
            "source": "Wikipedia: " + title,
            "source_type": "web",
            "url": BASE + quote(title.replace(" ", "_"), safe="()"),
            "text": content.strip()[:2800],
            "page": 1, "chunk": 1, "similarity": 1.0,
        }]
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, KeyError, TypeError) as exc:
        raise WebLookupUnavailable("Internet citation lookup failed; retry in local-only mode.") from exc
