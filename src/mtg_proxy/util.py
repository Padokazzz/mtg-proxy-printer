import re


def slugify(text: str) -> str:
    """Converte um nome em um slug seguro para nomes de arquivo."""
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", text.lower()).strip("-")
    return slug or "card"
