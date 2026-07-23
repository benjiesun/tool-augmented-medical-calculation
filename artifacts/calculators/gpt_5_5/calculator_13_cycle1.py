def _norm_key(k):
    s = str(k).lower()
    out = ''
    for ch in s:
        if ch.isalnum():
            out += ch
    return out


def _get_value(relevant, aliases):
    if not isinstance(relevant, dict):
        return None
    norm_map = {}
    for k, v in relevant.items():
        nk = _norm_key(k)
        if nk not in norm_map:
            norm_map[nk] = v
    for a in aliases:
        nk = _norm_key(a)
        if nk in norm_map:
            return norm_map[nk]
    return None


def _unwrap(value):
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def _parse_number(value):
    value = _unwrap(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        for k in ['value', 'number', 'amount', 'length', 'len']:
            if k in value:
                return _parse_number(value[k])
        return None
    s = str(value).strip()
    if not s:
        return None
    num = ''
    dot = False
    for i, ch in enumerate(s):
        if ch in '+-' and i == 0:
            num += ch
        elif ch.isdigit():
            num += ch
        elif ch == '.' and not dot:
            num += ch
            dot = True
        elif num:
            break
    try:
        if num in ('', '+', '-', '.', '+.', '-.'):
            return None
        return float(num) if '.' in num else int(num)
    except:
        return None


def _parse_date(value):
    value = _unwrap(value)
    if value is None:
        return None
    if isinstance(value, dict):
        y = value.get('year', value.get('yyyy'))
        m = value.get('month', value.get('mm'))
        d = value.get('day', value.get('dd'))
        if y is not None and m is not None and d is not None:
            try:
                return int(y), int(m), int(d)
            except:
                return None
        return None
    s = str(value).strip()
    if not s:
        return None
    sep = None
    for c in ['/', '-', '.']:
        if c in s:
            sep = c
            break
    parts = s.split(sep) if sep else s.split()
    if len(parts) != 3:
        return None
    try:
        a, b, c = [int(p) for p in parts]
    except:
        return None
    if len(parts[0]) == 4:
        return a, b, c
    return c, a, b


def _is_leap_year(y):
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


def _days_in_month(y, m):
    if m == 1 or m == 3 or m == 5 or m == 7 or m == 8 or m == 10 or m == 12:
        return 31
    if m == 4 or m == 6 or m == 9 or m == 11:
        return 30
    if m == 2:
        return 29 if _is_leap_year(y) else 28
    return None


def _add_days(y, m, d, delta):
    if delta == 0:
        return y, m, d
    step = 1 if delta > 0 else -1
    remaining = delta if delta > 0 else -delta
    for _ in range(5000):
        if remaining == 0:
            return y, m, d
        if step > 0:
            dim = _days_in_month(y, m)
            if dim is None:
                return None
            if d < dim:
                d += 1
            else:
                d = 1
                if m < 12:
                    m += 1
                else:
                    m = 1
                    y += 1
        else:
            if d > 1:
                d -= 1
            else:
                if m > 1:
                    m -= 1
                else:
                    m = 12
                    y -= 1
                dim = _days_in_month(y, m)
                if dim is None:
                    return None
                d = dim
        remaining -= 1
    return None


def _fmt_date(y, m, d):
    return str(m).zfill(2) + '/' + str(d).zfill(2) + '/' + str(y).zfill(4)


def calc(relevant):
    lmp_val = _get_value(relevant, ['Last menstrual date', 'Last menstrual period', 'LMP'])
    cycle_val = _get_value(relevant, ['cycle length', 'cycle length (days)', 'cycle'])
    if lmp_val is None or cycle_val is None:
        return 'N/A'
    lmp = _parse_date(lmp_val)
    cycle = _parse_number(cycle_val)
    if lmp is None or cycle is None:
        return 'N/A'
    try:
        cycle = int(round(float(cycle)))
    except:
        return 'N/A'
    if cycle <= 0:
        return 'N/A'
    delta = 280 + cycle - 28
    res = _add_days(lmp[0], lmp[1], lmp[2], delta)
    if res is None:
        return 'N/A'
    return _fmt_date(res[0], res[1], res[2])
