def calc(relevant):
    def norm_key(k):
        s = str(k).strip().lower()
        return ''.join(ch for ch in s if ch.isalnum())

    def to_number(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if not s:
            return None
        try:
            return float(s)
        except:
            num = []
            seen = False
            dot = False
            sign = False
            exp = False
            for i, ch in enumerate(s):
                if ch.isdigit():
                    num.append(ch)
                    seen = True
                elif ch in '+-' and i == 0 and not sign:
                    num.append(ch)
                    sign = True
                elif ch == '.' and not dot and not exp:
                    num.append(ch)
                    dot = True
                elif ch in 'eE' and seen and not exp:
                    num.append(ch)
                    exp = True
                    sign = False
                    dot = True
                elif seen:
                    break
            try:
                return float(''.join(num)) if num else None
            except:
                return None

    def clean_unit(u):
        if u is None:
            return ''
        return str(u).strip().lower()

    def extract_value(v):
        if isinstance(v, dict):
            unit = None
            for uk in ['unit', 'units', 'uom', 'measureunit']:
                for kk in v.keys():
                    if norm_key(kk) == norm_key(uk):
                        unit = v[kk]
                        break
                if unit is not None:
                    break
            for vk in ['value', 'val', 'amount', 'number', 'num', 'measurement']:
                for kk in v.keys():
                    if norm_key(kk) == norm_key(vk):
                        return v[kk], unit
            for kk in v.keys():
                num = to_number(v[kk])
                if num is not None:
                    return v[kk], unit
            return None, unit
        if isinstance(v, (list, tuple)):
            if len(v) == 0:
                return None, None
            if len(v) == 1:
                return v[0], None
            return v[0], v[1]
        return v, None

    def find_key(data, aliases):
        if not isinstance(data, dict):
            return None
        lookup = {}
        for k in data.keys():
            lookup[norm_key(k)] = k
        for a in aliases:
            nk = norm_key(a)
            if nk in lookup:
                return data[lookup[nk]]
        return None

    def get_measure(data, aliases):
        raw = find_key(data, aliases)
        if raw is None:
            return None, None
        val, unit = extract_value(raw)
        num = to_number(val)
        if num is None:
            return None, unit
        return num, clean_unit(unit)

    def weight_kg(val, unit):
        u = unit.replace(' ', '')
        if u in ('lb', 'lbs', 'pound', 'pounds'):
            return val * 0.45359237
        if u in ('g', 'gram', 'grams'):
            return val / 1000.0
        return val

    def height_cm(val, unit):
        u = unit.replace(' ', '')
        if u in ('m', 'meter', 'meters', 'metre', 'metres'):
            return val * 100.0
        if u in ('mm', 'millimeter', 'millimeters', 'millimetre', 'millimetres'):
            return val / 10.0
        if u in ('in', 'inch', 'inches'):
            return val * 2.54
        if u in ('ft', 'foot', 'feet'):
            return val * 30.48
        return val

    w, wu = get_measure(relevant, ['weight', 'wt', 'mass'])
    h, hu = get_measure(relevant, ['height', 'ht', 'stature', 'length'])
    if w is None or h is None:
        return 'N/A'
    w = weight_kg(w, wu)
    h = height_cm(h, hu)
    if w <= 0 or h <= 0:
        return 'N/A'
    return (h * w / 3600.0) ** 0.5
