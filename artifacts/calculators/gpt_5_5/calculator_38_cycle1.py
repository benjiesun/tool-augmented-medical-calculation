def calc(relevant):
    def _find(keys):
        if not isinstance(relevant, dict):
            return None
        lk = {str(k).strip().lower(): v for k, v in relevant.items()}
        for k in keys:
            if k in lk:
                return lk[k]
        return None

    def _wrap(v):
        if isinstance(v, dict):
            for k in ('value', 'val', 'amount', 'number', 'input', 'text', 'data'):
                if k in v:
                    return v[k]
            for vv in v.values():
                return vv
            return None
        if isinstance(v, (list, tuple)):
            return v[0] if len(v) > 0 else None
        return v

    def _unit(v):
        if isinstance(v, dict):
            for k in ('unit', 'units', 'uom', 'measure'):
                if k in v:
                    return _wrap(v[k])
            if 'value' in v and isinstance(v.get('value'), (list, tuple)) and len(v['value']) > 1:
                return _wrap(v['value'][1])
            return None
        if isinstance(v, (list, tuple)) and len(v) > 1:
            return _wrap(v[1])
        return None

    def _text(v):
        v = _wrap(v)
        if v is None:
            return None
        s = str(v).strip().lower()
        return s if s else None

    def _num(v):
        v = _wrap(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return float(v)
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return None
        try:
            return float(s)
        except:
            num = ''
            started = False
            dot = False
            for ch in s:
                if ch in '+-' and not started:
                    num += ch
                    started = True
                elif ch.isdigit():
                    num += ch
                    started = True
                elif ch == '.' and not dot:
                    num += ch
                    started = True
                    dot = True
                elif started:
                    break
            try:
                return float(num) if num not in ('', '+', '-', '.') else None
            except:
                return None

    def _age_years(v):
        n = _num(v)
        if n is None:
            return None
        u = _text(_unit(v))
        if u:
            if 'month' in u or u in ('mo', 'mos'):
                return n / 12.0
            if 'year' in u or u in ('yr', 'yrs', 'y'):
                return n
        return n

    def _weight_kg(v):
        n = _num(v)
        if n is None:
            return None
        u = _text(_unit(v))
        if u:
            if 'lb' in u or 'pound' in u:
                return n / 2.2046226218
            if u in ('g', 'gram', 'grams'):
                return n / 1000.0
        return n

    def _sex(v):
        s = _text(v)
        if not s:
            return None
        if s.startswith('m'):
            return 'male'
        if s.startswith('f'):
            return 'female'
        return None

    age = _find(('age',))
    sex = _sex(_find(('sex', 'gender')))
    weight = _weight_kg(_find(('weight', 'wt')))
    sodium = _num(_find(('sodium', 'na')))
    agey = _age_years(age)

    if agey is None or sex is None or weight is None or sodium is None:
        return 'N/A'

    if agey < 18:
        tbw = 0.6
    elif agey >= 65:
        tbw = 0.5 if sex == 'male' else 0.45
    else:
        tbw = 0.6 if sex == 'male' else 0.5

    result = tbw * weight * ((sodium / 140.0) - 1.0)
    return result
