def calc(relevant):
    def _is_num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    def _to_num(x):
        if _is_num(x):
            return float(x)
        if isinstance(x, str):
            s = x.strip()
            if s == '':
                return None
            try:
                return float(s)
            except:
                return None
        if isinstance(x, dict):
            for k in ('value', 'val', 'number', 'amount', 'height', 'bmi'):
                if k in x:
                    return _to_num(x.get(k))
        if isinstance(x, (list, tuple)):
            if len(x) > 0:
                return _to_num(x[0])
        return None

    def _lower(s):
        return s.strip().lower() if isinstance(s, str) else ''

    def _find_key(d, aliases):
        if not isinstance(d, dict):
            return None
        alias_set = [_lower(a) for a in aliases]
        for k in d.keys():
            kk = _lower(str(k))
            for a in alias_set:
                if kk == a:
                    return k
        for k in d.keys():
            kk = _lower(str(k))
            for a in alias_set:
                if a in kk:
                    return k
        return None

    def _extract_value_and_unit(v):
        if isinstance(v, dict):
            val = None
            unit = None
            for k in v.keys():
                lk = _lower(str(k))
                if lk in ('value', 'val', 'number', 'amount'):
                    val = _to_num(v.get(k))
                elif lk in ('unit', 'units'):
                    unit = v.get(k)
            if val is None:
                val = _to_num(v)
            return val, unit
        if isinstance(v, (list, tuple)):
            val = _to_num(v[0]) if len(v) > 0 else None
            unit = v[1] if len(v) > 1 else None
            return val, unit
        return _to_num(v), None

    if not isinstance(relevant, dict):
        return 'N/A'

    bmi_key = _find_key(relevant, ['Body Mass Index (BMI)', 'BMI', 'body mass index'])
    h_key = _find_key(relevant, ['height', 'ht'])
    if bmi_key is None or h_key is None:
        return 'N/A'

    bmi_val, _ = _extract_value_and_unit(relevant.get(bmi_key))
    h_val, h_unit = _extract_value_and_unit(relevant.get(h_key))
    if bmi_val is None or h_val is None:
        return 'N/A'

    unit = _lower(h_unit) if isinstance(h_unit, str) else ''
    if unit in ('in', 'inch', 'inches', '"'):
        height_m = h_val * 0.0254
    elif unit in ('cm', 'centimeter', 'centimeters'):
        height_m = h_val / 100.0
    elif unit in ('m', 'meter', 'meters'):
        height_m = h_val
    elif unit in ('ft', 'feet', 'foot'):
        height_m = h_val * 0.3048
    else:
        if h_val > 10:
            height_m = h_val / 100.0
        else:
            height_m = h_val

    return bmi_val * (height_m ** 2)
