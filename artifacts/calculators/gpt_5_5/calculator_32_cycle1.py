def calc(relevant):
    def norm(x):
        return str(x).strip().lower().replace('_', ' ')

    def find_value(names):
        if not isinstance(relevant, dict):
            return None
        wanted = [norm(n) for n in names]
        for k in relevant:
            nk = norm(k)
            for w in wanted:
                if nk == w:
                    return relevant[k]
        for k in relevant:
            nk = norm(k)
            for w in wanted:
                if w in nk or nk in w:
                    return relevant[k]
        return None

    def scalar(v):
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return v[0]
        if isinstance(v, dict):
            for key in ['value', 'val', 'answer', 'result']:
                if key in v:
                    return v[key]
            for key in v:
                return v[key]
        return v

    def to_bool(v):
        v = scalar(v)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            s = norm(v)
            if s in ['yes', 'y', 'true', 't', 'present', 'positive', '1']:
                return True
            if s in ['no', 'n', 'false', 'f', 'absent', 'negative', '0', 'none']:
                return False
            if 'yes' in s or 'present' in s:
                return True
        return False

    def bool_key(names):
        return to_bool(find_value(names))

    def first_number(s):
        s = str(s)
        buf = ''
        seen = False
        dot = False
        for ch in s:
            if ch >= '0' and ch <= '9':
                buf += ch
                seen = True
            elif ch == '.' and seen and not dot:
                buf += ch
                dot = True
            elif seen:
                break
        if buf == '' or buf == '.':
            return None
        try:
            return float(buf)
        except Exception:
            return None

    score = 0

    age = scalar(find_value(['age', 'Age']))
    age_years = None
    if isinstance(age, (int, float)):
        age_years = float(age)
    elif isinstance(age, str):
        s = norm(age)
        if '<50' in s or '< 50' in s or 'under 50' in s:
            age_years = 49
        elif '80' in s and ('>=' in s or '≥' in s or 'older' in s or '+' in s):
            age_years = 80
        else:
            age_years = first_number(s)
    if age_years is not None:
        if age_years >= 80:
            score += 4
        elif age_years >= 70:
            score += 3
        elif age_years >= 60:
            score += 2
        elif age_years >= 50:
            score += 1

    if bool_key(['Myocardial infarction', 'MI']):
        score += 1
    if bool_key(['Congestive Heart Failure', 'CHF', 'congestive heart failure']):
        score += 1
    if bool_key(['Peripheral vascular disease', 'PVD']):
        score += 1
    if bool_key(['Cerebrovascular Accident', 'CVA', 'stroke', 'Transient Ischemic Attacks History', 'TIA', 'transient ischemic attack']):
        score += 1
    if bool_key(['Dementia']):
        score += 1
    if bool_key(['Chronic Pulmonary Disease', 'COPD', 'chronic pulmonary disease']):
        score += 1
    if bool_key(['Connective tissue disease', 'rheumatologic disease']):
        score += 1
    if bool_key(['Peptic ulcer disease', 'PUD']):
        score += 1

    liver = scalar(find_value(['Liver disease severity', 'liver disease']))
    if liver is not None:
        s = norm(liver)
        if 'moderate' in s or 'severe' in s:
            score += 3
        elif 'mild' in s:
            score += 1
        elif to_bool(liver):
            score += 1

    diabetes = scalar(find_value(['Diabetes mellitus', 'diabetes']))
    if diabetes is not None:
        s = norm(diabetes)
        if 'none' in s or 'diet' in s or s in ['no', 'false', '0']:
            pass
        elif 'end-organ' in s or 'end organ' in s or 'organ damage' in s or 'with complication' in s or 'with complications' in s:
            score += 2
        elif 'uncomplicated' in s or 'without complication' in s or 'without complications' in s or to_bool(diabetes):
            score += 1

    if bool_key(['Hemiplegia', 'paraplegia']):
        score += 2
    if bool_key(['Moderate to severe Chronic Kidney Disease', 'moderate to severe chronic kidney disease', 'CKD', 'renal disease', 'kidney disease']):
        score += 2

    tumor = scalar(find_value(['Solid tumor', 'solid tumour', 'tumor']))
    if tumor is not None:
        s = norm(tumor)
        if 'metastatic' in s or 'metastasis' in s or 'metastases' in s:
            score += 6
        elif 'localized' in s or 'localised' in s or ('solid' in s and 'none' not in s and 'no' != s):
            score += 2
        elif to_bool(tumor):
            score += 2

    if bool_key(['Leukemia', 'leukaemia']):
        score += 2
    if bool_key(['Lymphoma']):
        score += 2
    if bool_key(['AIDS', 'HIV/AIDS']):
        score += 6

    return int(score)
