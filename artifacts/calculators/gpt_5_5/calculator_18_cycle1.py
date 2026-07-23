def calc(relevant):
    def unwrap(v):
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return v[0]
        if isinstance(v, dict):
            for k in ['value', 'val', 'answer', 'result']:
                if k in v:
                    return v[k]
            for k in v:
                return v[k]
        return v

    def norm_key(s):
        t = str(s).lower()
        out = ''
        for ch in t:
            if ch.isalnum():
                out += ch
        return out

    def get_val(d, aliases):
        if not isinstance(d, dict):
            return None
        amap = {}
        for k in d:
            amap[norm_key(k)] = k
        for a in aliases:
            nk = norm_key(a)
            if nk in amap:
                return d[amap[nk]]
        return None

    def to_num(v):
        v = unwrap(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return 1 if v else 0
        if isinstance(v, (int, float)):
            return v
        s = str(v).strip().lower()
        if s == '':
            return None
        cleaned = ''
        started = False
        dot_seen = False
        sign_seen = False
        for ch in s:
            if ch in '+-' and not started and not sign_seen:
                cleaned += ch
                sign_seen = True
                started = True
            elif ch.isdigit():
                cleaned += ch
                started = True
            elif ch == '.' and not dot_seen:
                cleaned += ch
                dot_seen = True
                started = True
            elif started:
                break
        try:
            return float(cleaned)
        except Exception:
            return None

    def to_bool(v):
        v = unwrap(v)
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        s = str(v).strip().lower()
        if s in ['true', 't', 'yes', 'y', '1', 'present', 'positive', 'pos', 'history', 'known']:
            return True
        if s in ['false', 'f', 'no', 'n', '0', 'absent', 'negative', 'neg', 'none', 'nil']:
            return False
        if 'no ' in s or 'without' in s or 'denies' in s:
            return False
        return False

    def to_text(v):
        v = unwrap(v)
        if v is None:
            return None
        return str(v).strip().lower()

    age_v = get_val(relevant, ['age', 'patient age'])
    hist_v = get_val(relevant, ['Suspicion History', 'history', 'clinical history', 'history suspicion', 'suspicious history'])
    ecg_v = get_val(relevant, ['Electrocardiogram Test', 'ECG', 'EKG', 'electrocardiogram'])
    trop_v = get_val(relevant, ['Initial troponin', 'troponin', 'initial troponin level'])

    age = to_num(age_v)
    hist = to_text(hist_v)
    ecg = to_text(ecg_v)
    trop = to_text(trop_v)
    if age is None or hist is None or ecg is None or trop is None:
        return 'N/A'

    score = 0

    if age >= 65:
        score += 2
    elif age >= 45:
        score += 1

    if 'high' in hist or 'highly' in hist:
        score += 2
    elif 'moderate' in hist or 'moderately' in hist:
        score += 1
    elif 'slight' in hist or 'slightly' in hist or 'low' in hist or 'non' in hist:
        score += 0
    else:
        return 'N/A'

    if 'st' in ecg and ('depress' in ecg or 'elevat' in ecg or 'deviation' in ecg):
        score += 2
    elif 'significant' in ecg and 'st' in ecg:
        score += 2
    elif 'normal' in ecg and 'non' not in ecg and 'abnormal' not in ecg:
        score += 0
    elif 'nonspecific' in ecg or 'non-specific' in ecg or 'repolar' in ecg or 'abnormal' in ecg or 'lbbb' in ecg or 'rbbb' in ecg or 'bundle' in ecg or 'paced' in ecg:
        score += 1
    else:
        return 'N/A'

    risk_count = 0
    risk_items = [
        ['Hypertension history', 'hypertension', 'htn'],
        ['Diabetes mellitus', 'diabetes', 'dm'],
        ['hypercholesterolemia', 'hyperlipidemia', 'high cholesterol', 'dyslipidemia'],
        ['obesity', 'obese'],
        ['smoking', 'smoker', 'tobacco use'],
        ['parent or sibling with Cardiovascular disease before age 65', 'family history cardiovascular disease', 'family history cad', 'family history coronary artery disease', 'parent sibling cvd before age 65']
    ]
    for aliases in risk_items:
        if to_bool(get_val(relevant, aliases)):
            risk_count += 1

    known_athero = False
    if to_bool(get_val(relevant, ['atherosclerotic disease', 'atherosclerosis', 'known atherosclerotic disease', 'coronary artery disease', 'cad', 'peripheral arterial disease', 'pad', 'prior mi', 'myocardial infarction'])):
        known_athero = True
    if to_bool(get_val(relevant, ['Transient Ischemic Attacks History', 'TIA history', 'transient ischemic attack history', 'stroke history', 'cva history'])):
        known_athero = True

    if known_athero or risk_count >= 3:
        score += 2
    elif risk_count >= 1:
        score += 1

    tn = to_num(trop_v)
    if 'less' in trop or '<=' in trop or '≤' in trop or 'normal limit' in trop and ('less' in trop or 'equal' in trop or 'normal' == trop):
        score += 0
    elif 'greater than three' in trop or '>3' in trop or '> 3' in trop or 'three times' in trop or '3 times' in trop:
        score += 2
    elif '1-3' in trop or 'one to three' in trop or 'greater' in trop or 'elevated' in trop or 'above' in trop:
        score += 1
    elif tn is not None:
        if tn <= 1:
            score += 0
        elif tn <= 3:
            score += 1
        else:
            score += 2
    else:
        return 'N/A'

    return int(score)
