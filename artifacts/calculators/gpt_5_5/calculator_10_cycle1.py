def calc(relevant):
    def _norm_key(x):
        s = str(x).strip().lower()
        out = ''
        for ch in s:
            if ch.isalnum():
                out += ch
        return out

    def _find_key(d, names):
        if not isinstance(d, dict):
            return None
        targets = [_norm_key(n) for n in names]
        for k, v in d.items():
            nk = _norm_key(k)
            if nk in targets:
                return v
        return None

    def _extract(obj):
        if isinstance(obj, dict):
            for k in ['value', 'val', 'text', 'name', 'content']:
                v = _find_key(obj, [k])
                if v is not None:
                    return _extract(v)
            if len(obj) == 1:
                for _, v in obj.items():
                    return _extract(v)
            return obj
        if isinstance(obj, (list, tuple)):
            if len(obj) == 0:
                return None
            return _extract(obj[0])
        return obj

    def _parse_text(obj):
        obj = _extract(obj)
        if obj is None:
            return None
        return str(obj).strip()

    def _parse_number(obj):
        obj = _extract(obj)
        if obj is None:
            return None
        if isinstance(obj, bool):
            return 1.0 if obj else 0.0
        if isinstance(obj, (int, float)):
            return float(obj)
        s = str(obj).strip()
        if s == '':
            return None
        try:
            return float(s)
        except:
            t = ''
            seen = False
            for ch in s:
                if ch.isdigit() or ch in '.+-eE':
                    t += ch
                    seen = True
                elif seen:
                    break
            try:
                return float(t) if t else None
            except:
                return None

    def _get_unit(obj):
        if isinstance(obj, dict):
            v = _find_key(obj, ['unit', 'units', 'uom'])
            if v is not None:
                return _parse_text(v)
        if isinstance(obj, (list, tuple)) and len(obj) >= 2:
            return _parse_text(obj[1])
        return None

    if not isinstance(relevant, dict):
        return 'N/A'

    sex_raw = _find_key(relevant, ['sex', 'gender'])
    height_raw = _find_key(relevant, ['height', 'ht', 'stature'])

    sex_text = _parse_text(sex_raw)
    height_val = _parse_number(height_raw)
    height_unit = _get_unit(height_raw)

    if sex_text is None or height_val is None:
        return 'N/A'

    s = _norm_key(sex_text)
    if s.startswith('f') or 'woman' in s or 'female' in s:
        base = 45.5
    elif s.startswith('m') or 'man' in s or 'male' in s:
        base = 50.0
    else:
        return 'N/A'

    inches = None
    u = _norm_key(height_unit) if height_unit is not None else ''
    if u in ['cm', 'centimeter', 'centimeters']:
        inches = height_val / 2.54
    elif u in ['m', 'meter', 'meters']:
        inches = height_val * 39.37007874015748
    elif u in ['mm', 'millimeter', 'millimeters']:
        inches = height_val / 25.4
    elif u in ['in', 'inch', 'inches', 'inchs']:
        inches = height_val
    elif u in ['ft', 'foot', 'feet']:
        inches = height_val * 12.0
    else:
        if height_val > 100.0:
            inches = height_val / 2.54
        elif height_val > 10.0:
            inches = height_val
        elif height_val > 3.0:
            inches = height_val * 12.0
        else:
            inches = height_val

    if inches is None:
        return 'N/A'

    ibw = base + 2.3 * (inches - 60.0)
    return ibw
