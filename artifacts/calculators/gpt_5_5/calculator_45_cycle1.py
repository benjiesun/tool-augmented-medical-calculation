def calc(relevant):
    def get_value(key, default=None):
        if key not in relevant:
            return default
        v = relevant.get(key)
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return v[0]
        return v

    def get_unit(key):
        v = relevant.get(key)
        if isinstance(v, (list, tuple)) and len(v) > 1:
            return str(v[1]).lower()
        return ""

    def to_float(x):
        try:
            return float(x)
        except Exception:
            return None

    score = 0

    confusion = get_value("Confusion", False)
    if isinstance(confusion, str):
        confusion_yes = confusion.strip().lower() in ["yes", "true", "1", "y", "confused", "present"]
    else:
        confusion_yes = bool(confusion)
    if confusion_yes:
        score += 1

    bun = to_float(get_value("Blood Urea Nitrogen (BUN)"))
    if bun is not None:
        unit = get_unit("Blood Urea Nitrogen (BUN)")
        if "mmol" in unit:
            if bun > 7:
                score += 1
        else:
            if bun > 19:
                score += 1

    rr = to_float(get_value("respiratory rate"))
    if rr is not None and rr >= 30:
        score += 1

    sbp = to_float(get_value("Systolic Blood Pressure"))
    dbp = to_float(get_value("Diastolic Blood Pressure"))
    if (sbp is not None and sbp < 90) or (dbp is not None and dbp <= 60):
        score += 1

    age = to_float(get_value("age"))
    if age is not None and age >= 65:
        score += 1

    return int(score)
