def calc(relevant):
    def find(keys, default=None):
        if not isinstance(relevant, dict):
            return default
        lowmap = {}
        for k in relevant:
            lowmap[str(k).strip().lower()] = k
        for key in keys:
            lk = str(key).strip().lower()
            if lk in lowmap:
                return relevant[lowmap[lk]]
        for key in keys:
            lk = str(key).strip().lower()
            for kk in lowmap:
                if lk == kk or lk in kk or kk in lk:
                    return relevant[lowmap[kk]]
        return default

    def num_unit(x):
        unit = None
        val = x
        if isinstance(x, (list, tuple)):
            if len(x) == 0:
                return None, None
            val = x[0]
            if len(x) > 1:
                unit = x[1]
        elif isinstance(x, dict):
            val = None
            for a in ['value', 'val', 'number', 'amount']:
                if a in x:
                    val = x[a]
                    break
            for a in ['unit', 'units']:
                if a in x:
                    unit = x[a]
                    break
        try:
            return float(val), unit
        except Exception:
            return None, unit

    def yes(x):
        if isinstance(x, bool):
            return x
        if isinstance(x, (int, float)):
            return x != 0
        if isinstance(x, str):
            s = x.strip().lower()
            return s in ['yes', 'y', 'true', 't', '1', 'on']
        return False

    def ln(x):
        if x <= 0:
            return None
        ln2 = 0.6931471805599453
        k = 0
        while x > 1.5:
            x = x / 2.0
            k += 1
        while x < 0.75:
            x = x * 2.0
            k -= 1
        y = (x - 1.0) / (x + 1.0)
        y2 = y * y
        term = y
        s = 0.0
        n = 1.0
        for i in range(40):
            s += term / n
            term *= y2
            n += 2.0
        return 2.0 * s + k * ln2

    bili, bu = num_unit(find(['Bilirubin', 'Total bilirubin', 'bilirubin']))
    cr, cu = num_unit(find(['creatinine', 'Creatinine', 'Cr', 'serum creatinine']))
    na, nu = num_unit(find(['Sodium', 'sodium', 'Na', 'serum sodium']))
    inr, iu = num_unit(find(['international normalized ratio', 'INR', 'inr']))
    if bili is None or cr is None or na is None or inr is None:
        return None

    if bu is not None:
        u = str(bu).lower()
        if 'umol' in u or 'µmol' in u or 'micromol' in u:
            bili = bili / 17.104
    if cu is not None:
        u = str(cu).lower()
        if 'umol' in u or 'µmol' in u or 'micromol' in u:
            cr = cr / 88.4

    dialysis = yes(find(['Dialysis at least twice in the past week', 'dialysis'], False))
    cvvhd = yes(find(['Continuous veno-venous hemodialysis for ≥24 hours in the past week', 'Continuous veno-venous hemodialysis for >=24 hours in the past week', 'CVVHD', 'continuous veno venous hemodialysis'], False))

    if bili < 1.0:
        bili = 1.0
    if cr < 1.0:
        cr = 1.0
    if inr < 1.0:
        inr = 1.0
    if cr > 4.0 or dialysis or cvvhd:
        cr = 4.0
    if na < 125.0:
        na = 125.0
    if na > 137.0:
        na = 137.0

    lcr = ln(cr)
    lbili = ln(bili)
    linr = ln(inr)
    if lcr is None or lbili is None or linr is None:
        return None

    meld_i = 10.0 * round(0.957 * lcr + 0.378 * lbili + 1.120 * linr + 0.643, 10)
    meld = meld_i
    if meld_i > 11.0:
        diff = 137.0 - na
        meld = meld_i + 1.32 * diff - 0.033 * meld_i * diff
    if meld > 40.0:
        meld = 40.0
    return float(round(meld))
