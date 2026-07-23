def calc(relevant):
    def _norm(x):
        return ''.join(ch for ch in str(x).lower() if ch.isalnum())

    def _as_int(v):
        if isinstance(v, bool):
            return None
        try:
            s = str(v).strip()
            if s == '':
                return None
            f = float(s)
            if f.is_integer():
                return int(f)
        except:
            return None
        return None

    def _is_leap(y):
        return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)

    def _dim(y, m):
        if m in (1, 3, 5, 7, 8, 10, 12):
            return 31
        if m in (4, 6, 9, 11):
            return 30
        if m == 2:
            return 29 if _is_leap(y) else 28
        return 0

    def _valid_date(y, m, d):
        return isinstance(y, int) and isinstance(m, int) and isinstance(d, int) and y > 0 and 1 <= m <= 12 and 1 <= d <= _dim(y, m)

    def _fmt_date(y, m, d):
        return '%02d/%02d/%04d' % (m, d, y)

    def _unwrap(v, depth=0):
        if depth > 4:
            return v
        if isinstance(v, (list, tuple)):
            if not v:
                return None
            return _unwrap(v[0], depth + 1)
        if isinstance(v, dict):
            nmap = {}
            for k, val in v.items():
                nmap[_norm(k)] = val
            for k in ('value', 'date', 'text', 'answer', 'result'):
                nk = _norm(k)
                if nk in nmap:
                    return _unwrap(nmap[nk], depth + 1)
            if len(v) == 1:
                return _unwrap(next(iter(v.values())), depth + 1)
        return v

    def _parse_date(v):
        v = _unwrap(v)
        if v is None:
            return None
        if isinstance(v, dict):
            nmap = {}
            for k, val in v.items():
                nmap[_norm(k)] = val
            y = _as_int(nmap.get('year'))
            m = _as_int(nmap.get('month'))
            d = _as_int(nmap.get('day'))
            if _valid_date(y, m, d):
                return (y, m, d)
        s = str(v).strip()
        if not s:
            return None
        if 'T' in s:
            s = s.split('T', 1)[0].strip()
        if ' ' in s:
            s = s.split(' ', 1)[0].strip()
        s = s.replace(',', '')
        delim = None
        for c in ('/', '-', '.'):
            if c in s:
                delim = c
                break
        if delim is not None:
            parts = [p for p in s.split(delim) if p != '']
            if len(parts) >= 3:
                a = _as_int(parts[0])
                b = _as_int(parts[1])
                c = _as_int(parts[2])
                if a is None or b is None or c is None:
                    return None
                if len(parts[0]) == 4 or a > 31:
                    y, m, d = a, b, c
                else:
                    m, d, y = a, b, c
                if y is not None and 0 <= y < 100:
                    y = 2000 + y if y < 50 else 1900 + y
                if _valid_date(y, m, d):
                    return (y, m, d)
        if s.isdigit() and len(s) == 8:
            y = _as_int(s[:4])
            m = _as_int(s[4:6])
            d = _as_int(s[6:8])
            if _valid_date(y, m, d):
                return (y, m, d)
        return None

    def _add_days(y, m, d, n):
        for _ in range(n):
            d += 1
            if d > _dim(y, m):
                d = 1
                m += 1
                if m > 12:
                    m = 1
                    y += 1
        return y, m, d

    def _find_key(d, aliases):
        if not isinstance(d, dict):
            return None
        nmap = {}
        for k, val in d.items():
            nmap[_norm(k)] = val
        for alias in aliases:
            nk = _norm(alias)
            if nk in nmap:
                return nmap[nk]
        for k, val in d.items():
            nk = _norm(k)
            for alias in aliases:
                na = _norm(alias)
                if nk == na or nk.find(na) != -1 or na.find(nk) != -1:
                    return val
        return None

    lmp = _find_key(relevant, ['Last menstrual date', 'Last menstrual period', 'LMP', 'LMP date', 'Date of last menstrual period'])
    dt = _parse_date(lmp)
    if dt is None:
        return 'N/A'
    y, m, d = dt
    y, m, d = _add_days(y, m, d, 14)
    return _fmt_date(y, m, d)
