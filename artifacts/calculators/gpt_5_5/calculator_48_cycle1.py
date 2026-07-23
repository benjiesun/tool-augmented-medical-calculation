def calc(relevant):
    def norm_key(k):
        return str(k).strip().lower()

    def get_any(relevant, names, default=None):
        if not isinstance(relevant, dict):
            return default
        idx = {norm_key(k): k for k in relevant.keys()}
        for name in names:
            k = idx.get(norm_key(name))
            if k is not None:
                return relevant.get(k, default)
        return default

    def num(v):
        if isinstance(v, dict):
            for key in ('value', 'val', 'number', 'amount'):
                if key in v:
                    v = v[key]
                    break
        if isinstance(v, (list, tuple)) and v:
            v = v[0]
        try:
            return float(v)
        except Exception:
            return None

    def flag(v):
        if isinstance(v, dict):
            for key in ('value', 'val', 'present', 'yes'):
                if key in v:
                    v = v[key]
                    break
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ('true', 'yes', 'y', '1', 'present'):
                return True
            if s in ('false', 'no', 'n', '0', 'absent'):
                return False
        return bool(v)

    score = 0

    age = num(get_any(relevant, ['age']))
    if age is not None and age >= 50:
        score += 1

    hr = num(get_any(relevant, ['Heart Rate or Pulse', 'Heart Rate', 'Pulse']))
    if hr is not None and hr >= 100:
        score += 1

    o2 = num(get_any(relevant, ['O₂ saturation percentage', 'O2 saturation percentage', 'O2 sat percentage', 'Oxygen saturation percentage']))
    if o2 is not None and o2 < 95:
        score += 1

    if flag(get_any(relevant, ['Unilateral Leg Swelling'])):
        score += 1

    if flag(get_any(relevant, ['Hemoptysis'])):
        score += 1

    if flag(get_any(relevant, ['Recent surgery or trauma'])):
        score += 1

    # Prior PE or DVT counts as one PERC criterion, not two separate points.
    prior_pe = flag(get_any(relevant, ['Previously Documented Pulmonary Embolism', 'Previously documented Pulmonary Embolism', 'Prior Pulmonary Embolism', 'Prior PE']))
    prior_dvt = flag(get_any(relevant, ['Previously documented Deep Vein Thrombosis', 'Previously Documented Deep Vein Thrombosis', 'Prior Deep Vein Thrombosis', 'Prior DVT']))
    if prior_pe or prior_dvt:
        score += 1

    if flag(get_any(relevant, ['Hormone use', 'Hormone Use'])):
        score += 1

    return score
