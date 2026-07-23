def calc(relevant):
    def _norm(x):
        return ''.join(ch.lower() for ch in str(x) if ch.isalnum())

    def _text(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return 'true' if v else 'false'
        return str(v)

    def _num(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, dict):
            for kk in ('value', 'val', 'amount', 'number', 'num', 'measurement'):
                for k2, v2 in v.items():
                    if _norm(k2) == _norm(kk):
                        n = _num(v2)
                        if n is not None:
                            return n
            if len(v) == 1:
                return _num(next(iter(v.values())))
            return None
        if isinstance(v, (list, tuple)):
            for item in v:
                n = _num(item)
                if n is not None:
                    return n
            return None
        s = _text(v)
        if s is None:
            return None
        s = s.strip()
        if not s or s.lower() in ('na', 'n/a', 'none', 'null', 'nan'):
            return None
        try:
            return float(s)
        except:
            pass
        buf = ''
        started = False
        for ch in s:
            if ch in '+-0123456789.eE':
                buf += ch
                started = True
            elif started:
                break
        try:
            return float(buf)
        except:
            return None

    def _unit(v):
        if isinstance(v, dict):
            for kk in ('unit', 'units', 'uom', 'measure', 'measureunit'):
                for k2, v2 in v.items():
                    if _norm(k2) == _norm(kk):
                        return _text(v2)
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            return _text(v[1])
        return None

    def _value(v):
        if isinstance(v, dict):
            for kk in ('value', 'val', 'amount', 'number', 'num', 'measurement'):
                for k2, v2 in v.items():
                    if _norm(k2) == _norm(kk):
                        n = _num(v2)
                        if n is not None:
                            return n
            if len(v) == 1:
                return _num(next(iter(v.values())))
        if isinstance(v, (list, tuple)) and v:
            return _num(v[0]) if len(v) >= 1 else None
        return _num(v)

    def _find(obj, aliases):
        if isinstance(obj, dict):
            wanted = {_norm(a) for a in aliases}
            for k, v in obj.items():
                if _norm(k) in wanted:
                    return v
            for v in obj.values():
                if isinstance(v, (dict, list, tuple)):
                    r = _find(v, aliases)
                    if r is not None:
                        return r
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                r = _find(item, aliases)
                if r is not None:
                    return r
        return None

    def _weight_kg(v):
        n = _value(v)
        if n is None:
            return None
        u = _norm(_unit(v) or '')
        if u in ('lb', 'lbs', 'pound', 'pounds') or 'pound' in u:
            return n * 0.45359237
        if u in ('g', 'gram', 'grams'):
            return n / 1000.0
        return n

    def _height_m(v):
        n = _value(v)
        if n is None:
            return None
        u = _norm(_unit(v) or '')
        if u in ('cm', 'centimeter', 'centimeters', 'centimetre', 'centimetres'):
            return n / 100.0
        if u in ('m', 'meter', 'meters', 'metre', 'metres'):
            return n
        if u in ('mm', 'millimeter', 'millimeters', 'millimetre', 'millimetres'):
            return n / 1000.0
        if u in ('in', 'inch', 'inches'):
            return n * 0.0254
        if u in ('ft', 'foot', 'feet'):
            return n * 0.3048
        return n / 100.0 if n > 10 else n

    w_raw = _find(relevant, ('weight', 'wt', 'bodyweight', 'mass'))
    h_raw = _find(relevant, ('height', 'ht', 'stature', 'bodyheight'))
    w = _weight_kg(w_raw)
    h = _height_m(h_raw)
    if w is None or h is None or h <= 0:
        return 'N/A'
    return round(w / (h * h), 5)
