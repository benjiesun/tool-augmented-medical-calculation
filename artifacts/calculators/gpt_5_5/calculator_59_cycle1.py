def calc(relevant):
    def parse_text(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return 'true' if v else 'false'
        return str(v).strip()

    def parse_number(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, (list, tuple)):
            for item in v:
                n = parse_number(item)
                if n is not None:
                    return n
            return None
        if isinstance(v, dict):
            for k in ('value', 'val', 'amount', 'number', 'num', 'reading', 'result'):
                if k in v:
                    n = parse_number(v.get(k))
                    if n is not None:
                        return n
            for item in v.values():
                n = parse_number(item)
                if n is not None:
                    return n
            return None
        s = parse_text(v)
        if not s:
            return None
        s = s.replace(',', '')
        num = ''
        dot = False
        sign_allowed = True
        for ch in s:
            if ch in '+-' and sign_allowed and not num:
                num += ch
                sign_allowed = False
            elif ch.isdigit():
                num += ch
                sign_allowed = False
            elif ch == '.' and not dot:
                num += ch
                dot = True
                sign_allowed = False
            elif num:
                break
        try:
            return float(num) if num not in ('', '+', '-') else None
        except Exception:
            return None

    def norm(s):
        s = parse_text(s)
        if s is None:
            return ''
        out = ''
        for ch in s.lower():
            if ch.isalnum():
                out += ch
        return out

    def get_field(d, aliases):
        wanted = [norm(a) for a in aliases if norm(a)]
        def rec(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    nk = norm(k)
                    for a in wanted:
                        if nk == a or a in nk or nk in a:
                            return v
                for v in x.values():
                    r = rec(v)
                    if r is not None:
                        return r
            elif isinstance(x, (list, tuple)):
                for item in x:
                    r = rec(item)
                    if r is not None:
                        return r
            return None
        return rec(d)

    hr_v = get_field(relevant, ('Heart Rate or Pulse', 'Heart Rate', 'Pulse'))
    qt_v = get_field(relevant, ('QT Interval', 'QT'))
    hr = parse_number(hr_v)
    qt = parse_number(qt_v)
    if hr is None or qt is None:
        return 'N/A'
    qtc = qt * (120.0 + hr) / 180.0
    return round(qtc, 5)
