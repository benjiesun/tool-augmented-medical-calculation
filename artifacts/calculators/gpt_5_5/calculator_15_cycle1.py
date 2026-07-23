def calc(relevant):
    def norm_key(x):
        s = str(x).lower()
        out = []
        for ch in s:
            if ch.isalnum():
                out.append(ch)
        return ''.join(out)

    def unwrap(v):
        if isinstance(v, (list, tuple)):
            if len(v) == 0:
                return None
            return unwrap(v[0])
        if isinstance(v, dict):
            for k in ('value', 'val', 'amount', 'text', 'label', 'name'):
                if k in v:
                    return unwrap(v[k])
            for k in v:
                return unwrap(v[k])
            return None
        return v

    def get_num(v):
        v = unwrap(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            try:
                return float(s.replace(',', ''))
            except Exception:
                return None

    def get_text(v):
        v = unwrap(v)
        if v is None:
            return None
        return str(v).strip().lower()

    def find_key(d, aliases):
        if not isinstance(d, dict):
            return None
        lookup = {}
        for k, val in d.items():
            lookup[norm_key(k)] = val
        for alias in aliases:
            nk = norm_key(alias)
            if nk in lookup:
                return lookup[nk]
        for k, val in d.items():
            nk = norm_key(k)
            for alias in aliases:
                ak = norm_key(alias)
                if ak in nk or nk in ak:
                    return val
        return None

    bilirubin_v = find_key(relevant, ['bilirubin', 'total bilirubin'])
    albumin_v = find_key(relevant, ['albumin'])
    inr_v = find_key(relevant, ['international normalized ratio', 'inr'])
    ascites_v = find_key(relevant, ['ascites'])
    enceph_v = find_key(relevant, ['encephalopathy'])

    bilirubin = get_num(bilirubin_v)
    albumin = get_num(albumin_v)
    inr = get_num(inr_v)
    ascites = get_text(ascites_v)
    enceph = get_text(enceph_v)

    if bilirubin is None or albumin is None or inr is None or ascites is None or enceph is None:
        return 'N/A'

    score = 0

    if bilirubin < 2:
        score += 1
    elif bilirubin <= 3:
        score += 2
    else:
        score += 3

    if albumin > 3.5:
        score += 1
    elif albumin >= 2.8:
        score += 2
    else:
        score += 3

    if inr < 1.7:
        score += 1
    elif inr <= 2.3:
        score += 2
    else:
        score += 3

    a = ascites.replace('-', ' ').replace('_', ' ')
    if 'absent' in a or a in ('none', 'no ascites'):
        score += 1
    elif 'slight' in a or 'mild' in a:
        score += 2
    elif 'moderate' in a or 'tense' in a or 'severe' in a:
        score += 3
    else:
        return 'N/A'

    e = enceph.replace('-', ' ').replace('_', ' ')
    if 'no encephalopathy' in e or e in ('none', 'absent', 'normal'):
        score += 1
    elif 'grade 1' in e or 'grade 2' in e or '1 2' in e or '1-2' in e or 'mild' in e:
        score += 2
    elif 'grade 3' in e or 'grade 4' in e or '3 4' in e or '3-4' in e or 'severe' in e:
        score += 3
    else:
        return 'N/A'

    return int(score)
