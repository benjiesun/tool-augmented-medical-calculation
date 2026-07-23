def calc(relevant):
    def norm_key(k):
        s = str(k).strip().lower()
        out = []
        for ch in s:
            if ch.isalnum():
                out.append(ch)
        return ''.join(out)

    def unwrap_value(v):
        if isinstance(v, dict):
            for kk in ('value', 'val', 'number', 'amount'):
                if kk in v:
                    return unwrap_value(v[kk])
            for vv in v.values():
                return unwrap_value(vv)
            return None
        if isinstance(v, (list, tuple)):
            if len(v) == 0:
                return None
            return unwrap_value(v[0])
        return v

    def to_number(v):
        v = unwrap_value(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            num = []
            seen_digit = False
            seen_dot = False
            seen_sign = False
            for i, ch in enumerate(s):
                if ch in '+-' and not seen_digit and not seen_sign and i == 0:
                    num.append(ch)
                    seen_sign = True
                elif ch.isdigit():
                    num.append(ch)
                    seen_digit = True
                elif ch == '.' and not seen_dot:
                    num.append(ch)
                    seen_dot = True
                elif seen_digit:
                    break
            if num and any(c.isdigit() for c in num):
                try:
                    return float(''.join(num))
                except Exception:
                    return None
            return None

    def get_any(d, aliases):
        if not isinstance(d, dict):
            return None
        target = [norm_key(a) for a in aliases]
        for k, v in d.items():
            nk = norm_key(k)
            if nk in target:
                return to_number(v)
        return None

    na = get_any(relevant, ['sodium', 'na', 'na+', 'serumsodium'])
    cl = get_any(relevant, ['chloride', 'cl', 'cl-', 'serumchloride'])
    hco3 = get_any(relevant, ['bicarbonate', 'hco3', 'hco3-', 'bicarb', 'co2', 'tco2'])

    if na is None or cl is None or hco3 is None:
        return 'N/A'

    anion_gap = na - (cl + hco3)
    delta_gap = anion_gap - 12.0
    return float(delta_gap)
