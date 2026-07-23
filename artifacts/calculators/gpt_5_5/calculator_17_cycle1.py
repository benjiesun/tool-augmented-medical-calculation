def calc(relevant):
    def is_true(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            return v.strip().lower() in {'yes', 'y', 'true', '1', 'present', 'positive'}
        return False

    def get_any(keys, default=None):
        for k in keys:
            if k in relevant:
                return relevant[k]
        return default

    score = 0

    if is_true(get_any(['Elevated-risk surgery', 'High-risk surgery'])):
        score += 1

    if is_true(get_any(['History of ischemic heart disease'])):
        score += 1

    if is_true(get_any(['Congestive Heart Failure criteria for the Cardiac Risk Index rule', 'History of congestive heart failure', 'History of congestive heart failure'])):
        score += 1

    if is_true(get_any(['History of cerebrovascular disease'])):
        score += 1

    if is_true(get_any(['Pre-operative treatment with insulin'])):
        score += 1

    creat = get_any(['Pre-operative creatinine', 'Pre-operative creatinine >2 mg/dL / 176.8 µmol/L'])
    creat_high = False
    if isinstance(creat, (list, tuple)) and len(creat) >= 1:
        try:
            val = float(creat[0])
            unit = str(creat[1]).lower() if len(creat) > 1 else 'mg/dl'
            if 'µmol' in unit or 'umol' in unit or 'micromol' in unit:
                creat_high = val > 176.8
            else:
                creat_high = val > 2.0
        except Exception:
            creat_high = False
    elif isinstance(creat, (int, float)):
        creat_high = float(creat) > 2.0
    else:
        creat_high = is_true(creat)

    if creat_high:
        score += 1

    return int(score)
