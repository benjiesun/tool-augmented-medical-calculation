def calc(relevant):
    def pick(name, aliases):
        if not isinstance(relevant, dict):
            return None
        keys = [name] + aliases
        for k in keys:
            if k in relevant:
                return relevant.get(k)
        low = {}
        for k in relevant:
            low[str(k).strip().lower()] = k
        for k in keys:
            lk = str(k).strip().lower()
            if lk in low:
                return relevant.get(low[lk])
        return None

    def val_unit(x):
        if isinstance(x, dict):
            v = None
            for kk in ('value', 'val', 'amount', 'num', 'number'):
                if kk in x:
                    v = x.get(kk)
                    break
            if v is None:
                for kk in x:
                    if str(kk).lower() not in ('unit', 'units'):
                        v = x.get(kk)
                        break
            u = x.get('unit', x.get('units', ''))
            return v, u
        if isinstance(x, (list, tuple)):
            if len(x) == 0:
                return None, ''
            if len(x) == 1:
                return x[0], ''
            return x[0], x[1]
        return x, ''

    def num(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return float(x)
        if isinstance(x, str):
            s = x.strip().replace(',', '')
            if s == '':
                return None
            try:
                return float(s)
            except Exception:
                return None
        try:
            return float(x)
        except Exception:
            return None

    def get_num(name, aliases):
        v, u = val_unit(pick(name, aliases))
        return num(v), str(u).strip().lower()

    age, age_u = get_num('age', ['years', 'yr', 'yrs'])
    weight, wt_u = get_num('weight', ['wt', 'actual_weight', 'actual body weight', 'body_weight'])
    cr, cr_u = get_num('creatinine', ['serum_creatinine', 'scr', 'cr'])
    height, ht_u = get_num('height', ['ht', 'stature'])

    sex_x = pick('sex', ['gender'])
    sex_v, sex_u = val_unit(sex_x)
    sex = str(sex_v if sex_v is not None else '').strip().lower()

    if age is None or weight is None or cr is None or cr == 0:
        return None

    if 'month' in age_u or age_u in ('mo', 'mos'):
        age = age / 12.0
    elif 'day' in age_u:
        age = age / 365.25
    elif 'week' in age_u:
        age = age / 52.1775

    if 'lb' in wt_u or 'pound' in wt_u:
        weight = weight * 0.45359237
    elif wt_u in ('g', 'gram', 'grams'):
        weight = weight / 1000.0
    elif wt_u in ('oz', 'ounce', 'ounces'):
        weight = weight * 0.028349523125

    if 'umol' in cr_u or 'µmol' in cr_u or 'micromol' in cr_u or 'mcmol' in cr_u:
        cr = cr / 88.4
    elif cr_u in ('mg/l', 'mg per l', 'mg/litre', 'mg/liter'):
        cr = cr / 10.0

    calc_weight = weight
    if height is not None and height > 0:
        if ht_u in ('m', 'meter', 'meters', 'metre', 'metres'):
            height_in = height * 39.37007874015748
        elif ht_u in ('cm', 'centimeter', 'centimeters', 'centimetre', 'centimetres'):
            height_in = height / 2.54
        elif ht_u in ('mm', 'millimeter', 'millimeters', 'millimetre', 'millimetres'):
            height_in = height / 25.4
        elif 'ft' in ht_u or 'foot' in ht_u or 'feet' in ht_u:
            height_in = height * 12.0
        elif ht_u in ('in', 'inch', 'inches', ''):
            if ht_u == '' and height < 3.0:
                height_in = height * 39.37007874015748
            elif ht_u == '' and height > 100.0:
                height_in = height / 2.54
            else:
                height_in = height
        else:
            height_in = height

        if height_in > 0:
            if sex.startswith('f') or sex in ('woman', 'female'):
                ibw = 45.5 + 2.3 * (height_in - 60.0)
            else:
                ibw = 50.0 + 2.3 * (height_in - 60.0)
            if ibw > 0 and weight > ibw:
                calc_weight = ibw + 0.4 * (weight - ibw)
            else:
                calc_weight = weight

    factor = 0.85 if (sex.startswith('f') or sex in ('woman', 'female')) else 1.0
    return ((140.0 - age) * calc_weight * factor) / (72.0 * cr)
