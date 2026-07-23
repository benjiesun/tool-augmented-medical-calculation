def calc(relevant):
    def norm(x):
        return ''.join(ch for ch in str(x).lower() if ch.isalnum()) if x is not None else ''
    def parse_num(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, dict):
            for k in ('value', 'val', 'amount', 'number', 'num', 'result'):
                for kk, vv in x.items():
                    if norm(kk) == norm(k):
                        n = parse_num(vv)
                        if n is not None:
                            return n
            for vv in x.values():
                n = parse_num(vv)
                if n is not None:
                    return n
            return None
        if isinstance(x, (list, tuple)):
            if len(x) == 2:
                n = parse_num(x[0])
                if n is not None:
                    return n
            for it in x:
                n = parse_num(it)
                if n is not None:
                    return n
            return None
        s = str(x).strip().replace(',', '')
        if not s:
            return None
        try:
            return float(s)
        except:
            token = ''
            started = False
            for ch in s:
                if ch.isdigit() or ch in '.-+eE':
                    token += ch
                    started = True
                elif started:
                    break
            try:
                return float(token) if token else None
            except:
                return None
    def parse_text(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 'true' if x else 'false'
        if isinstance(x, (str, int, float)):
            return str(x)
        if isinstance(x, (list, tuple)):
            if len(x) == 2 and isinstance(x[1], (str, int, float)):
                t = parse_text(x[1])
                if t is not None and t != '':
                    return t
            for it in x:
                t = parse_text(it)
                if t is not None and t != '':
                    return t
            return None
        if isinstance(x, dict):
            for k in ('unit', 'units', 'uom', 'measure', 'measurement', 'label', 'name', 'text'):
                for kk, vv in x.items():
                    if norm(kk) == norm(k):
                        t = parse_text(vv)
                        if t is not None and t != '':
                            return t
            return None
        return str(x)
    def find_key(obj, aliases):
        al = {norm(a) for a in aliases}
        if isinstance(obj, dict):
            for k, v in obj.items():
                if norm(k) in al:
                    return v
            for v in obj.values():
                if isinstance(v, (dict, list, tuple)):
                    f = find_key(v, aliases)
                    if f is not None:
                        return f
        elif isinstance(obj, (list, tuple)):
            for it in obj:
                f = find_key(it, aliases)
                if f is not None:
                    return f
        return None
    def get_value_and_unit(obj, aliases):
        v = find_key(obj, aliases)
        if v is None:
            return None, None
        num = parse_num(v)
        unit = None
        if isinstance(v, dict):
            unit = parse_text(v.get('unit') or v.get('units') or v.get('uom') or v.get('measure') or v.get('measurement'))
        elif isinstance(v, (list, tuple)) and len(v) >= 2:
            unit = parse_text(v[1])
        if unit is None:
            unit = parse_text(find_key(obj, [aliases[0] + ' unit', aliases[0] + ' units', 'unit', 'units', 'uom']))
        return num, unit
    calcium, calcium_unit = get_value_and_unit(relevant, ['calcium', 'serumcalcium', 'cacl2', 'serumca'])
    albumin, albumin_unit = get_value_and_unit(relevant, ['albumin', 'serumalbumin'])
    if calcium is None or albumin is None:
        return 'N/A'
    cu = norm(calcium_unit)
    au = norm(albumin_unit)
    if 'mmoll' in cu or (cu == 'mmol' if cu else False):
        calcium_mgdl = calcium * 4.0
    else:
        calcium_mgdl = calcium
    if 'gl' in au and 'gdl' not in au:
        albumin_gdl = albumin / 10.0
    else:
        albumin_gdl = albumin
    corrected = calcium_mgdl + 0.8 * (4.0 - albumin_gdl)
    return corrected
