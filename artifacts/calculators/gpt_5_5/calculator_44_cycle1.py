def calc(relevant):
    def clean_key(x):
        s = str(x).lower()
        out = ''
        for ch in s:
            if ch.isalnum():
                out += ch
        return out

    def unwrap(v):
        unit = ''
        val = v
        if isinstance(v, dict):
            for k in v:
                ck = clean_key(k)
                if ck in ['unit', 'units']:
                    unit = v[k]
                if ck in ['value', 'val', 'result', 'answer']:
                    val = v[k]
        elif isinstance(v, (list, tuple)):
            if len(v) > 0:
                val = v[0]
            if len(v) > 1:
                unit = v[1]
        return val, unit

    def to_num(x):
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == '':
            return None
        t = ''
        started = False
        dot = False
        for ch in s:
            if ch.isdigit():
                t += ch
                started = True
            elif ch in ['-', '+'] and not started and t == '':
                t += ch
            elif ch == '.' and not dot:
                t += ch
                dot = True
                started = True
            elif ch == ',' and started:
                continue
            elif started:
                break
        try:
            return float(t)
        except Exception:
            return None

    def find(aliases, kind):
        if not isinstance(relevant, dict):
            return None
        alias_clean = [clean_key(a) for a in aliases]
        best = None
        for k, v in relevant.items():
            ck = clean_key(k)
            match = False
            for a in alias_clean:
                if ck == a or a in ck or ck in a:
                    match = True
                    break
            if match:
                best = v
                break
        if best is None:
            return None
        val, unit = unwrap(best)
        num = to_num(val)
        if num is None:
            return None
        u = str(unit).lower()
        if 'mmol' in u:
            if kind == 'tg':
                num = num * 88.57
            else:
                num = num * 38.67
        return num

    total = find(['total cholesterol', 'cholesterol total', 'totalcholesterol', 'tc'], 'chol')
    hdl = find(['high density lipoprotein cholesterol', 'high-density lipoprotein cholesterol', 'hdl cholesterol', 'hdl-c', 'hdlc', 'hdl'], 'chol')
    tg = find(['triglycerides', 'triglyceride', 'trig', 'tg', 'triacylglycerol'], 'tg')

    if total is None or hdl is None or tg is None:
        return 'N/A'
    return total - hdl - (tg / 5.0)
