def calc(relevant):
    def norm_key(k):
        s = str(k).lower()
        return ''.join(ch for ch in s if ch.isalnum())

    def unwrap(v):
        if isinstance(v, dict):
            for k in ['value', 'date', 'text', 'number', 'val', 'answer']:
                if k in v:
                    return v[k]
            if len(v) == 1:
                for x in v.values():
                    return x
            return None
        if isinstance(v, (list, tuple)):
            if not v:
                return None
            return v[0]
        return v

    def get_value(names):
        if not isinstance(relevant, dict):
            return None
        items = []
        for k, v in relevant.items():
            items.append((norm_key(k), v))
        wants = [norm_key(x) for x in names]
        for w in wants:
            for nk, v in items:
                if nk == w:
                    return unwrap(v)
        for w in wants:
            for nk, v in items:
                if w and (w in nk or nk in w):
                    return unwrap(v)
        return None

    def read_text(v):
        v = unwrap(v)
        if v is None:
            return None
        return str(v).strip()

    def read_number(v):
        v = unwrap(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        out = ''
        seen_dot = False
        for i, ch in enumerate(s):
            if ch in '+-' and out == '':
                out += ch
            elif ch.isdigit():
                out += ch
            elif ch == '.' and not seen_dot:
                out += ch
                seen_dot = True
            elif out not in ['', '+', '-']:
                break
        try:
            return float(out)
        except Exception:
            return None

    def read_bool(v):
        v = unwrap(v)
        if isinstance(v, bool):
            return v
        if v is None:
            return None
        s = str(v).strip().lower()
        if s in ['true', 't', 'yes', 'y', '1']:
            return True
        if s in ['false', 'f', 'no', 'n', '0']:
            return False
        return None

    def is_leap(y):
        return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)

    def days_before_year(y):
        yy = y - 1
        return 365 * yy + yy // 4 - yy // 100 + yy // 400

    def days_before_month(y, m):
        md = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        total = 0
        for i in range(m - 1):
            total += md[i]
        if m > 2 and is_leap(y):
            total += 1
        return total

    def valid_date(y, m, d):
        if y < 1 or m < 1 or m > 12 or d < 1:
            return False
        md = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        lim = md[m - 1]
        if m == 2 and is_leap(y):
            lim = 29
        return d <= lim

    def to_ordinal(y, m, d):
        return days_before_year(y) + days_before_month(y, m) + d

    def parse_date(v):
        s = read_text(v)
        if not s:
            return None
        s = s.strip()
        parts = []
        cur = ''
        for ch in s:
            if ch.isdigit():
                cur += ch
            else:
                if cur != '':
                    parts.append(cur)
                    cur = ''
        if cur != '':
            parts.append(cur)
        if len(parts) < 3:
            return None
        a = int(parts[0]); b = int(parts[1]); c = int(parts[2])
        candidates = []
        if len(parts[0]) == 4:
            candidates.append((a, b, c))
        elif len(parts[2]) == 4:
            candidates.append((c, a, b))
            candidates.append((c, b, a))
        else:
            y = c
            if y < 100:
                y += 2000 if y < 50 else 1900
            candidates.append((y, a, b))
            candidates.append((y, b, a))
        for y, m, d in candidates:
            if valid_date(y, m, d):
                return (y, m, d)
        return None

    current = get_value(['Current Date', 'CurrentDate', 'date today', 'today', 'as of date', 'evaluation date'])
    lmp = get_value(['Last menstrual date', 'Last menstrual period', 'LMP', 'first day of last menstrual period', 'last period date'])
    cd = parse_date(current)
    ld = parse_date(lmp)
    if cd is None or ld is None:
        return 'N/A'
    diff = to_ordinal(cd[0], cd[1], cd[2]) - to_ordinal(ld[0], ld[1], ld[2])
    if diff < 0:
        return 'N/A'
    weeks = diff // 7
    days = diff % 7
    return (str(int(weeks)) + ' weeks', str(int(days)) + ' days')
