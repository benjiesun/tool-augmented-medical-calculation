def _norm_key(k):
    s = str(k).lower().strip()
    out = ''
    for ch in s:
        if ch.isalnum():
            out += ch
    return out

def _get_value_unit(v):
    unit = None
    val = v
    if isinstance(v, dict):
        for kk in v:
            nk = _norm_key(kk)
            if nk in ('value','val','number','num','amount'):
                val = v[kk]
            elif nk in ('unit','units','u'):
                unit = v[kk]
    elif isinstance(v, (list, tuple)):
        if len(v) > 0:
            val = v[0]
        if len(v) > 1:
            unit = v[1]
    return val, unit

def _to_float(x):
    if x is None:
        return None
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        return float(x)
    try:
        s = str(x).strip().replace(',', '')
        if s == '':
            return None
        return float(s)
    except Exception:
        return None

def _read_num(relevant, aliases):
    if not isinstance(relevant, dict):
        return None, None
    amap = {}
    for k, v in relevant.items():
        amap[_norm_key(k)] = v
    for a in aliases:
        na = _norm_key(a)
        if na in amap:
            val, unit = _get_value_unit(amap[na])
            return _to_float(val), unit
    return None, None

def _read_text(relevant, aliases):
    if not isinstance(relevant, dict):
        return None
    amap = {}
    for k, v in relevant.items():
        amap[_norm_key(k)] = v
    for a in aliases:
        na = _norm_key(a)
        if na in amap:
            val, unit = _get_value_unit(amap[na])
            if val is None:
                return None
            return str(val).strip()
    return None

def _unit_text(unit):
    if unit is None:
        return ''
    return str(unit).lower().strip().replace('.', '')

def _height_to_inches(value, unit):
    if value is None:
        return None
    u = _unit_text(unit)
    if u in ('cm','centimeter','centimeters'):
        return value / 2.54
    if u in ('m','meter','meters','metre','metres'):
        return value * 100.0 / 2.54
    if u in ('in','inch','inches'):
        return value
    if u in ('ft','foot','feet'):
        return value * 12.0
    if value > 100.0:
        return value / 2.54
    if value < 3.0:
        return value * 100.0 / 2.54
    return value

def _weight_to_kg(value, unit):
    if value is None:
        return None
    u = _unit_text(unit)
    if u in ('lb','lbs','pound','pounds'):
        return value * 0.45359237
    if u in ('g','gram','grams'):
        return value / 1000.0
    return value

def calc(relevant):
    sex = _read_text(relevant, ['sex', 'gender'])
    height_val, height_unit = _read_num(relevant, ['height', 'ht', 'stature'])
    weight_val, weight_unit = _read_num(relevant, ['weight', 'actual body weight', 'actual weight', 'body weight', 'abw', 'tbw'])
    if sex is None or height_val is None or weight_val is None:
        return 'N/A'
    sex_l = sex.lower().strip()
    if sex_l.startswith('m'):
        base = 50.0
    elif sex_l.startswith('f'):
        base = 45.5
    else:
        return 'N/A'
    height_in = _height_to_inches(height_val, height_unit)
    weight_kg = _weight_to_kg(weight_val, weight_unit)
    if height_in is None or weight_kg is None:
        return 'N/A'
    ibw = base + 2.3 * (height_in - 60.0)
    adjusted = ibw + 0.4 * (weight_kg - ibw)
    return adjusted
