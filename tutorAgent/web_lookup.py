"""Opt-in Wikipedia citation lookup. Course documents never leave the host."""
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

# First match wins, so specific topics come before general ones (Triple DES before DES,
# modes of operation before block cipher). Article titles were checked to exist on Wikipedia.
TOPICS = (
    (r"\b(?:aes|advanced encryption standard)\b", "Advanced Encryption Standard"),
    (r"\b(?:rsa|rivest.shamir.adleman)\b", "RSA (cryptosystem)"),
    (r"\b(?:diffie.hellman)\b", "Diffie–Hellman key exchange"),
    (r"\b(?:tls|transport layer security)\b", "Transport Layer Security"),
    (r"\bhmac\b", "HMAC"),
    (r"\b(?:message authentication code|mac(?!\s+address))\b", "Message authentication code"),
    (r"\bdigital signature\b", "Digital signature"),
    (r"\b(?:hash function|cryptographic hash)\b", "Cryptographic hash function"),
    (r"\b(?:triple des|3des)\b", "Triple DES"),
    (r"\b(?:data encryption standard|des)\b", "Data Encryption Standard"),
    (r"\bfeistel\b", "Feistel cipher"),
    (r"\b(?:modes? of operation|ecb|cbc)\b", "Block cipher mode of operation"),
    (r"\bblock ciphers?\b", "Block cipher"),
    (r"\bstream ciphers?\b", "Stream cipher"),
    (r"\b(?:confusion|diffusion)\b", "Confusion and diffusion"),
    (r"\b(?:brute.force|exhaustive key search)\b", "Brute-force attack"),
    (r"\bcryptanalysis\b", "Cryptanalysis"),
    (r"\b(?:symmetric|secret.key|shared.key) (?:encryption|key|cipher|cryptography)", "Symmetric-key algorithm"),
    (r"\b(?:public.key|asymmetric) (?:encryption|cryptography|key)", "Public-key cryptography"),
    (r"\b(?:man.in.the.middle|mitm)\b", "Man-in-the-middle attack"),
    (r"\breplay attacks?\b", "Replay attack"),
    (r"\b(?:denial.of.service|dos|ddos)\b", "Denial-of-service attack"),
    (r"\b(?:passive attacks?|eavesdropping)\b", "Eavesdropping"),
    (r"\bthreat models?\b", "Threat model"),
    (r"\b(?:x\.800|security services?|osi security architecture)\b", "Security service (telecommunication)"),
    (r"\b(?:confidentiality|integrity|availability|cia triad|security requirements?)\b", "Information security"),
)
API = "https://en.wikipedia.org/w/api.php"
BASE = "https://en.wikipedia.org/wiki/"

MAX_RESPONSE_BYTES = 400_000  # a whole article's plain text; the largest are about 200 KB


def _fetch(request):
    opener = build_opener(ProxyHandler({}), _NoRedirects())
    with opener.open(request, timeout=8) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Response too large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid provider JSON")
    return data

# Words that carry no topic; everything else in the question may be sent as a search keyword.
STOPWORDS = frozenset("""
a about above after again all also an and any are as at be because been before being below
between both but by can could did do does doing during each explain few for from give had has
have how i if in into is it its just me more most my no nor not of off on once only or other our
out over own please same she should so some such tell than that the their them then there these
they this those through to too under until up very was we were what when where which while who
whom why will with would you your example examples difference differences between mean means
meaning describe define definition work works role used use using purpose
""".split())
MAX_TERMS = 6
MAX_QUERY_CHARS = 80
MIN_SEARCH_SIMILARITY = 0.55  # on-topic hits scored 0.74-0.87 in testing; off-topic ones up to 0.52
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "TutorBot-CS5342-Prototype/1.0 (educational citation lookup; https://github.com/walkmoody/NetworkSecurityFinalProject)",
}


def search_terms(question: str) -> str:
    """Keywords from the student's question only: letters/digits, no stopwords, at most 6."""
    words = re.findall(r"[a-z0-9][a-z0-9\-.]*[a-z0-9]|[a-z0-9]", question.lower())
    terms = []
    for word in words:
        if word not in STOPWORDS and len(word) > 1 and word not in terms:
            terms.append(word)
    return " ".join(terms[:MAX_TERMS])[:MAX_QUERY_CHARS].strip()


SEARCH_RESULTS = 3
MAX_WEB_CHARS = 2800      # text handed to the model, same budget as before
PASSAGE_CHARS = 700       # article paragraphs are grouped into passages about this long


def _best_match(question: str, pages: list[dict]) -> dict | None:
    """The search hit closest to the question read as a security question, if close enough.

    Scoring runs on the local embedding model, so nothing extra is sent anywhere.
    """
    from rag_pipeline.embeddings import load_embedding_model  # loaded once per process
    model = load_embedding_model()
    vectors = model.encode([question + " (network security, cryptography)"]
                           + [p["extract"][:1000] for p in pages], normalize_embeddings=True)
    scores = [float(vectors[0] @ v) for v in vectors[1:]]
    best = max(range(len(pages)), key=scores.__getitem__)
    return pages[best] if scores[best] >= MIN_SEARCH_SIMILARITY else None


def _passages(text: str) -> list[str]:
    """Group the article's paragraphs into passages of about PASSAGE_CHARS."""
    passages, current = [], ""
    for paragraph in (p.strip() for p in text.split("\n")):
        if not paragraph:
            continue
        if current and len(current) + len(paragraph) > PASSAGE_CHARS:
            passages.append(current)
            current = ""
        current = (current + " " + paragraph).strip()
    if current:
        passages.append(current)
    return passages


def _relevant_text(question: str, article: str) -> str:
    """The article's intro plus the passages closest to the question, in article order.

    An article's intro rarely answers a specific question (the Firewall intro never mentions
    stateful inspection), so the rest of the article is ranked locally with the embedding model.
    """
    article = article.strip()
    if len(article) <= MAX_WEB_CHARS:
        return article
    passages = _passages(article)
    from rag_pipeline.embeddings import load_embedding_model  # loaded once per process
    model = load_embedding_model()
    vectors = model.encode([question] + passages, normalize_embeddings=True)
    ranked = sorted(range(len(passages)), key=lambda i: -float(vectors[0] @ vectors[i + 1]))
    chosen, used = {0}, len(passages[0])  # keep the intro for context
    for i in ranked:
        if i not in chosen and used + len(passages[i]) <= MAX_WEB_CHARS:
            chosen.add(i)
            used += len(passages[i])
    return "\n\n".join(passages[i] for i in sorted(chosen))[:MAX_WEB_CHARS]


def _article_text(title: str) -> str:
    """The whole article as plain text; one request with the article title only."""
    params = {"action": "query", "prop": "extracts", "explaintext": "1",
              "exsectionformat": "plain", "redirects": "1", "format": "json", "titles": title}
    pages = _fetch(Request(API + "?" + urlencode(params), headers=HEADERS))["query"]["pages"]
    if not isinstance(pages, dict) or len(pages) != 1:
        raise ValueError("Invalid encyclopedia pages")
    page = next(iter(pages.values()))
    text = page.get("extract")
    if "missing" in page or not isinstance(text, str) or not text.strip():
        raise ValueError("Missing public article")
    return text


def lookup_public_sources(question: str) -> list[dict]:
    """One Wikipedia article for the question.

    Only a curated article title or up to 6 keywords from the question are sent; retrieved
    course text never is. Known acronyms (DES, AES, ...) use the curated title, since a plain
    search finds the wrong article for them; anything else is a Wikipedia search, and a hit
    that doesn't match the question is discarded.
    """
    if not isinstance(question, str):
        raise WebLookupUnavailable("No public topic selected.")
    title = next((article for pattern, article in TOPICS
                  if re.search(pattern, question, flags=re.I)), None)
    params = {"action": "query", "prop": "extracts", "exintro": "1",
              "explaintext": "1", "redirects": "1", "format": "json"}
    if title is not None:
        params["titles"] = title
    else:
        terms = search_terms(question)
        if not terms:
            raise WebLookupUnavailable("No searchable keywords in this question.")
        params.update({"generator": "search", "gsrsearch": terms,
                       "gsrlimit": str(SEARCH_RESULTS), "gsrnamespace": "0", "exlimit": "max"})
    request = Request(API + "?" + urlencode(params), headers=HEADERS)
    try:
        result = _fetch(request)
        if title is None and "query" not in result:
            raise WebLookupUnavailable("No public article matched this question.")
        pages = result["query"]["pages"]
        if not isinstance(pages, dict) or not 1 <= len(pages) <= SEARCH_RESULTS:
            raise ValueError("Invalid encyclopedia pages")
        pages = [p for p in pages.values()
                 if isinstance(p, dict) and "missing" not in p
                 and isinstance(p.get("title"), str) and p["title"].strip()
                 and isinstance(p.get("extract"), str) and p["extract"].strip()]
        if not pages:
            raise ValueError("Missing public article")
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, KeyError, TypeError) as exc:
        raise WebLookupUnavailable("Internet citation lookup failed; retry in local-only mode.") from exc
    page = pages[0] if title is not None else _best_match(question, pages)
    if page is None:
        raise WebLookupUnavailable("No sufficiently relevant public article was found.")
    found = page["title"]
    try:
        article = _article_text(found)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, KeyError, TypeError):
        article = page["extract"]  # the intro we already have is still a usable source
    content = _relevant_text(question, article)
    return [{
        "id": "web:wikipedia:" + found.replace(" ", "_"),
        "source": "Wikipedia: " + found,
        "source_type": "web",
        "url": BASE + quote(found.replace(" ", "_"), safe="()"),
        "text": content,
        "page": 1, "chunk": 1, "similarity": 1.0,
    }]
