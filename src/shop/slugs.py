"""URL slugs for product names."""

import re
import unicodedata

POLISH_LETTERS = {
    "ą": "a",
    "ć": "c",
    "ę": "e",
    "ł": "l",
    "ń": "n",
    "ó": "o",
    "ś": "s",
    "ź": "z",
    "ż": "z",
}


def slugify(text: str) -> str:
    """Return `text` as a URL slug: lower case ASCII words joined by one hyphen."""
    replaced = "".join(POLISH_LETTERS.get(char, char) for char in text.lower())
    ascii_only = unicodedata.normalize("NFKD", replaced).encode("ascii", "ignore").decode("ascii")
    words = [word for word in re.split("[^a-z0-9]+", ascii_only) if word]
    return "-".join(words)
