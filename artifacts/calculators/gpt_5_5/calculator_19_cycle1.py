def calc(relevant):
    def unpack(x):
        unit = ''
        val = x
        if isinstance(x, dict):
            for k in ('value', 'val', 'number', 'amount'):
                if k in x:
                    val = x[k]
                    break
            for k in ('unit', 'units'):
                if k in x:
                    unit = x[k]
                    break
        elif isinstance(x, (list, tuple)):
            if len(x) > 0:
                val = x[0]
            if len(x) > 1:
                unit = x[1]
        return float(val), str(unit)

    def get(names):
        low = {}
        for k in relevant:
            low[str(k).lower()] = k
        for name in names:
            key = str(name).lower()
            if key in low:
                return unpack(relevant[low[key]])
        for name in names:
            key = str(name).lower()
            for lk, ok in low.items():
                if key in lk or lk in key:
                    return unpack(relevant[ok])
        raise KeyError(names[0])

    age, age_unit = get(('age', 'Age'))
    ast, ast_unit = get(('Aspartate aminotransferase', 'AST', 'SGOT'))
    alt, alt_unit = get(('Alanine aminotransferase', 'ALT', 'SGPT'))
    platelets, plt_unit = get(('Platelet count', 'Platelets', 'platelet'))

    u = plt_unit.lower().replace(' ', '').replace('/', '').replace('per', '')
    if 'µl' in u or 'μl' in u or 'ul' in u or 'mcl' in u or 'mm3' in u or 'mm^3' in u:
        plt = platelets / 1000.0 if platelets > 10000 else platelets
    elif '10^9' in u or 'x10^9' in u or '109' in u:
        plt = platelets
    elif u in ('l', 'liter', 'litre') or 'liter' in u or 'litre' in u:
        plt = platelets / 1000000000.0 if platelets > 10000 else platelets
    else:
        if platelets > 100000000:
            plt = platelets / 1000000000.0
        elif platelets > 10000:
            plt = platelets / 1000.0
        else:
            plt = platelets

    if alt <= 0 or plt <= 0:
        return None
    return (age * ast) / (plt * (alt ** 0.5))
