def calc(relevant):
    def get_bool(key):
        v = relevant.get(key, False)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            return v.strip().lower() in ('yes', 'true', '1', 'y', 'present', 'positive')
        return bool(v)

    def get_age():
        v = relevant.get('age', 0)
        if isinstance(v, (list, tuple)) and len(v) > 0:
            v = v[0]
        if isinstance(v, str):
            s = v.strip().lower()
            if '>=' in s or '≥' in s:
                nums = ''.join(ch if ch.isdigit() or ch == '.' else ' ' for ch in s).split()
                return float(nums[0]) if nums else 75.0
            nums = ''.join(ch if ch.isdigit() or ch == '.' else ' ' for ch in s).split()
            return float(nums[0]) if nums else 0.0
        try:
            return float(v)
        except Exception:
            return 0.0

    score = 0
    age = get_age()
    if age >= 75:
        score += 2
    elif age >= 65:
        score += 1

    sex = str(relevant.get('sex', '')).strip().lower()
    if sex == 'female' or sex == 'f':
        score += 1

    if get_bool('Congestive Heart Failure'):
        score += 1
    if get_bool('Hypertension history'):
        score += 1
    if get_bool('Diabetes history'):
        score += 1
    if get_bool('Vascular disease history'):
        score += 1

    if get_bool('Stroke') or get_bool('Transient Ischemic Attacks History') or get_bool('Thromboembolism history'):
        score += 2

    return int(score)
