# QA Report — PPTX Self-Review (v2)

## Generation Status
- File: E:\artificialIntelligence\course-of-Introduction-to-AI\paper\scripts\..\output\final_presentation_cn.pptx
- Slides: 12
- Total shapes: 112
- Slides with images: 7
- Slides with speaker notes: 12

## Defects

### High Severity
- None

### Medium Severity
- None

### Low Severity
- None

## Structural
- Shapes OOB (validated): 0
- Text-heavy (>600 chars): None
- All slides have speaker notes: True

## Figures
- 7/12 slides contain embedded images
- All figures use original aspect ratio via PIL-based sizing

## Verification
- python-pptx re-open, shape bounds, text density, placeholder scan
- Aspect ratio: figures sized via Pillow open() → min(max_w/iw, max_h/ih)
- No rendered preview (headless renderer not available)
