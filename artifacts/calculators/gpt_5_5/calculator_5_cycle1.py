def calc(relevant):
    def to_number(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return float(x)
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            s = x.strip()
            if not s:
                return None
            try:
                return float(s)
            except Exception:
                return None
        return None

    def extract_value(v):
        if isinstance(v, dict):
            for key in ('value', 'val', 'amount', 'number', 'text'):
                if key in v:
                    num = extract_value(v[key])
                    if num is not None:
                        return num
            for item in v.values():
                num = extract_value(item)
                if num is not None:
                    return num
            return None
        if isinstance(v, (list, tuple)):
            for item in v:
                num = extract_value(item)
                if num is not None:
                    return num
            return None
        return to_number(v)

    if not isinstance(relevant, dict):
        return 'N/A'

    sbp = None
    dbp = None
    for k, v in relevant.items():
        key = str(k).strip().lower()
        if key == 'systolic blood pressure':
            sbp = extract_value(v)
        elif key == 'diastolic blood pressure':
            dbp = extract_value(v)

    if sbp is None or dbp is None:
        return 'N/A'

    return (sbp + 2.0 * dbp) / 3.0
