import random
import re
import string
import unicodedata


def rm_space(value: str) -> str:
    return " ".join(value.split())


def q_to_rand(value: str) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) if c == "?" else c for c in value)


def uni2ascii_approx(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def tag_to_filename(tag: str) -> str:
    ascii_tag = uni2ascii_approx(tag)
    safe = q_to_rand(ascii_tag.replace(" ", "_"))
    safe = re.sub(r"[^\w.\-+]", "_", safe)
    return f"{safe}.pdf"
