def calc(relevant):
    def _num(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return float(int(x))
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            s = x.strip()
            if not s:
                return None
            try:
                return float(s)
            except Exception:
                buf = ''
                seen = False
                for ch in s:
                    if ch.isdigit() or ch in '.-+eE':
                        buf += ch
                        seen = True
                    elif seen:
                        break
                try:
                    return float(buf) if buf else None
                except Exception:
                    return None
        if isinstance(x, (list, tuple)):
            if not x:
                return None
            return _num(x[0])
        if isinstance(x, dict):
            for k in ('value', 'val', 'amount', 'number', 'numeric', 'text'):
                if k in x:
                    v = _num(x[k])
                    if v is not None:
                        return v
            for v in x.values():
                vv = _num(v)
                if vv is not None:
                    return vv
        return None

    def _unit(x):
        if isinstance(x, (list, tuple)) and len(x) > 1 and x[1] is not None:
            return str(x[1]).strip().lower()
        if isinstance(x, dict):
            for k in ('unit', 'units', 'u'):
                if k in x and x[k] is not None:
                    return str(x[k]).strip().lower()
        return None

    def _get(d, key):
        if not isinstance(d, dict):
            return None
        t = key.strip().lower()
        for k, v in d.items():
            if isinstance(k, str) and k.strip().lower() == t:
                return v
        return None

    def _field(d, names):
        if not isinstance(d, dict):
            return None
        for n in names:
            v = _get(d, n)
            if v is not None:
                return v
        return None

    sodium_raw = _field(relevant, ('Sodium', 'Na', 'Na+'))
    chloride_raw = _field(relevant, ('Chloride', 'Cl', 'Cl-'))
    bicarb_raw = _field(relevant, ('Bicarbonate', 'HCO3', 'HCO3-', 'HCO 3', 'CO2', 'Total CO2'))
    albumin_raw = _field(relevant, ('Albumin', 'Alb'))

    sodium = _num(sodium_raw)
    chloride = _num(chloride_raw)
    bicarbonate = _num(bicarb_raw)
    albumin = _num(albumin_raw)
    if sodium is None or chloride is None or bicarbonate is None or albumin is None:
        return None

    u = _unit(albumin_raw)
    if u:
        if 'g/l' in u or u == 'g per l':
            albumin = albumin / 10.0
        elif 'mg/dl' in u:
            albumin = albumin / 1000.0

    anion_gap = sodium - (chloride + bicarbonate)
    corrected_anion_gap = anion_gap + 2.5 * (4.0 - albumin)
    corrected_delta_gap = corrected_anion_gap - 12.0
    return float(round(corrected_delta_gap, 6))
