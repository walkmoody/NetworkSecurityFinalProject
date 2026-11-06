"""Optional network lookup is deliberately disabled pending a privacy review."""

class WebLookupUnavailable(RuntimeError):
    pass

def lookup_public_sources(query: str) -> list[dict]:
    raise WebLookupUnavailable(
        "External lookup is disabled: course documents remain on the local host."
    )
