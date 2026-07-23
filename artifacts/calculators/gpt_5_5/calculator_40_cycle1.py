def calc(relevant):
    def get_num(x):
        if isinstance(x, dict):
            for k in ('value', 'val', 'amount'):
                if k in x:
                    return get_num(x[k])
            for v in x.values():
                n = get_num(v)
                if n is not None:
                    return n
            return None
        if isinstance(x, (list, tuple)):
            if not x:
                return None
            return get_num(x[0])
        try:
            if x is None:
                return None
            return float(x)
        except (TypeError, ValueError):
            return None

    def norm(s):
        return ''.join(ch.lower() for ch in str(s) if ch.isalnum())

    aliases = {
        'Sodium': ('Sodium', 'Serum sodium', 'serum sodium', 'Na', 'S Na', 'sodium'),
        'Urine sodium': ('Urine sodium', 'Urine Na', 'U Na', 'urinesodium', 'urinena'),
        'creatinine': ('creatinine', 'Serum creatinine', 'serum creatinine', 'S Cr', 'Scr', 'creatinine'),
        'Urine creatinine': ('Urine creatinine', 'Urine Cr', 'U Cr', 'urinecreatinine', 'urinecr'),
    }

    lookup = {}
    for k, v in relevant.items():
        lookup[norm(k)] = v

    vals = {}
    for out_key, alist in aliases.items():
        found = None
        for a in alist:
            nk = norm(a)
            if nk in lookup:
                found = get_num(lookup[nk])
                if found is not None:
                    break
        vals[out_key] = found

    s_na = vals['Sodium']
    u_na = vals['Urine sodium']
    s_cr = vals['creatinine']
    u_cr = vals['Urine creatinine']

    if None in (s_na, u_na, s_cr, u_cr) or s_na == 0 or u_cr == 0:
        return None

    return 100.0 * (s_cr * u_na) / (s_na * u_cr)
