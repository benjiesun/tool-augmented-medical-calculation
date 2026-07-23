def calc(relevant):
    def unwrap(v):
        if isinstance(v, dict):
            for k in ['value', 'val', 'number', 'num', 'amount', 'result']:
                if k in v:
                    return v[k]
                for kk in v:
                    if str(kk).lower() == k:
                        return v[kk]
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
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s == '':
            return None
        s = s.replace(',', '')
        low = s.lower()
        if low in ['na', 'n/a', 'none', 'null', 'nan']:
            return None
        num = ''
        started = False
        for ch in s:
            if ch in '0123456789.-+eE':
                num += ch
                started = True
            elif started:
                break
        try:
            return float(num)
        except Exception:
            return None

    def get_value(keys):
        if not isinstance(relevant, dict):
            return None
        aliases = []
        for key in keys:
            aliases.append(str(key).lower())
        for k, v in relevant.items():
            lk = str(k).strip().lower()
            compact = lk.replace(' ', '').replace('_', '').replace('-', '')
            for a in aliases:
                ac = a.replace(' ', '').replace('_', '').replace('-', '')
                if lk == a or compact == ac:
                    return to_number(v)
        for k, v in relevant.items():
            lk = str(k).strip().lower()
            compact = lk.replace(' ', '').replace('_', '').replace('-', '')
            for a in aliases:
                ac = a.replace(' ', '').replace('_', '').replace('-', '')
                if a in lk or ac in compact:
                    return to_number(v)
        return None

    sodium = get_value(['Sodium', 'Na', 'Na+', 'serum sodium'])
    chloride = get_value(['Chloride', 'Cl', 'Cl-', 'serum chloride'])
    bicarbonate = get_value(['Bicarbonate', 'HCO3', 'HCO3-', 'CO2', 'carbon dioxide', 'serum bicarbonate'])

    if sodium is None or chloride is None or bicarbonate is None:
        return 'N/A'

    denominator = 24.0 - bicarbonate
    if denominator == 0:
        return 'N/A'

    anion_gap = sodium - (chloride + bicarbonate)
    result = (anion_gap - 12.0) / denominator
    return result
