def calc(relevant):
    def norm_key(k):
        return ''.join(ch.lower() for ch in str(k) if ch.isalnum())

    def unwrap(v):
        if isinstance(v, dict):
            for kk in ('value', 'val', 'number', 'num', 'text', 'raw'):
                for k, x in v.items():
                    if norm_key(k) == norm_key(kk):
                        return unwrap(x)
            if len(v) == 1:
                return unwrap(next(iter(v.values())))
        if isinstance(v, (list, tuple)) and v:
            return unwrap(v[0])
        return v

    def parse_number(v):
        v = unwrap(v)
        if v is None or isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return None
        try:
            return float(s)
        except:
            pass
        s = s.replace(',', '')
        token = ''
        started = False
        for ch in s:
            if not started:
                if ch in '+-0123456789.':
                    started = True
                    token += ch
            else:
                if ch in '0123456789.eE+-':
                    token += ch
                else:
                    break
        if token in ('', '+', '-', '.', '+.', '-.'):
            return None
        try:
            return float(token)
        except:
            return None

    def parse_text(v):
        v = unwrap(v)
        if v is None:
            return None
        return str(v).strip().lower()

    def parse_sex(v):
        s = parse_text(v)
        if s is None:
            return None
        if s in ('female', 'f', 'woman', 'girl'):
            return 'female'
        if s in ('male', 'm', 'man', 'boy'):
            return 'male'
        return None

    def parse_bool(v):
        s = parse_text(v)
        if s is None:
            return None
        if s in ('1', 'true', 't', 'yes', 'y', 'black', 'african american', 'africanamerican', 'afroamerican'):
            return True
        if s in ('0', 'false', 'f', 'no', 'n', 'nonblack', 'non-black', 'not black', 'white', 'other'):
            return False
        return None

    def get_value(d, aliases):
        if not isinstance(d, dict):
            return None
        want = {norm_key(a) for a in aliases}
        for k, v in d.items():
            if norm_key(k) in want:
                return v
        return None

    def parse_creatinine(v):
        unit = None
        if isinstance(v, dict):
            val = None
            for k, x in v.items():
                nk = norm_key(k)
                if nk in ('value', 'val', 'number', 'num', 'text', 'raw'):
                    val = x
                elif nk in ('unit', 'units', 'u'):
                    unit = x
            if val is None and len(v) == 1:
                val = next(iter(v.values()))
        elif isinstance(v, (list, tuple)) and v:
            val = v[0]
            if len(v) > 1:
                unit = v[1]
        else:
            val = v
        num = parse_number(val)
        if num is None:
            return None
        u = parse_text(unit)
        if u:
            if ('umol' in u) or ('µmol' in u) or ('micromol' in u) or ('micromole' in u):
                num = num / 88.4
        else:
            if num > 20:
                num = num / 88.4
        return num

    age = parse_number(get_value(relevant, ('age', 'patient age', 'years')))
    creatinine = parse_creatinine(get_value(relevant, ('creatinine', 'creat', 'scr', 'serum creatinine', 'serumcr')))
    sex = parse_sex(get_value(relevant, ('sex', 'gender')))
    race_raw = get_value(relevant, ('race', 'black', 'african american', 'africanamerican'))
    black = parse_bool(race_raw)

    if age is None or creatinine is None or sex is None:
        return 'N/A'
    if age <= 0 or creatinine <= 0:
        return 'N/A'

    gfr = 175.0 * (creatinine ** -1.154) * (age ** -0.203)
    if black:
        gfr *= 1.212
    if sex == 'female':
        gfr *= 0.742
    return gfr
