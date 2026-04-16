#!/usr/bin/env python3
import re
from pathlib import Path

body = Path('/home/bookforge/books/factory/LEARNING.md').read_text()

# Split by ## to get first entry body
parts = body.split('## [2026-04-06]')
if len(parts) > 0:
    first_entry = parts[0]
else:
    first_entry = body

print("Body length:", len(first_entry))
print("Body preview:", repr(first_entry[:300]))
print()

# Test patterns
patterns = [
    (r'- \*\*Royalty\*\*:\s*\$(\d+\.?\d*)', 'royalty'),
    (r'- \*\*Units Sold\*\*:\s*(\d+)', 'units'),
    (r'- \*\*KENP Pages\*\*:\s*(\d+)', 'kenp'),
    (r'- \*\*Royalty/unit\*\*:\s*\$(\d+\.?\d*)', 'royalty_per_unit'),
    (r'- \*\*KENP/unit\*\*:\s*(\d+\.?\d*)', 'kenp_per_unit'),
    (r'- \*\*Niche Category\*\*:\s*(\S+)', 'niche'),
    (r'- \*\*Niche Score\*\*:\s*(\d+\.?\d*)/10', 'niche_score'),
]

for pattern, name in patterns:
    match = re.search(pattern, first_entry)
    if match:
        print(f'{name}: {match.group(1)}')
    else:
        print(f'{name}: NOT FOUND')
