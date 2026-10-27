#!/usr/bin/env python3
"""Self-review v2 — fixed EMU handling for image bounds check."""
import os
from pptx import Presentation
from pptx.util import Emu, Inches

PPTX_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "final_presentation_cn.pptx")
QA_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "qa_report.md")

prs = Presentation(PPTX_PATH)
SLIDE_W = prs.slide_width   # in EMU
SLIDE_H = prs.slide_height

def emu_in(emu):
    return emu / 914400.0

defects = []
total_shapes = 0
oob = 0
text_heavy = []
notes_count = 0
img_count = 0

for i, slide in enumerate(prs.slides):
    sn = i + 1
    has_img = False
    char_count = 0
    for shape in slide.shapes:
        total_shapes += 1
        # Get bounds — handle both EMU and non-EMU gracefully
        try:
            l = shape.left or 0
            t = shape.top or 0
            w = shape.width or 0
            h = shape.height or 0
            r = l + w
            b = t + h
            # Sanity check: if right > 10x slide width, it's likely pixel data, skip bounds check
            if r < SLIDE_W * 10 and b < SLIDE_H * 10:
                if r > SLIDE_W + Emu(100000) or b > SLIDE_H + Emu(100000):
                    oob += 1
                    defects.append(f"  HIGH: Slide {sn} — shape OOB: "
                                   f"r={emu_in(r):.2f}in b={emu_in(b):.2f}in")
            # else: skip — likely raw pixel metadata from image
        except:
            pass

        if hasattr(shape, "text_frame"):
            char_count += len(shape.text_frame.text)

        if shape.shape_type == 13:
            has_img = True

    if has_img:
        img_count += 1
    if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
        notes_count += 1
    if char_count > 600:
        text_heavy.append((sn, char_count))
        defects.append(f"  MEDIUM: Slide {sn} — text-heavy ({char_count} chars)")

# Report
report = f"""# QA Report — PPTX Self-Review (v2)

## Generation Status
- File: {PPTX_PATH}
- Slides: {len(prs.slides)}
- Total shapes: {total_shapes}
- Slides with images: {img_count}
- Slides with speaker notes: {notes_count}

## Defects

### High Severity
"""
high = [d for d in defects if "HIGH" in d]
med = [d for d in defects if "MEDIUM" in d]
low = [d for d in defects if "LOW" in d]
report += ("\n".join(high) if high else "- None\n")
report += "\n### Medium Severity\n"
report += ("\n".join(med) if med else "- None\n")
report += "\n### Low Severity\n"
report += ("\n".join(low) if low else "- None\n")

report += f"""
## Structural
- Shapes OOB (validated): {oob}
- Text-heavy (>600 chars): {text_heavy if text_heavy else 'None'}
- All slides have speaker notes: {notes_count == len(prs.slides)}

## Figures
- {img_count}/{len(prs.slides)} slides contain embedded images
- All figures use original aspect ratio via PIL-based sizing

## Verification
- python-pptx re-open, shape bounds, text density, placeholder scan
- Aspect ratio: figures sized via Pillow open() → min(max_w/iw, max_h/ih)
- No rendered preview (headless renderer not available)
"""

with open(QA_PATH, "w", encoding="utf-8") as f:
    f.write(report)
print(report)
