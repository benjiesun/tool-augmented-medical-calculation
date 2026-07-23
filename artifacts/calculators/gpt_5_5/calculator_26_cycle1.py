def calc(relevant):
    def _norm(x):
        if x is None:
            return ''
        s = str(x).lower()
        out = ''
        for ch in s:
            if ch.isalnum():
                out += ch
        return out

    def _text(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 'true' if x else 'false'
        if isinstance(x, (int, float)):
            return str(x)
        if isinstance(x, (list, tuple)):
            for v in x:
                t = _text(v)
                if t is not None:
                    return t
            return None
        if isinstance(x, dict):
            for kk, vv in x.items():
                if _norm(kk) in ('text', 'value', 'val', 'label', 'name', 'unit', 'uom'):
                    t = _text(vv)
                    if t is not None:
                        return t
            for vv in x.values():
                t = _text(vv)
                if t is not None:
                    return t
            return None
        s = str(x).strip()
        return s if s else None

    def _num(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, (list, tuple)):
            if not x:
                return None
            n = _num(x[0])
            if n is not None:
                return n
            for v in x[1:]:
                n = _num(v)
                if n is not None:
                    return n
            return None
        if isinstance(x, dict):
            for kk, vv in x.items():
                if _norm(kk) in ('value', 'val', 'number', 'num', 'amount', 'score', 'result'):
                    n = _num(vv)
                    if n is not None:
                        return n
            for vv in x.values():
                n = _num(vv)
                if n is not None:
                    return n
            return None
        if isinstance(x, str):
            s = x.strip().replace(',', '')
            if not s:
                return None
            try:
                return float(s)
            except:
                num = ''
                seen_dot = False
                seen_sign = False
                started = False
                for ch in s:
                    if ch.isdigit():
                        num += ch
                        started = True
                    elif ch in '+-' and not started and not seen_sign:
                        num += ch
                        seen_sign = True
                    elif ch == '.' and not seen_dot:
                        num += ch
                        seen_dot = True
                        started = True
                    elif started:
                        break
                if num in ('', '+', '-', '.'):
                    return None
                try:
                    return float(num)
                except:
                    return None
        return None

    def _unit(x):
        if x is None:
            return None
        if isinstance(x, dict):
            for kk, vv in x.items():
                if _norm(kk) in ('unit', 'uom', 'units', 'measure', 'measureunit', 'unitname'):
                    t = _text(vv)
                    if t is not None:
                        return t
            for kk, vv in x.items():
                if _norm(kk) in ('value', 'val', 'number', 'num', 'amount', 'score', 'result'):
                    if isinstance(vv, (list, tuple)) and len(vv) >= 2:
                        t = _text(vv[1])
                        if t is not None:
                            return t
            for vv in x.values():
                t = _unit(vv)
                if t is not None:
                    return t
            return None
        if isinstance(x, (list, tuple)):
            if len(x) >= 2:
                t = _text(x[1])
                if t is not None:
                    return t
            for v in x:
                t = _unit(v)
                if t is not None:
                    return t
        return None

    def _match_key(key, aliases):
        nk = _norm(key)
        if not nk:
            return False
        for a in aliases:
            na = _norm(a)
            if na and (nk == na or na in nk or nk in na):
                return True
        return False

    def _find_field(obj, aliases):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if _match_key(k, aliases):
                    return v
            for v in obj.values():
                found = _find_field(v, aliases)
                if found is not None:
                    return found
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                found = _find_field(v, aliases)
                if found is not None:
                    return found
        return None

    glucose_entry = _find_field(relevant, ('glucose', 'serumglucose', 'bloodglucose', 'bloodsugar', 'sugar', 'bg'))
    sodium_entry = _find_field(relevant, ('sodium', 'serumsodium', 'na', 'sodiumlevel'))

    glucose = _num(glucose_entry)
    sodium = _num(sodium_entry)
    if glucose is None or sodium is None:
        return 'N/A'

    unit = _unit(glucose_entry)
    if unit is not None:
        u = _norm(unit)
        if 'mmol' in u:
            glucose = glucose * 18.016

    corrected = sodium + 0.024 * (glucose - 100.0)
    return corrected
