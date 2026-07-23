def calc(relevant):
    def num(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            s = x.strip()
            if not s:
                return None
            l = s.lower()
            if l in ('true', 't', 'yes', 'y'):
                return 1.0
            if l in ('false', 'f', 'no', 'n'):
                return 0.0
            try:
                return float(s)
            except:
                return None
        return None

    def txt(x):
        return '' if x is None else str(x).strip()

    def find(obj, key):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).strip().lower() == key:
                    return v
            for v in obj.values():
                r = find(v, key)
                if r is not None:
                    return r
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                r = find(v, key)
                if r is not None:
                    return r
        return None

    def extract(x):
        unit = None
        val = x
        if isinstance(x, dict):
            for k in ('unit', 'units', 'uom', 'measure_unit'):
                if k in x:
                    unit = txt(x[k])
                    break
            for k in ('value', 'val', 'amount', 'number', 'numeric', 'result'):
                if k in x:
                    val = x[k]
                    break
            else:
                if len(x) == 1:
                    val = next(iter(x.values()))
        elif isinstance(x, (list, tuple)):
            if not x:
                return None, None
            val = x[0]
            if len(x) > 1:
                unit = txt(x[1])
        return val, unit

    def unit_norm(u):
        return txt(u).lower().replace('µ', 'u').replace('μ', 'u').replace(' ', '')

    g_raw = find(relevant, 'glucose')
    i_raw = find(relevant, 'insulin')
    if g_raw is None or i_raw is None:
        return 'N/A'

    g_val, g_unit = extract(g_raw)
    i_val, i_unit = extract(i_raw)
    g = num(g_val)
    i = num(i_val)
    if g is None or i is None:
        return 'N/A'

    gu = unit_norm(g_unit)
    iu = unit_norm(i_unit)
    if not gu:
        gu = 'mmol/l' if g <= 40 else 'mg/dl'
    if not iu:
        iu = 'pmol/l' if i > 50 else 'uiu/ml'

    g_mgdl = g * 18.0 if 'mmol' in gu else g
    denom = 67.5 if 'pmol' in iu else 405.0
    return (i * g_mgdl) / denom
