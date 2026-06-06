import fitz
import json
import re
from collections import Counter

# --- Function to detect headings ---
def get_headings(page):
    headings = []
    data = page.get_text("dict")

    for block in data["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                size = span["size"]
                flags = span["flags"]
                is_bold = bool(flags & 16)

                if not text:
                    continue

                if size >= 11 and is_bold:
                    headings.append({
                        "text": text,
                        "font_size": round(size, 1)
                    })

    return headings


# --- Function to check for images ---
def has_images(page):
    data = page.get_text("dict")
    for block in data["blocks"]:
        if block["type"] == 1:
            return True
    return False

def get_tables(page):
    words = page.get_text("words")
    rows = {}

    for word in words:
        x0   = word[0]
        y0   = word[1]
        text = word[4]

        y_key = round(y0 / 3) * 3

        if y_key not in rows:
            rows[y_key] = []

        rows[y_key].append((x0, text))

    result = []
    for y_key in sorted(rows.keys()):
        row_words = sorted(rows[y_key], key=lambda w: w[0])
        row_text  = [w[1] for w in row_words]
        result.append(row_text)

    return result

# --- Function to detect page number lines ---
def is_page_number(text):
    text = text.strip()

    # re.fullmatch means the ENTIRE string must match the pattern, not just part of it
    # Pattern 1: just a number, optionally wrapped in dashes like "- 3 -"
    # Pattern 2: "Page 3" or "Page 3 of 10"
    pattern = r'[--]?\s*\d+\s*[--]?|[Pp]age\s+\d+(\s+of\s+\d+)?'

    return bool(re.fullmatch(pattern, text))

# --- Function to find lines that repeat across most pages (headers/footers) ---
def find_repeated_lines(all_pages_lines, repeat_threshold=0.6):
    # all_pages_lines is a list of lists.
    # Each inner list is all the text lines for one page.
    # Example: [["Chapter 1", "Lexical Analysis", "3"], ["Chapter 1", "Tokens", "4"], ...]

    total_pages = len(all_pages_lines)
    line_counts = Counter()

    for page_lines in all_pages_lines:
        # Convert to a set so each line is counted only ONCE per page
        # even if it appears twice on the same page
        unique_lines = set(page_lines)

        for line in unique_lines:
            line = line.strip()
            if line:  # ignore empty lines
                line_counts[line] += 1

    # Keep only lines that appeared on more than 60% of all pages
    repeated = set()
    for line, count in line_counts.items():
        if count / total_pages >= repeat_threshold:
            repeated.add(line)

    return repeated

# --- Main script ---
doc = fitz.open("COMPILER DESIGN.pdf")

meta = doc.metadata
result = {
    "metadata": {
        "title":      meta.get("title", "Unknown"),
        "author":     meta.get("author", "Unknown"),
        "page_count": len(doc),
        "creator":    meta.get("creator", "Unknown"),
    },
    "pages": []
}

all_page_lines = []
for page in doc:
    text = page.get_text("text")
    lines = text.split("\n")
    all_page_lines.append(lines)

repeated_lines = find_repeated_lines(all_page_lines)
print("Repeated lines found: ",repeated_lines)

for i, page in enumerate(doc):
    text = page.get_text("text")       
    lines = text.split("\n")

    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if is_page_number(stripped):
            pass
        elif stripped in repeated_lines:
            pass
        else:
            cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines).strip()

    page_data = {
        "page_number": i + 1,
        "text":        cleaned_text,
        "headings":    get_headings(page),   # NEW
        "has_images":  has_images(page),      # NEW
        "table_rows": get_tables(page)
    }

    result["pages"].append(page_data)

doc.close()

with open("output.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("Done! Check output.json")