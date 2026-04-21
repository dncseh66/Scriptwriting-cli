import re
from pathlib import Path


def count_words(text: str) -> int:
    return len(text.split())


def sanitize_folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name)
    cleaned = cleaned.strip().rstrip(".")
    return cleaned[:180] or "untitled"


def tail_words(text: str, n: int) -> str:
    words = text.split()
    if len(words) <= n:
        return text
    return " ".join(words[-n:])


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(content)


def section_type(section_id: str, is_last: bool, rules: dict) -> str:
    if is_last and "last" in rules:
        return rules["last"]
    if section_id in rules:
        return rules[section_id]
    return rules.get("default", "body")
