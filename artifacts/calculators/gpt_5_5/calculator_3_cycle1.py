def calc(relevant):
    def _norm(x):
        return ''.join(ch.lower() for ch in str(x) if ch.isalnum())

    def _unwrap(v):
        if isinstance(v, dict):
            for k in ('value', 'val', 'data', 'amount', 'number', 'text'):
                if k in v:
                    return _unwrap(v[k])
            for k, val in v.items():
                if _norm(k) not in ('unit', 'units', 'uom', 'type', 'label', 'description', 'desc'):
                    return _unwrap(val)
            return None
        if isinstance(v, (list, tuple)):
            return _unwrap(v[0]) if v else None
        return v

    def _txt(v):
        v = _unwrap(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return 'true' if v else 'false'
        s = str(v).strip()
        return s if s else None

    def _num(v):
        v = _unwrap(v)
        if v is None or isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(',', '')
        if not s:
            return None
        try:
            return float(s)
        except:
            return None

    def _unit(v):
        if isinstance(v, dict):
            for k in ('unit', 'units', 'uom', 'measureunit'):
                for kk, vv in v.items():
                    if _norm(kk) == _norm(k):
                        t = _txt(vv)
                        return t
            return None
        if isinstance(v, (list, tuple)):
            if len(v) >= 2:
                u = v[1]
                if u is None or isinstance(u, bool):
                    return None
                if isinstance(u, dict):
                    return _unit(u)
                s = str(u).strip()
                return s if s else None
        return None

    def _get(*names):
        if not isinstance(relevant, dict):
            return None
        norms = [_norm(n) for n in names]
        for k, v in relevant.items():
            nk = _norm(k)
            if nk in norms:
                return v
        for k, v in relevant.items():
            nk = _norm(k)
            for n in norms:
                if n and (n in nk or nk in n):
                    return v
        return None

    def _creatinine_mgdl(raw):
        scr = _num(raw)
        if scr is None:
            return None
        u = _unit(raw)
        if u:
            uu = str(u).strip().lower().replace('μ', 'u').replace('µ', 'u').replace(' ', '')
            if 'umol' in uu or 'micromol' in uu:
                scr = scr / 88.4
            elif 'mmol' in uu:
                scr = scr * 11.312217194570136
        return scr

    sex = _txt(_get('sex', 'gender'))
    age = _num(_get('age', 'years'))
    scr = _creatinine_mgdl(_get('creatinine', 'scr', 'serum creatinine', 'serumcreatinine'))

    if sex is None or age is None or scr is None:
        return 'N/A'

    s = sex.strip().lower()
    female = s.startswith('f')
    male = s.startswith('m')
    if not (female or male):
        return 'N/A'

    k = 0.7 if female else 0.9
    a = -0.241 if female else -0.302
    x = scr / k
    egfr = 142.0 * (min(x, 1.0) ** a) * (max(x, 1.0) ** -1.2) * (0.9938 ** age)
    if female:
        egfr *= 1.012
    return round(egfr, 5)
