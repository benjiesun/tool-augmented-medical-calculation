def calc(relevant):
    def norm_key(k):
        return ''.join(ch.lower() for ch in str(k) if ch.isalnum())

    def first_num_from_text(s):
        if s is None:
            return None
        if isinstance(s, bool):
            return 1.0 if s else 0.0
        if isinstance(s, (int, float)):
            return float(s)
        s = str(s).strip()
        if not s:
            return None
        try:
            return float(s)
        except:
            pass
        for sep in [',', ';', '/', '(', ')', '[', ']', '{', '}', ':']:
            s = s.replace(sep, ' ')
        for raw in s.split():
            token = ''.join(ch for ch in raw if ch.isdigit() or ch in '+-.eE')
            if token and any(c.isdigit() for c in token):
                try:
                    return float(token)
                except:
                    pass
        return None

    def extract(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, (list, tuple)):
            for item in v:
                num = extract(item)
                if num is not None:
                    return num
            return None
        if isinstance(v, dict):
            for key in ('value', 'val', 'number', 'amount', 'qty', 'result', 'text', 'data'):
                if key in v:
                    num = extract(v[key])
                    if num is not None:
                        return num
            for item in v.values():
                num = extract(item)
                if num is not None:
                    return num
            return None
        return first_num_from_text(v)

    def find_input(d, wanted):
        if not isinstance(d, dict):
            return None
        wanted_norm = [norm_key(w) for w in wanted]
        for k, v in d.items():
            nk = norm_key(k)
            if nk in wanted_norm:
                num = extract(v)
                if num is not None:
                    return num
        for k, v in d.items():
            nk = norm_key(k)
            for w in wanted_norm:
                if w and (w in nk or nk in w):
                    num = extract(v)
                    if num is not None:
                        return num
        for v in d.values():
            if isinstance(v, dict):
                num = find_input(v, wanted)
                if num is not None:
                    return num
        return None

    hr = find_input(relevant, ['Heart Rate or Pulse', 'Heart Rate', 'Pulse', 'HR', 'Heartrate', 'Pulserate'])
    qt = find_input(relevant, ['QT Interval', 'QT', 'QTinterval'])
    if hr is None or qt is None:
        return 'N/A'
    try:
        hr = float(hr)
        qt = float(qt)
        if hr <= 0 or qt <= 0:
            return 'N/A'
        return qt * ((hr / 60.0) ** 0.5)
    except:
        return 'N/A'
