import fitz
import json
import re
from collections import Counter
import debug
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

def get_row_blocks(page, y_tolerance=3, gap_threshold=15):
    words = page.get_text("words")
    rows = {}

    for word in words:
        x0   = word[0]
        y0   = word[1]
        text = word[4]
        y_key = round(y0 / y_tolerance) * y_tolerance

        if y_key not in rows:
            rows[y_key] = []
        rows[y_key].append((x0, text))

    sorted_y_keys = sorted(rows.keys())

    blocks = []
    current_block = []

    for idx, y_key in enumerate(sorted_y_keys):
        current_block.append((y_key, rows[y_key]))

        if idx < len(sorted_y_keys) - 1:
            next_y = sorted_y_keys[idx + 1]
            gap = next_y - y_key

            if gap > gap_threshold:
                blocks.append(current_block)
                current_block = []

    if current_block:
        blocks.append(current_block)

    return blocks

# --- Function to decide if a block of rows looks like a table ---
def is_table_block(block, x_tolerance=50, min_rows=3, min_cols=2):
    # block is a list of (y_key, [(x0, text), (x0, text), ...])

    if len(block) < min_rows:
        return False

    # Collect every X position from every row in this block
    all_x = []
    for (y_key, word_list) in block:
        for (x0, text) in word_list:
            all_x.append(x0)

    # Sort and cluster nearby X values into "columns"
    # If X=48, X=50, X=51 all appear, they form one column at roughly X=50
    all_x.sort()

    columns = []
    current_cluster = [all_x[0]]

    for x in all_x[1:]:
        if x - current_cluster[-1] <= x_tolerance:
            # Close enough — same column
            current_cluster.append(x)
        else:
            # Gap too big — new column starts
            columns.append(current_cluster)
            current_cluster = [x]
    columns.append(current_cluster)

    # A real column appears in MANY rows, not just once or twice
    strong_columns = [c for c in columns if len(c) >= min_rows]

    return len(strong_columns) >= min_cols


# --- Main function: separate tables from prose ---
def get_tables_and_prose(page):
    blocks = get_row_blocks(page)

    tables = []
    prose_blocks = []

    for block in blocks:
        # Convert block rows into clean word lists for output
        rows_as_text = []
        for (y_key, word_list) in block:
            sorted_words = sorted(word_list, key=lambda w: w[0])
            rows_as_text.append([w[1] for w in sorted_words])

        if is_table_block(block):
            tables.append(rows_as_text)
        else:
            prose_blocks.append(rows_as_text)

    return tables, prose_blocks


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

    if total_pages < 3:
        return set()
    
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

# --- Function to check if a span of text is likely a watermark ---
def is_watermark_span(span):
    color = span.get("color", 0)  # default 0 = black

    # Unpack the single color integer into R, G, B channels
    r = (color >> 16) & 0xFF
    g = (color >> 8)  & 0xFF
    b =  color        & 0xFF

    # Average brightness: 0 = black, 255 = white
    brightness = (r + g + b) / 3

    # If very light (almost white), treat as watermark
    return brightness > 200

# --- Get page text with watermark spans removed ---
def get_text_without_watermarks(page):
    data = page.get_text("dict")
    clean_lines = []

    for block in data["blocks"]:
        if block["type"] != 0:  # 0 = text block
            continue
        for line in block["lines"]:
            line_text = ""
            for span in line["spans"]:
                if not is_watermark_span(span):
                    line_text += span["text"]
            if line_text.strip():
                clean_lines.append(line_text)

    return "\n".join(clean_lines)

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

    #debug.debug_watermark_spans(page, i+1)

    text = get_text_without_watermarks(page)     
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

    tables, prose_block = get_tables_and_prose(page)

    page_data = {
        "page_number": i + 1,
        "text":        cleaned_text,
        "headings":    get_headings(page),   # NEW
        "has_images":  has_images(page),      # NEW
        "tables": tables,
        "prose_blocks": prose_block
    }

    result["pages"].append(page_data)

doc.close()

with open("output.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("Done! Check output.json")