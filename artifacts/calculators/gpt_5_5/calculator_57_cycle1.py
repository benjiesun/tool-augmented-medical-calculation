def calc(relevant):
    def unwrap(x):
        if isinstance(x, dict):
            for k in ['value', 'Value', 'val', 'number', 'amount']:
                if k in x:
                    unit = None
                    for uk in ['unit', 'units', 'Unit', 'Units']:
                        if uk in x:
                            unit = x[uk]
                            break
                    return x[k], unit
            return None, None
        if isinstance(x, (list, tuple)):
            if len(x) == 0:
                return None, None
            val = x[0]
            unit = x[1] if len(x) > 1 else None
            return val, unit
        return x, None

    def to_num(x):
        v, u = unwrap(x)
        if v is None:
            return None
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s == '':
            return None
        out = ''
        started = False
        dot = False
        sign = False
        for ch in s:
            if ch.isdigit():
                out += ch
                started = True
            elif ch == '.' and not dot:
                out += ch
                dot = True
                started = True
            elif ch in '+-' and not started and not sign:
                out += ch
                sign = True
            elif started:
                break
        try:
            return float(out)
        except Exception:
            return None

    def unit_text(x):
        v, u = unwrap(x)
        txt = ''
        if u is not None:
            txt += str(u).lower()
        if not isinstance(v, (int, float)) and v is not None:
            sv = str(v).lower()
            if any(c.isalpha() for c in sv):
                txt += ' ' + sv
        return txt.strip()

    def find_value(names):
        if not isinstance(relevant, dict):
            return None
        low = {}
        for k in relevant:
            low[str(k).lower()] = k
        for name in names:
            n = name.lower()
            if n in low:
                return relevant[low[n]]
        for k in relevant:
            kl = str(k).lower()
            for name in names:
                if name.lower() in kl:
                    return relevant[k]
        return None

    hr_raw = find_value(['Heart Rate or Pulse', 'Heart Rate', 'Pulse', 'HR'])
    qt_raw = find_value(['QT Interval', 'QT'])
    hr = to_num(hr_raw)
    qt = to_num(qt_raw)
    if hr is None or qt is None or hr <= 0 or qt < 0:
        return 'N/A'

    qt_unit = unit_text(qt_raw)
    if 'sec' in qt_unit and 'msec' not in qt_unit and 'ms' not in qt_unit and 'millisec' not in qt_unit:
        qt = qt * 1000.0
    elif 'small' in qt_unit or 'box' in qt_unit or 'boxes' in qt_unit:
        paper_raw = find_value(['Paper speed', 'Paper Speed', 'mm/sec', 'mm/s'])
        paper = to_num(paper_raw)
        if paper == 50:
            qt = qt * 20.0
        else:
            qt = qt * 40.0

    rr = 60.0 / hr
    qtc = qt + 154.0 * (1.0 - rr)
    return qtc
