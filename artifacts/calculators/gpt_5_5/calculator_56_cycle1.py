def calc(relevant):
    def parse_text(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 'true' if x else 'false'
        return str(x).strip()

    def parse_bool(x):
        if isinstance(x, bool):
            return x
        s = parse_text(x)
        if s is None:
            return None
        s = s.lower()
        if s in ('true', 't', 'yes', 'y', '1'):
            return True
        if s in ('false', 'f', 'no', 'n', '0'):
            return False
        return None

    def parse_number(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, (list, tuple)):
            for item in x:
                val = parse_number(item)
                if val is not None:
                    return val
            return None
        if isinstance(x, dict):
            for key in ('value', 'num', 'number', 'amount', 'val'):
                if key in x:
                    val = parse_number(x.get(key))
                    if val is not None:
                        return val
            for val in x.values():
                num = parse_number(val)
                if num is not None:
                    return num
            return None
        s = parse_text(x)
        if not s:
            return None
        s = s.replace(',', '')
        num = ''
        started = False
        dot_used = False
        sign_used = False
        for ch in s:
            if ch.isdigit():
                num += ch
                started = True
            elif ch in '+-' and not started and not sign_used:
                num += ch
                sign_used = True
            elif ch == '.' and not dot_used:
                num += ch
                dot_used = True
                started = True
            elif started:
                break
        if num in ('', '+', '-', '.', '+.', '-.'):
            return None
        try:
            return float(num)
        except:
            return None

    def find_value(obj, aliases):
        if obj is None:
            return None
        if isinstance(obj, dict):
            for k, v in obj.items():
                ks = parse_text(k)
                if ks is not None:
                    low = ks.lower()
                    for a in aliases:
                        if low == a.lower():
                            return v
            for v in obj.values():
                found = find_value(v, aliases)
                if found is not None:
                    return found
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                found = find_value(item, aliases)
                if found is not None:
                    return found
        return None

    if not isinstance(relevant, dict):
        return 'N/A'

    hr_raw = find_value(relevant, ('Heart Rate or Pulse', 'Heart Rate', 'Pulse', 'HR'))
    qt_raw = find_value(relevant, ('QT Interval', 'QT'))
    speed_raw = find_value(relevant, ('Paper speed, mm/sec', 'Paper speed', 'Speed'))

    hr = parse_number(hr_raw)
    qt = parse_number(qt_raw)
    if hr is None or qt is None or hr <= 0:
        return 'N/A'

    qt_unit = ''
    if isinstance(qt_raw, dict):
        for key in ('unit', 'units', 'uom'):
            if key in qt_raw:
                qt_unit = parse_text(qt_raw.get(key)) or ''
                break
    elif isinstance(qt_raw, (list, tuple)) and len(qt_raw) >= 2:
        qt_unit = parse_text(qt_raw[1]) or ''

    qt_unit_l = qt_unit.lower()
    if 'small' in qt_unit_l or 'box' in qt_unit_l:
        speed = parse_number(speed_raw)
        if speed == 50:
            qt = qt * 20.0
        else:
            qt = qt * 40.0

    rr = 60.0 / hr
    qtc = qt / (rr ** (1.0 / 3.0))
    return float(qtc)
