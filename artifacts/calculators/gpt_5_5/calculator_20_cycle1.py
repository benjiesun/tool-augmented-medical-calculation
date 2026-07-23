def calc(relevant):
    def get_value(x):
        if isinstance(x, (list, tuple)) and len(x) > 0:
            return x[0]
        return x

    def is_yes(x):
        return bool(x) is True

    score = 0

    age = get_value(relevant.get('age'))
    try:
        age = float(age)
    except Exception:
        age = None

    if age is not None:
        if 3 <= age <= 14:
            score += 1
        elif age >= 45:
            score -= 1

    if is_yes(relevant.get('Exudate or swelling on tonsils')):
        score += 1

    if is_yes(relevant.get('Tender/swollen anterior cervical lymph nodes')):
        score += 1

    temp = get_value(relevant.get('Temperature'))
    temp_unit = None
    if isinstance(relevant.get('Temperature'), (list, tuple)) and len(relevant.get('Temperature')) > 1:
        temp_unit = str(relevant.get('Temperature')[1]).lower()
    try:
        temp = float(temp)
    except Exception:
        temp = None

    if temp is not None:
        if temp_unit and 'c' in temp_unit:
            if temp > 38.0:
                score += 1
        elif temp_unit and 'f' in temp_unit:
            if temp > 100.4:
                score += 1
        else:
            if temp > 38.0:
                score += 1

    cough_absent = relevant.get('Cough Absent')
    if is_yes(cough_absent):
        score += 1

    return int(score)
