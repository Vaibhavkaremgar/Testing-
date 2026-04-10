path = r'd:\ai-recruitment-dashboard\backend\ats\extraction\resume_parser.py'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines to remove (0-indexed): 1666-1669 and 1691-1694
# Line 1666: if result["field_confidence"]["name"] < CONFIDENCE_RETRY_THRESHOLD:
# Line 1667:     result["name"] = None
# Line 1668:     result["personal_details"]["name"] = None
# Line 1669:     result["field_confidence"]["name"] = 0.0
# Line 1691: if result["field_confidence"]["name"] < CONFIDENCE_RETRY_THRESHOLD:
# Line 1692:     result["name"] = None
# Line 1693:     result["personal_details"]["name"] = None
# Line 1694:     result["field_confidence"]["name"] = 0.0

# Verify the lines match what we expect before removing
checks = [
    (1665, 'CONFIDENCE_RETRY_THRESHOLD'),  # 0-indexed line 1665 = line number 1666
    (1666, 'result["name"] = None'),
    (1667, 'personal_details'),
    (1668, 'field_confidence.*0.0'),
    (1690, 'CONFIDENCE_RETRY_THRESHOLD'),
    (1691, 'result["name"] = None'),
    (1692, 'personal_details'),
    (1693, 'field_confidence.*0.0'),
]

import re
all_ok = True
for idx, pattern in checks:
    if not re.search(pattern, lines[idx]):
        print(f'MISMATCH at line {idx+1}: {repr(lines[idx].strip())} (expected {pattern})')
        all_ok = False

if not all_ok:
    print('Aborting - line mismatch')
    exit(1)

# Remove lines in reverse order to preserve indices
for idx in sorted([1665, 1666, 1667, 1668, 1690, 1691, 1692, 1693], reverse=True):
    del lines[idx]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed: removed both name-wiping confidence blocks')
print('Verifying syntax...')
import subprocess
result = subprocess.run(['python', '-m', 'py_compile', path], capture_output=True, text=True)
if result.returncode == 0:
    print('Syntax OK')
else:
    print('Syntax ERROR:', result.stderr)
