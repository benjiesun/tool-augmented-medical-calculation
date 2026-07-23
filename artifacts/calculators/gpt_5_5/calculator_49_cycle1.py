def calc(relevant):
    if not isinstance(relevant, dict):
        return 0

    def num(v):
        if isinstance(v, (list, tuple)):
            v = v[0] if v else 0
        try:
            return float(v)
        except Exception:
            return 0.0

    def norm(s):
        return ''.join(ch.lower() for ch in str(s) if ch.isalnum())

    def find_key(labels, per_day=False):
        if isinstance(labels, str):
            labels = [labels]
        for label in labels:
            target = norm(label)
            for k in relevant:
                nk = norm(k)
                if target in nk:
                    if per_day and 'doseperday' in nk:
                        return k
                    if not per_day and 'doseperday' not in nk:
                        return k
        return None

    rules = [
        (['Codeine'], 0.15, True),
        (['FentaNYL buccal', 'FentaNYL buccal or sublingual tablets'], 0.13, True),
        (['FentaNYL patch', 'FentaNYL patch (Duragesic)'], 2.4, False),
        (['HYDROcodone', 'HYDROcodone (Vicodin, Norco, Lortab)'], 1.0, True),
        (['HYDROmorphone', 'HYDROmorphone (Dilaudid)'], 5.0, True),
        (['Methadone'], 4.7, True),
        (['Morphine'], 1.0, True),
        (['OxyCODONE', 'OxyCODONE (OxyCONTIN, Roxicodone)'], 1.5, True),
        (['OxyMORphone'], 3.0, True),
        (['Tapentadol'], 0.4, True),
        (['TraMADol', 'TraMADol (Ultram)'], 0.2, True),
    ]

    total = 0.0
    for labels, factor, needs_day in rules:
        dose_key = find_key(labels, per_day=False)
        if dose_key is None:
            continue
        dose = num(relevant.get(dose_key))
        if needs_day:
            day_key = find_key(labels, per_day=True)
            day = num(relevant.get(day_key)) if day_key is not None else 1.0
        else:
            day = 1.0
        total += dose * day * factor

    return int(total + 0.5)
