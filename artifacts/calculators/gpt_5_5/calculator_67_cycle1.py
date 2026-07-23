def calc(relevant):
    def _unwrap(x):
        unit = None
        val = x
        if isinstance(x, dict):
            for k in ['value', 'val', 'number', 'num', 'result', 'answer']:
                if k in x:
                    val = x.get(k)
                    break
            for k in ['unit', 'units', 'u']:
                if k in x:
                    unit = x.get(k)
                    break
        elif isinstance(x, (list, tuple)):
            if len(x) > 0:
                val = x[0]
            if len(x) > 1:
                unit = x[1]
        return val, unit

    def _finite(v):
        return v == v and v != float('inf') and v != -float('inf')

    def _to_float(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            v = float(x)
            return v if _finite(v) else None
        if isinstance(x, str):
            s = x.strip().replace(',', '')
            if not s:
                return None
            token = ''
            started = False
            prev = ''
            for ch in s:
                ok = ('0' <= ch <= '9') or ch in ['.', '+', '-', 'e', 'E']
                if ok:
                    if ch in ['+', '-'] and started and prev not in ['e', 'E']:
                        if token:
                            break
                    token += ch
                    started = True
                    prev = ch
                elif started:
                    break
            try:
                v = float(token)
                return v if _finite(v) else None
            except Exception:
                return None
        return None

    def _unit_text(u):
        if u is None:
            return ''
        return str(u).strip().lower().replace('µ', 'u')

    def _norm_key(k):
        return str(k).strip().lower().replace('_', ' ').replace('-', ' ')

    def _find_key(names):
        if not isinstance(relevant, dict):
            return None
        norm = {}
        for k in relevant.keys():
            norm[_norm_key(k)] = k
        for name in names:
            n = _norm_key(name)
            if n in norm:
                return norm[n]
        for k in relevant.keys():
            kl = _norm_key(k)
            for name in names:
                n = _norm_key(name)
                if n in kl or kl in n:
                    return k
        return None

    def read_number(names):
        k = _find_key(names)
        if k is None:
            return None, ''
        val, unit = _unwrap(relevant.get(k))
        return _to_float(val), _unit_text(unit)

    def read_text(names):
        k = _find_key(names)
        if k is None:
            return None
        val, unit = _unwrap(relevant.get(k))
        if isinstance(val, str):
            return val
        if unit is not None:
            return str(unit)
        return None

    def read_bool(names):
        k = _find_key(names)
        if k is None:
            return None
        val, unit = _unwrap(relevant.get(k))
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ['true', 'yes', 'y', '1', 'positive', 'pos']:
                return True
            if s in ['false', 'no', 'n', '0', 'negative', 'neg']:
                return False
        return None

    sodium, sodium_u = read_number(['Sodium', 'Na', 'Na+'])
    chloride, chloride_u = read_number(['Chloride', 'Cl', 'Cl-'])
    bicarbonate, bicarbonate_u = read_number(['Bicarbonate', 'HCO3', 'HCO3-', 'CO2', 'Carbon dioxide'])
    albumin, albumin_u = read_number(['Albumin', 'Alb'])

    if sodium is None or chloride is None or bicarbonate is None or albumin is None:
        return None

    alb_g_dl = albumin
    au = albumin_u.replace(' ', '')
    if au in ['g/l', 'gpl', 'gram/l', 'grams/l'] or 'g/l' in au:
        alb_g_dl = albumin / 10.0
    elif au in ['mg/dl', 'mgdl', 'milligram/dl', 'milligrams/dl'] or 'mg/dl' in au:
        alb_g_dl = albumin / 1000.0
    elif au in ['mg/l', 'mgl'] or 'mg/l' in au:
        alb_g_dl = albumin / 10000.0

    anion_gap = sodium - (chloride + bicarbonate)
    corrected_ag = anion_gap + 2.5 * (4.0 - alb_g_dl)
    delta_gap = corrected_ag - 12.0
    denom = 24.0 - bicarbonate
    if denom == 0:
        return None
    return delta_gap / denom
