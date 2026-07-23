def calc(relevant):
    def get(key, default=None):
        return relevant.get(key, default)

    def val(key, default=None):
        x = get(key, default)
        if isinstance(x, (list, tuple)) and len(x) > 0:
            return x[0]
        return x

    def unit(key):
        x = get(key)
        if isinstance(x, (list, tuple)) and len(x) > 1:
            return str(x[1]).lower()
        return ""

    def num(key, default=None):
        x = val(key, default)
        try:
            return float(x)
        except Exception:
            return default

    def yes(key):
        x = get(key, False)
        if isinstance(x, (list, tuple)) and len(x) > 0:
            x = x[0]
        if isinstance(x, bool):
            return x
        if x is None:
            return False
        return str(x).strip().lower() in ["yes", "true", "1", "y"]

    total = 0

    # Age points
    age = num("age")
    if age is not None:
        if age >= 75:
            total += 6
        elif age >= 65:
            total += 5
        elif age >= 55:
            total += 3
        elif age >= 45:
            total += 2

    # Temperature, convert F to C if needed
    t = num("Temperature")
    if t is not None:
        u = unit("Temperature")
        if "f" in u or t > 60:
            t = (t - 32.0) * 5.0 / 9.0
        if t >= 41:
            total += 4
        elif t >= 39:
            total += 3
        elif t >= 38.5:
            total += 1
        elif t >= 36:
            total += 0
        elif t >= 34:
            total += 1
        elif t >= 32:
            total += 2
        elif t >= 30:
            total += 3
        else:
            total += 4

    # Mean arterial pressure; calculate if absent
    mapv = num("Mean arterial pressure")
    if mapv is None:
        sbp = num("Systolic Blood Pressure")
        dbp = num("Diastolic Blood Pressure")
        if sbp is not None and dbp is not None:
            mapv = (sbp + 2.0 * dbp) / 3.0
    if mapv is not None:
        if mapv >= 160:
            total += 4
        elif mapv >= 130:
            total += 3
        elif mapv >= 110:
            total += 2
        elif mapv >= 70:
            total += 0
        elif mapv >= 50:
            total += 2
        else:
            total += 4

    # pH
    ph = num("pH")
    if ph is not None:
        if ph >= 7.70:
            total += 4
        elif ph >= 7.60:
            total += 3
        elif ph >= 7.50:
            total += 1
        elif ph >= 7.33:
            total += 0
        elif ph >= 7.25:
            total += 2
        elif ph >= 7.15:
            total += 3
        else:
            total += 4

    # Heart rate
    hr = num("Heart Rate or Pulse")
    if hr is not None:
        if hr >= 180:
            total += 4
        elif hr >= 140:
            total += 3
        elif hr >= 110:
            total += 2
        elif hr >= 70:
            total += 0
        elif hr >= 55:
            total += 2
        elif hr >= 40:
            total += 3
        else:
            total += 4

    # Respiratory rate
    rr = num("respiratory rate")
    if rr is not None:
        if rr >= 50:
            total += 4
        elif rr >= 35:
            total += 3
        elif rr >= 25:
            total += 1
        elif rr >= 12:
            total += 0
        elif rr >= 10:
            total += 1
        elif rr >= 6:
            total += 2
        else:
            total += 4

    # Oxygenation: if FiO2 >= 50%, use A-a gradient; otherwise PaO2
    fio2 = num("FiO2")
    if fio2 is not None and fio2 <= 1.0:
        fio2 = fio2 * 100.0
    if fio2 is not None and fio2 >= 50:
        aa = num("A-a gradient")
        if aa is not None:
            if aa >= 500:
                total += 4
            elif aa >= 350:
                total += 3
            elif aa >= 200:
                total += 2
            else:
                total += 0
    else:
        pao2 = num("PaO2")
        if pao2 is not None:
            if pao2 > 70:
                total += 0
            elif pao2 >= 61:
                total += 1
            elif pao2 >= 55:
                total += 3
            else:
                total += 4

    # Sodium
    na = num("Sodium")
    if na is not None:
        if na >= 180:
            total += 4
        elif na >= 160:
            total += 3
        elif na >= 155:
            total += 2
        elif na >= 150:
            total += 1
        elif na >= 130:
            total += 0
        elif na >= 120:
            total += 2
        elif na >= 111:
            total += 3
        else:
            total += 4

    # Potassium
    k = num("Potassium")
    if k is not None:
        if k >= 7.0:
            total += 4
        elif k >= 6.0:
            total += 3
        elif k >= 5.5:
            total += 1
        elif k >= 3.5:
            total += 0
        elif k >= 3.0:
            total += 1
        elif k >= 2.5:
            total += 2
        else:
            total += 4

    # Creatinine, double points for acute renal failure
    cr = num("creatinine")
    if cr is not None:
        cr_pts = 0
        if cr >= 3.5:
            cr_pts = 4
        elif cr >= 2.0:
            cr_pts = 3
        elif cr >= 1.5:
            cr_pts = 2
        elif cr >= 0.6:
            cr_pts = 0
        else:
            cr_pts = 2
        if yes("Acute renal failure"):
            cr_pts *= 2
        total += cr_pts

    # Hematocrit
    hct = num("Hematocrit")
    if hct is not None:
        if hct >= 60:
            total += 4
        elif hct >= 50:
            total += 2
        elif hct >= 46:
            total += 1
        elif hct >= 30:
            total += 0
        elif hct >= 20:
            total += 2
        else:
            total += 4

    # White blood cell count; convert absolute/mm3 to thousands/mm3 when large
    wbc = num("White blood cell count")
    if wbc is not None:
        if wbc > 1000:
            wbc = wbc / 1000.0
        if wbc >= 40:
            total += 4
        elif wbc >= 20:
            total += 2
        elif wbc >= 15:
            total += 1
        elif wbc >= 3:
            total += 0
        elif wbc >= 1:
            total += 2
        else:
            total += 4

    # Glasgow Coma Scale
    gcs = num("Glasgow Coma Score")
    if gcs is not None:
        total += max(0, int(round(15 - gcs)))

    # Chronic health points
    if yes("History of severe organ failure or immunocompromise"):
        st = str(val("Surgery Type", "")).strip().lower()
        if "elective" in st:
            total += 2
        else:
            total += 5

    return int(total)
