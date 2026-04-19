---
name: factory-cover
description: "Regenerate the ebook cover for the current/latest book"
---

# Factory Cover

Regenerate the cover image for the most recent or specified book.

## Steps

1. Find the latest workbook directory:
   ```bash
   ls -td ~/.hermes/ebook-factory/workbooks/book-* | head -1
   ```

2. Run the cover generator:
   ```bash
   python3 ~/.hermes/ebook-factory/skills/cover-generator/cover_generator.py --book-dir <WORKBOOK_DIR>
   ```

   With niche override:
   ```bash
   python3 ~/.hermes/ebook-factory/skills/cover-generator/cover_generator.py --book-dir <WORKBOOK_DIR> --niche health
   ```

3. After generation, the cover will be at `<WORKBOOK_DIR>/output/cover.jpg`

4. Send a thumbnail notification to Telegram if possible.

## Notes

- Cover generation uses Ideogram API (~$0.09/cover)
- The cover is automatically included in the packager output
- If re-running after packaging, you must re-run the packager to embed the new cover in EPUB/PDF
