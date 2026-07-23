def calc(relevant):
    if not isinstance(relevant, dict):
        return 'N/A'

    def _norm_key(k):
        return str(k).strip().lower()

    def _norm_unit(u):
        if u is None:
            return None
        return str(u).strip().lower().replace(' ', '').replace('_', '')

    def _to_num(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return float(x)
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            s = x.strip().replace(',', '')
            if s == '' or s.lower() in ('na', 'n/a', 'none', 'null'):
                return None
            try:
                return float(s)
            except Exception:
                return None
        if isinstance(x, (list, tuple)):
            if not x:
                return None
            return _to_num(x[0])
        if isinstance(x, dict):
            for key in ('value', 'val', 'amount', 'number', 'numeric', 'data'):
                if key in x:
                    n = _to_num(x[key])
                    if n is not None:
                        return n
            if len(x) == 1:
                return _to_num(next(iter(x.values())))
            for v in x.values():
                n = _to_num(v)
                if n is not None:
                    return n
            return None
        return None

    def _get_unit(x):
        if x is None:
            return None
        if isinstance(x, dict):
            for key in ('unit', 'units', 'uom', 'measure'):
                if key in x and x[key] is not None:
                    return str(x[key]).strip().lower()
            if len(x) == 1:
                return _get_unit(next(iter(x.values())))
            return None
        if isinstance(x, (list, tuple)):
            if len(x) >= 2 and x[1] is not None:
                return str(x[1]).strip().lower()
            if len(x) == 1:
                return _get_unit(x[0])
        return None

    def _get_field(d, names):
        if not isinstance(d, dict):
            return None
        lookup = {}
        for k, v in d.items():
            if isinstance(k, str):
                lookup[_norm_key(k)] = v
        wanted = [_norm_key(n) for n in names]
        for w in wanted:
            if w in lookup:
                return lookup[w]
        for k, v in d.items():
            nk = _norm_key(k)
            for w in wanted:
                if w in nk or nk in w:
                    return v
        return None

    def _to_mgdl(value, unit, kind):
        if value is None:
            return None
        u = _norm_unit(unit)
        if u is None or u in ('mg/dl', 'mgdl', 'mgperdl'):
            return value
        if u in ('mmol/l', 'mmol/liter', 'mmolperl'):
            return value * (2.8 if kind == 'bun' else 18.0)
        if u in ('g/l', 'gperl', 'gram/l', 'grams/l'):
            return value * 100.0
        return value

    sodium_obj = _get_field(relevant, ['Sodium'])
    bun_obj = _get_field(relevant, ['Blood Urea Nitrogen (BUN)', 'Blood Urea Nitrogen', 'BUN'])
    glucose_obj = _get_field(relevant, ['Glucose'])
    ethanol_obj = _get_field(relevant, ['Serum alcohol concentration', 'Serum alcohol', 'Ethanol', 'Alcohol'])

    if sodium_obj is None or bun_obj is None or glucose_obj is None:
        return 'N/A'

    na = _to_num(sodium_obj)
    bun = _to_num(bun_obj)
    glu = _to_num(glucose_obj)
    if na is None or bun is None or glu is None:
        return 'N/A'

    bun_unit = _get_unit(bun_obj)
    glu_unit = _get_unit(glucose_obj)
    bun_mgdl = _to_mgdl(bun, bun_unit, 'bun')
    glu_mgdl = _to_mgdl(glu, glu_unit, 'glucose')
    if bun_mgdl is None or glu_mgdl is None:
        return 'N/A'

    osm = 2.0 * na + (bun_mgdl / 2.8) + (glu_mgdl / 18.0)

    if ethanol_obj is not None:
        eth = _to_num(ethanol_obj)
        if eth is not None:
            eth_unit = _get_unit(ethanol_obj)
            if _norm_unit(eth_unit) in ('g/l', 'gperl', 'gram/l', 'grams/l'):
                eth = eth * 100.0
            osm += eth / 4.6

    return float(osm)
