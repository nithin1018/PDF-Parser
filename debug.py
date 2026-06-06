# --- Debug: print all spans with their colour and brightness ---
def debug_watermark_spans(page, page_number):
    data = page.get_text("dict")

    print(f"\n── Page {page_number} spans ──")

    for block in data["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue

                color = span.get("color", 0)

                r = (color >> 16) & 0xFF
                g = (color >> 8)  & 0xFF
                b =  color        & 0xFF
                brightness = (r + g + b) / 3

                # Flag it clearly if it would be removed
                flag = " ← WATERMARK" if brightness > 200 else ""

                print(f"  brightness={brightness:6.1f}  color=({r},{g},{b})  text='{text}'{flag}")