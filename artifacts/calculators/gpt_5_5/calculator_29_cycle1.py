def calc(relevant):
    def get_val(key, default=None):
        v = relevant.get(key, default)
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return v[0]
        return v

    def get_unit(key):
        v = relevant.get(key)
        if isinstance(v, (list, tuple)) and len(v) > 1:
            return str(v[1]).lower()
        return ""

    score = 0

    age = get_val("age", 0) or 0
    sex = str(get_val("sex", "")).strip().lower()
    if sex.startswith("f"):
        score += max(0, int(age) - 10)
    else:
        score += int(age)

    if bool(get_val("Nursing home resident", False)):
        score += 10
    if bool(get_val("Neoplastic disease", False)):
        score += 30
    if bool(get_val("Liver disease history", False)):
        score += 20
    if bool(get_val("Congestive Heart Failure", False)):
        score += 10
    if bool(get_val("Cerebrovascular disease history", False)):
        score += 10
    if bool(get_val("Renal disease history", False)):
        score += 10
    if bool(get_val("Altered mental status", False)):
        score += 20

    rr = get_val("respiratory rate")
    if rr is not None and float(rr) >= 30:
        score += 20

    sbp = get_val("Systolic Blood Pressure")
    if sbp is not None and float(sbp) < 90:
        score += 20

    temp = get_val("Temperature")
    if temp is not None:
        unit = get_unit("Temperature")
        t = float(temp)
        if "f" in unit:
            temp_c = (t - 32.0) * 5.0 / 9.0
        else:
            temp_c = t
        if temp_c < 35.0 or temp_c > 39.9:
            score += 15

    pulse = get_val("Heart Rate or Pulse")
    if pulse is not None and float(pulse) >= 125:
        score += 10

    ph = get_val("pH")
    if ph is not None and float(ph) < 7.35:
        score += 30

    bun = get_val("Blood Urea Nitrogen (BUN)")
    if bun is not None and float(bun) >= 30:
        score += 20

    sodium = get_val("Sodium")
    if sodium is not None and float(sodium) < 130:
        score += 20

    glucose = get_val("Glucose")
    if glucose is not None and float(glucose) >= 250:
        score += 10

    hematocrit = get_val("Hematocrit")
    if hematocrit is not None and float(hematocrit) < 30:
        score += 10

    p_o2 = get_val("Partial pressure of oxygen")
    if p_o2 is not None and float(p_o2) < 60:
        score += 10

    if bool(get_val("Pleural effusion on x-ray", False)):
        score += 10

    return int(score)
