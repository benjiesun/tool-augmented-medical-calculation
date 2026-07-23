def calc(relevant):
    if not isinstance(relevant, dict):
        relevant = {}

    def unwrap(v):
        if isinstance(v, (list, tuple)):
            if len(v) == 0:
                return None
            return v[0]
        if isinstance(v, dict):
            for k in ('value', 'val', 'answer', 'selected', 'result', 'input'):
                if k in v:
                    return v[k]
            for k in v:
                return v[k]
            return None
        return v

    def norm(s):
        out = ''
        for ch in str(s).lower():
            if ('a' <= ch <= 'z') or ('0' <= ch <= '9'):
                out += ch
        return out

    def get_any(keys, default=None):
        for k in keys:
            if k in relevant:
                return relevant[k]
        wanted = []
        for k in keys:
            wanted.append(norm(k))
        for rk in relevant:
            nrk = norm(rk)
            for wk in wanted:
                if nrk == wk:
                    return relevant[rk]
        return default

    def to_number(v):
        v = unwrap(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace(',', '').strip()
        token = ''
        started = False
        dot_seen = False
        sign_allowed = True
        for ch in s:
            if ch in '+-' and sign_allowed and not started:
                token += ch
                started = True
                sign_allowed = False
            elif ch.isdigit():
                token += ch
                started = True
                sign_allowed = False
            elif ch == '.' and not dot_seen:
                token += ch
                started = True
                dot_seen = True
                sign_allowed = False
            elif started:
                break
        if token in ('', '+', '-', '.', '+.', '-.'):
            return None
        try:
            return float(token)
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
        if s in ('yes', 'y', 'true', 't', '1', 'present', 'positive', 'pos', 'abnormal', 'high', 'elevated'):
            return True
        if s in ('no', 'n', 'false', 'f', '0', 'absent', 'negative', 'neg', 'normal', 'none', 'null', ''):
            return False
        n = to_number(s)
        if n is not None:
            return n != 0
        return False

    score = 0

    if to_bool(get_any(['Hypertension', 'Uncontrolled hypertension', 'HTN'])):
        score += 1

    if to_bool(get_any(['Renal disease criteria for the HAS-BLED rule', 'Renal disease', 'Abnormal renal function', 'Kidney disease'])):
        score += 1

    if to_bool(get_any(['Liver disease criteria for the HAS-BLED rule', 'Liver disease', 'Abnormal liver function', 'Hepatic disease'])):
        score += 1

    if to_bool(get_any(['Stroke', 'Stroke history', 'History of stroke', 'Prior stroke'])):
        score += 1

    if to_bool(get_any(['Prior major bleeding or predisposition to bleeding', 'Bleeding history', 'Bleeding predisposition', 'Major bleeding', 'Prior major bleeding'])):
        score += 1

    if to_bool(get_any(['Labile international normalized ratio', 'Labile INR', 'Labile inr', 'Unstable INR'])):
        score += 1

    age_raw = get_any(['age', 'Age'], None)
    age_num = to_number(age_raw)
    if age_num is not None:
        if age_num > 65:
            score += 1
    else:
        if to_bool(get_any(['Age >65', 'Age over 65', 'Elderly'])):
            score += 1

    med_raw = get_any(['Medication usage predisposing to bleeding', 'Drug usage predisposing to bleeding', 'Drugs', 'Antiplatelet or NSAID use', 'Aspirin clopidogrel NSAIDs'])
    if to_bool(med_raw):
        score += 1
    else:
        mv = unwrap(med_raw)
        if mv is not None:
            ms = str(mv).lower()
            if ('aspirin' in ms) or ('clopidogrel' in ms) or ('nsaid' in ms) or ('antiplatelet' in ms):
                score += 1

    drinks = to_number(get_any(['Number of Alcoholic Drinks Per Week', 'Alcoholic drinks per week', 'Drinks per week', 'Alcohol drinks/week']))
    if drinks is not None:
        if drinks >= 8:
            score += 1
    else:
        if to_bool(get_any(['Alcohol use', 'Alcohol usage', 'Alcohol', 'Excess alcohol use'])):
            score += 1

    return int(score)
