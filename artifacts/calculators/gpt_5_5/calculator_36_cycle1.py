def calc(relevant):
    def num(v):
        if isinstance(v, (list, tuple)) and v:
            v = v[0]
        try:
            return float(v)
        except Exception:
            return None

    def is_true(v):
        if isinstance(v, (list, tuple)) and v:
            v = v[0]
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        if isinstance(v, (int, float)):
            return v != 0
        return str(v).strip().lower() in {'true', 't', 'yes', 'y', '1'}

    def text(v):
        if isinstance(v, (list, tuple)) and v:
            v = v[0]
        if v is None:
            return ''
        return str(v).strip().lower()

    score = 0

    age = num(relevant.get('age'))
    if age is not None:
        if age >= 75:
            score += 3
        elif age >= 61:
            score += 2
        elif age >= 41:
            score += 1

    bmi = num(relevant.get('Body Mass Index (BMI)'))
    if bmi is not None and bmi > 25:
        score += 1

    s = text(relevant.get('Surgery Type'))
    if 'elective major lower extremity arthroplasty' in s or 'arthroplasty' in s:
        score += 5
    elif 'major' in s or 'laparoscopic' in s or 'arthroscopic' in s:
        score += 2
    elif 'minor' in s:
        score += 1

    if is_true(relevant.get('Major Surgery in the last month')):
        score += 1
    if is_true(relevant.get('Congestive Heart Failure in the last month')):
        score += 1
    if is_true(relevant.get('Sepsis in the last month')):
        score += 1
    if is_true(relevant.get('Pneumonia in the last month')):
        score += 1
    if is_true(relevant.get('Immobilizing plaster cast in the last month')):
        score += 2
    if is_true(relevant.get('Hip, pelvis, or leg fracture in the last month')):
        score += 5
    if is_true(relevant.get('Stroke in the last month')):
        score += 5
    if is_true(relevant.get('Multiple trauma in the last month')):
        score += 5
    if is_true(relevant.get('Acute spinal cord injury causing paralysis in the last month')):
        score += 5
    if is_true(relevant.get('Acute Myocardial infarction')):
        score += 1

    m = text(relevant.get('Mobility'))
    if m:
        if 'out of bed' in m or m == 'normal':
            pass
        elif 'confined' in m or '>72' in m or '72 hours' in m or 'bedridden' in m:
            score += 2
        elif 'bed rest' in m:
            score += 1

    if is_true(relevant.get('Varicose veins')):
        score += 1
    if is_true(relevant.get('Current swollen legs')):
        score += 1
    if is_true(relevant.get('Current central venous access')):
        score += 2

    if is_true(relevant.get('Previously documented Deep Vein Thrombosis')):
        score += 3
    if is_true(relevant.get('Previously Documented Pulmonary Embolism')):
        score += 3
    if is_true(relevant.get('Family history of thrombosis')):
        score += 3
    if is_true(relevant.get('Positive lupus anticoagulant')):
        score += 3
    if is_true(relevant.get('Positive Factor V Leiden')):
        score += 3
    if is_true(relevant.get('Positive prothrombin 20210A')):
        score += 3
    if is_true(relevant.get('Elevated serum homocysteine')):
        score += 3
    if is_true(relevant.get('Elevated anticardiolipin antibody')):
        score += 3
    if is_true(relevant.get('Heparin-induced thrombocytopenia')):
        score += 3

    if is_true(relevant.get('Chronic Obstructive Pulmonary Disease')):
        score += 1
    if is_true(relevant.get('Present or previous malignancy')):
        score += 2
    if is_true(relevant.get('History of inflammatory bowel disease')):
        score += 1

    return int(score)
