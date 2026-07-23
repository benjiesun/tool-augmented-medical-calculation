def calc(relevant):
    def get_value(key, default=None):
        v = relevant.get(key, default)
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return v[0]
        return v

    def get_unit(key):
        v = relevant.get(key)
        if isinstance(v, (list, tuple)) and len(v) > 1:
            return str(v[1]).lower()
        return ""

    def to_float(x, default=0.0):
        try:
            if x is None:
                return default
            return float(x)
        except Exception:
            return default

    def to_bool(x):
        if isinstance(x, bool):
            return x
        if x is None:
            return False
        if isinstance(x, (int, float)):
            return x != 0
        s = str(x).strip().lower()
        return s in ("yes", "y", "true", "t", "1", "present", "positive")

    score = 0

    bun = to_float(get_value("Blood Urea Nitrogen (BUN)"))
    bun_unit = get_unit("Blood Urea Nitrogen (BUN)")
    if "mmol" in bun_unit:
        bun_mg_dl = bun * 2.8
    else:
        bun_mg_dl = bun

    if bun_mg_dl >= 70:
        score += 6
    elif bun_mg_dl >= 28:
        score += 4
    elif bun_mg_dl >= 22.4:
        score += 3
    elif bun_mg_dl >= 18.2:
        score += 2

    sbp = to_float(get_value("Systolic Blood Pressure"))
    if sbp < 90:
        score += 3
    elif sbp <= 99:
        score += 2
    elif sbp <= 109:
        score += 1

    hr = to_float(get_value("Heart Rate or Pulse"))
    if hr >= 100:
        score += 1

    hgb = to_float(get_value("Hemoglobin"))
    hgb_unit = get_unit("Hemoglobin")
    if "g/l" in hgb_unit and "g/dl" not in hgb_unit:
        hgb = hgb / 10.0

    sex = str(relevant.get("sex", "")).strip().lower()
    if sex.startswith("m"):
        if hgb < 10:
            score += 6
        elif hgb < 12:
            score += 3
        elif hgb < 13:
            score += 1
    else:
        if hgb < 10:
            score += 6
        elif hgb < 12:
            score += 1

    if to_bool(relevant.get("Melena Present")):
        score += 1
    if to_bool(relevant.get("Recent Syncope")):
        score += 2
    if to_bool(relevant.get("Hepatic disease history")):
        score += 2
    if to_bool(relevant.get("Cardiac Failure Present")):
        score += 2

    return int(score)
