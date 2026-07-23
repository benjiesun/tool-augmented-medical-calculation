def calc(relevant):
    def norm_key(x):
        s = str(x).lower()
        out = ''
        for ch in s:
            if ch.isalnum():
                out += ch
        return out

    def find_value(data, aliases):
        if not isinstance(data, dict):
            return None
        alias_norms = []
        for a in aliases:
            alias_norms.append(norm_key(a))
        for k in data:
            nk = norm_key(k)
            if nk in alias_norms:
                return data[k]
        for k in data:
            nk = norm_key(k)
            for a in alias_norms:
                if a and (a in nk or nk in a):
                    return data[k]
        return None

    def to_number(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            s = x.strip()
            cleaned = ''
            seen_digit = False
            for ch in s:
                if ch.isdigit() or ch in '.-+':
                    cleaned += ch
                    if ch.isdigit():
                        seen_digit = True
                elif seen_digit:
                    break
            try:
                return float(cleaned)
            except Exception:
                return None
        return None

    def extract_number_unit(v):
        num = None
        unit = None
        if isinstance(v, dict):
            for nk in ['value', 'val', 'number', 'num', 'amount', 'weight']:
                if nk in v and num is None:
                    num = to_number(v[nk])
            if num is None:
                for k in v:
                    cand = to_number(v[k])
                    if cand is not None:
                        num = cand
                        break
            for uk in ['unit', 'units', 'u']:
                if uk in v and v[uk] is not None:
                    unit = str(v[uk])
                    break
        elif isinstance(v, (list, tuple)):
            if len(v) > 0:
                num = to_number(v[0])
            if len(v) > 1 and v[1] is not None:
                unit = str(v[1])
            if num is None:
                for item in v:
                    cand = to_number(item)
                    if cand is not None:
                        num = cand
                        break
        else:
            num = to_number(v)
            if isinstance(v, str):
                unit = v
        return num, unit

    def weight_to_kg(value, unit):
        if value is None:
            return None
        if unit is None:
            return float(value)
        u = str(unit).lower().strip()
        compact = ''
        for ch in u:
            if ch.isalpha():
                compact += ch
        if compact in ['kg', 'kgs', 'kilogram', 'kilograms']:
            return float(value)
        if compact in ['g', 'gm', 'gram', 'grams']:
            return float(value) / 1000.0
        if compact in ['mg', 'milligram', 'milligrams']:
            return float(value) / 1000000.0
        if compact in ['lb', 'lbs', 'pound', 'pounds']:
            return float(value) * 0.45359237
        if compact in ['oz', 'ounce', 'ounces']:
            return float(value) * 0.028349523125
        if compact in ['st', 'stone', 'stones']:
            return float(value) * 6.35029318
        return float(value)

    raw_wt = find_value(relevant, ['weight', 'body weight', 'wt', 'mass'])
    wt_val, wt_unit = extract_number_unit(raw_wt)
    kg = weight_to_kg(wt_val, wt_unit)
    if kg is None or kg < 0:
        return 'N/A'

    if kg <= 10:
        rate = 4.0 * kg
    elif kg <= 20:
        rate = 40.0 + 2.0 * (kg - 10.0)
    else:
        rate = 60.0 + (kg - 20.0)
    return rate
