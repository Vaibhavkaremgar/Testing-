"""Apply remaining ACC-4 fixes to _normalize_name_candidate."""

with open('ats/extraction/resume_parser.py', 'rb') as f:
    rp = f.read()

# FIX C: 2<=len<=4 -> 2<=len<=5
old_c = b'    if not (2 <= len(words) <= 4):\n        return ""\n'
new_c = b'    if not (2 <= len(words) <= 5):\n        return ""\n'
if old_c in rp:
    rp = rp.replace(old_c, new_c, 1)
    print('ACC-4C 5-word names: OK')
elif b'if not (2 <= len(words) <= 5):' in rp:
    print('ACC-4C 5-word names: already applied')
else:
    print('ACC-4C 5-word names: PATTERN NOT FOUND')
    idx = rp.find(b'2 <= len(words)')
    print(repr(rp[idx:idx+60]))

# FIX D: allow hyphens
old_d = b'    if not all(word.replace(".", "").replace("\'", "").isalpha() for word in words):\n        return ""\n'
new_d = b'    if not all(word.replace(".", "").replace("\'", "").replace("-", "").isalpha() for word in words):\n        return ""\n'
if old_d in rp:
    rp = rp.replace(old_d, new_d, 1)
    print('ACC-4D hyphen names: OK')
elif b'.replace("-", "").isalpha()' in rp:
    print('ACC-4D hyphen names: already applied')
else:
    print('ACC-4D hyphen names: PATTERN NOT FOUND')
    idx = rp.find(b'isalpha() for word in words')
    print(repr(rp[max(0,idx-80):idx+60]))

# FIX A+B: honorific strip + ALL CAPS before final return
old_ret = b'    return " ".join(word if len(word) == 1 else word.title() for word in words)\n'
new_ret = (
    b'    candidate = NAME_HONORIFIC_PATTERN.sub("", candidate).strip()\n'
    b'    candidate = NAME_CREDENTIAL_SUFFIX.sub("", candidate).strip()\n'
    b'    if not candidate:\n'
    b'        return ""\n'
    b'    words = candidate.split()\n'
    b'    if not (2 <= len(words) <= 5):\n'
    b'        return ""\n'
    b'    if candidate.isupper() and 2 <= len(words) <= 5:\n'
    b'        candidate = candidate.title()\n'
    b'        words = candidate.split()\n'
    b'    return " ".join(word if len(word) == 1 else word.title() for word in words)\n'
)
if old_ret in rp and b'NAME_HONORIFIC_PATTERN.sub' not in rp:
    rp = rp.replace(old_ret, new_ret, 1)
    print('ACC-4AB honorific+caps: OK')
elif b'NAME_HONORIFIC_PATTERN.sub' in rp:
    print('ACC-4AB honorific+caps: already applied')
else:
    print('ACC-4AB honorific+caps: PATTERN NOT FOUND')
    idx = rp.find(b'word.title() for word in words')
    print(repr(rp[max(0,idx-40):idx+60]))

with open('ats/extraction/resume_parser.py', 'wb') as f:
    f.write(rp)
