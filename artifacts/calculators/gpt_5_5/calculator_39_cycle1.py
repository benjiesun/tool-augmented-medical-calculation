def calc(relevant):
    def norm_key(s):
        return ''.join([c.lower() for c in str(s) if c.isalnum()])

    def unwrap(v):
        if isinstance(v, dict):
            for k in ['value', 'val', 'number', 'result', 'amount']:
                if k in v:
                    return v[k]
            for k in v:
                return v[k]
            return None
        if isinstance(v, (list, tuple)):
            if len(v) == 0:
                return None
            return v[0]
        return v

    def to_number(v):
        v = unwrap(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            s = str(v).strip()
            if s == '':
                return None
            cleaned = ''
            dot_seen = False
            sign_allowed = True
            for ch in s:
                if ch in '+-' and sign_allowed:
                    cleaned += ch
                    sign_allowed = False
                elif ch.isdigit():
                    cleaned += ch
                    sign_allowed = False
                elif ch == '.' and not dot_seen:
                    cleaned += ch
                    dot_seen = True
                    sign_allowed = False
                elif cleaned:
                    break
            if cleaned in ['', '+', '-', '.', '+.', '-.']:
                return None
            return float(cleaned)
        except Exception:
            return None

    def get_value(names):
        if not isinstance(relevant, dict):
            return None
        lookup = {}
        for k in relevant:
            lookup[norm_key(k)] = relevant[k]
        for name in names:
            nk = norm_key(name)
            if nk in lookup:
                return to_number(lookup[nk])
        for k in relevant:
            nk = norm_key(k)
            for name in names:
                nn = norm_key(name)
                if nn and (nn in nk or nk in nn):
                    return to_number(relevant[k])
        return None

    sodium = get_value(['Sodium', 'Na', 'Na+', 'Serum sodium'])
    chloride = get_value(['Chloride', 'Cl', 'Cl-', 'Serum chloride'])
    bicarbonate = get_value(['Bicarbonate', 'HCO3', 'HCO3-', 'CO2', 'Total CO2', 'Serum bicarbonate'])

    if sodium is None or chloride is None or bicarbonate is None:
        return 'N/A'

    anion_gap = sodium - (chloride + bicarbonate)
    return float(anion_gap)
