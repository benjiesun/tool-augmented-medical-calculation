def calc(relevant):
    score = 0

    def _find(names):
        if not isinstance(relevant, dict):
            return None
        lookup = {str(k).strip().lower(): v for k, v in relevant.items()}
        for name in names:
            key = str(name).strip().lower()
            if key in lookup:
                return lookup[key]
        return None

    def _unpack(x):
        unit = None
        if isinstance(x, dict):
            unit = x.get('unit', x.get('units'))
            for vk in ('value', 'amount', 'measurement'):
                if vk in x:
                    x = x[vk]
                    break
            else:
                if len(x) == 1:
                    x = next(iter(x.values()))
        elif isinstance(x, (list, tuple)):
            if len(x) >= 2:
                unit = x[1]
            if len(x) >= 1:
                x = x[0]
        return x, unit

    def _num_unit(x):
        x, unit = _unpack(x)
        try:
            val = float(x)
        except Exception:
            return None, None
        if unit is None:
            return val, None
        return val, str(unit).strip().lower()

    temp = _find(['Temperature', 'temp'])
    if temp is not None:
        t, unit = _num_unit(temp)
        if t is not None:
            if unit is not None:
                u = unit.replace(' ', '').replace('°', '')
                if 'fahrenheit' in u or u in ('f', 'degf'):
                    t = (t - 32.0) * 5.0 / 9.0
            if t > 38.0 or t < 36.0:
                score += 1

    hr = _find(['Heart Rate or Pulse', 'Heart Rate', 'Pulse', 'HR'])
    if hr is not None:
        h, _ = _num_unit(hr)
        if h is not None and h > 90.0:
            score += 1

    rr = _find(['respiratory rate', 'Respiratory Rate', 'resp rate', 'RR'])
    paco2 = _find(['PaCO2', 'PACO2', 'Pa CO2', 'PCO2', 'pco2'])
    resp_positive = False
    if rr is not None:
        r, _ = _num_unit(rr)
        if r is not None and r > 20.0:
            resp_positive = True
    if paco2 is not None:
        p, _ = _num_unit(paco2)
        if p is not None and p < 32.0:
            resp_positive = True
    if resp_positive:
        score += 1

    wbc = _find(['White blood cell count', 'WBC', 'white blood cell count'])
    if wbc is not None:
        w, _ = _num_unit(wbc)
        if w is not None and (w > 12000.0 or w < 4000.0):
            score += 1

    return int(score)
