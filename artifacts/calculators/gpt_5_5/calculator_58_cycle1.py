def calc(relevant):
    def is_num(x):
        try:
            if x is None or isinstance(x, bool):
                return False
            float(str(x).replace(',', '').strip())
            return True
        except Exception:
            return False

    def first_number(x):
        if x is None:
            return None
        if is_num(x):
            return float(str(x).replace(',', '').strip())
        s = str(x).replace(',', '')
        token = ''
        started = False
        for ch in s:
            if ch.isdigit() or ch in '+-.':
                token += ch
                started = True
            elif started:
                break
        try:
            if token in ('', '+', '-', '.', '+.', '-.'):
                return None
            return float(token)
        except Exception:
            return None

    def val_text(v):
        if v is None:
            return ''
        if isinstance(v, dict):
            parts = []
            for k in ('unit', 'units', 'text', 'label', 'name'):
                if k in v and v.get(k) is not None:
                    parts.append(str(v.get(k)))
            return ' '.join(parts).lower()
        if isinstance(v, (list, tuple)):
            return ' '.join(str(x) for x in v[1:] if x is not None).lower()
        return str(v).lower() if not is_num(v) else ''

    def val_num(v):
        if v is None:
            return None
        if isinstance(v, dict):
            for k in ('value', 'val', 'number', 'num', 'amount'):
                if k in v:
                    n = first_number(v.get(k))
                    if n is not None:
                        return n
            for x in v.values():
                n = first_number(x)
                if n is not None:
                    return n
            return None
        if isinstance(v, (list, tuple)):
            for x in v:
                n = first_number(x)
                if n is not None:
                    return n
            return None
        return first_number(v)

    def norm(s):
        return ''.join(ch for ch in str(s).lower() if ch.isalnum())

    def get_key(data, aliases):
        if not isinstance(data, dict):
            return None
        items = [(norm(k), k) for k in data.keys()]
        for a in aliases:
            na = norm(a)
            for nk, ok in items:
                if nk == na:
                    return data[ok]
        for a in aliases:
            na = norm(a)
            for nk, ok in items:
                if na and (na in nk or nk in na):
                    return data[ok]
        return None

    if not isinstance(relevant, dict):
        return 'N/A'

    hr_v = get_key(relevant, ['Heart Rate or Pulse', 'Heart Rate', 'Pulse', 'HR', 'Rate'])
    qt_v = get_key(relevant, ['QT Interval', 'QT', 'QT duration'])
    paper_v = get_key(relevant, ['Paper speed', 'Paper speed mm sec', 'Paper Speed mm/sec'])

    hr = val_num(hr_v)
    qt = val_num(qt_v)
    if hr is None or qt is None:
        return 'N/A'

    qt_unit = val_text(qt_v)
    paper = val_num(paper_v)
    if paper is None:
        paper = 25.0

    if 'box' in qt_unit or 'square' in qt_unit:
        if abs(paper - 50.0) < 0.001:
            qt = qt * 20.0
        else:
            qt = qt * 40.0
    elif 'sec' in qt_unit and 'msec' not in qt_unit and 'ms' not in qt_unit and qt < 10:
        qt = qt * 1000.0

    if hr <= 0 or qt <= 0:
        return 'N/A'

    qtc = qt + 1.75 * (hr - 60.0)
    return qtc
