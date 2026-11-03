"""Text extraction and chunking, keeping page / section references."""
import csv
from pathlib import Path

import pymupdf

MAX_CHUNK_CHARS = 1000
CSV_ROWS_PER_CHUNK = 12  # one fiscal year of monthly rows per chunk

Pieces = list[tuple[int | None, str]]


def chunk_lines(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks on line boundaries (keeps table rows intact)."""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines():
        if current and size + len(line) + 1 > max_chars:
            chunks.append("\n".join(current).strip())
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current).strip())
    return [c for c in chunks if c]


def extract_pdf(path: Path) -> tuple[int | None, Pieces]:
    pieces: Pieces = []
    doc = pymupdf.open(str(path))
    try:
        page_count = len(doc)
        for page_number, page in enumerate(doc, start=1):
            for chunk in chunk_lines(page.get_text("text")):
                pieces.append((page_number, chunk))
    finally:
        doc.close()
    return page_count, pieces


def extract_csv(path: Path) -> tuple[int | None, Pieces]:
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.reader(f))
    if not rows:
        return None, []
    header, body = rows[0], rows[1:]
    pieces: Pieces = []
    for start in range(0, len(body), CSV_ROWS_PER_CHUNK):
        block = body[start:start + CSV_ROWS_PER_CHUNK]
        lines = [f"# data rows {start + 1}-{start + len(block)}", ",".join(header)]
        lines += [",".join(r) for r in block]
        pieces.append((None, "\n".join(lines)))
    return None, pieces


def extract_text_file(path: Path) -> tuple[int | None, Pieces]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return None, [(None, c) for c in chunk_lines(text)]


def extract(path: Path) -> tuple[int | None, Pieces]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".csv":
        return extract_csv(path)
    if suffix == ".txt":
        return extract_text_file(path)
    raise ValueError(f"Unsupported file type: {suffix}")