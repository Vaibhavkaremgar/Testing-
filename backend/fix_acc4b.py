"""Apply ACC-4 fixes with CRLF line endings."""

with open('ats/extraction/resume_parser.py', 'rb') as f:
    rp = f.read()

# FIX C: 2<=len<=4 -> 2<=len<=5  (CRLF)
old_c = b'    if not (2 <= len(words) <= 4):\r\n        return ""\r\n'
new_c = b'    if not (2 <= len(words) <= 5):\r\n        return ""\r\n'
if old_c in rp:
    rp = rp.replace(old_c, new_c, 1)
    print('ACC-4C: OK')
elif b'if not (2 <= len(words) <= 5):' in rp:
    print('ACC-4C: already applied')
else:
    print('ACC-4C: STILL NOT FOUND')

# FIX D: allow hyphens (CRLF)
old_d = b'    if not all(word.replace(".", "").replace("\'", "").isalpha() for word in words):\r\n        return ""\r\n'
new_d = b'    if not all(word.replace(".", "").replace("\'", "").replace("-", "").isalpha() for word in words):\r\n        return ""\r\n'
if old_d in rp:
    rp = rp.replace(old_d, new_d, 1)
    print('ACC-4D: OK')
elif b'.replace("-", "").isalpha()' in rp:
    print('ACC-4D: already applied')
else:
    print('ACC-4D: STILL NOT FOUND')

# FIX A+B: honorific strip + ALL CAPS before final return (CRLF)
old_ret = b'    return " ".join(word if len(word) == 1 else word.title() for word in words)\r\n'
new_ret = (
    b'    candidate = NAME_HONORIFIC_PATTERN.sub("", candidate).strip()\r\n'
    b'    candidate = NAME_CREDENTIAL_SUFFIX.sub("", candidate).strip()\r\n'
    b'    if not candidate:\r\n'
    b'        return ""\r\n'
    b'    words = candidate.split()\r\n'
    b'    if not (2 <= len(words) <= 5):\r\n'
    b'        return ""\r\n'
    b'    if candidate.isupper() and 2 <= len(words) <= 5:\r\n'
    b'        candidate = candidate.title()\r\n'
    b'        words = candidate.split()\r\n'
    b'    return " ".join(word if len(word) == 1 else word.title() for word in words)\r\n'
)
if old_ret in rp and b'NAME_HONORIFIC_PATTERN.sub' not in rp:
    rp = rp.replace(old_ret, new_ret, 1)
    print('ACC-4AB: OK')
elif b'NAME_HONORIFIC_PATTERN.sub' in rp:
    print('ACC-4AB: already applied')
else:
    print('ACC-4AB: STILL NOT FOUND')

with open('ats/extraction/resume_parser.py', 'wb') as f:
    f.write(rp)
