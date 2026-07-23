def calc(relevant):
    def norm(x):
        return ''.join(ch for ch in str(x).lower() if ch.isalnum())

    def first_num(x):
        if isinstance(x, bool) or x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, (list, tuple)):
            for v in x:
                n = first_num(v)
                if n is not None:
                    return n
            return None
        if isinstance(x, dict):
            for k in ('value', 'dose', 'amount', 'mg', 'number'):
                if k in x:
                    n = first_num(x[k])
                    if n is not None:
                        return n
            for v in x.values():
                n = first_num(v)
                if n is not None:
                    return n
            return None
        s = str(x).replace(',', ' ')
        i, n = 0, len(s)
        while i < n:
            c = s[i]
            if c.isdigit() or (c in '+-' and i + 1 < n and (s[i + 1].isdigit() or s[i + 1] == '.')) or (c == '.' and i + 1 < n and s[i + 1].isdigit()):
                j = i + 1
                seen_digit = c.isdigit()
                seen_dot = (c == '.')
                seen_exp = False
                while j < n:
                    d = s[j]
                    if d.isdigit():
                        seen_digit = True
                        j += 1
                    elif d == '.' and not seen_dot and not seen_exp:
                        seen_dot = True
                        j += 1
                    elif d in 'eE' and seen_digit and not seen_exp:
                        seen_exp = True
                        j += 1
                        if j < n and s[j] in '+-':
                            j += 1
                        k = j
                        while j < n and s[j].isdigit():
                            j += 1
                        if k == j:
                            break
                    else:
                        break
                try:
                    return float(s[i:j])
                except:
                    pass
            i += 1
        return None

    def find_key(obj, wanted):
        wn = norm(wanted)
        if isinstance(obj, dict):
            for k, v in obj.items():
                if norm(k) == wn:
                    return v
            for v in obj.values():
                r = find_key(v, wanted)
                if r is not None:
                    return r
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                r = find_key(v, wanted)
                if r is not None:
                    return r
        return None

    steroids = [
        ('betamethasone', 0.75),
        ('cortisone', 25.0),
        ('dexamethasone', 0.75),
        ('hydrocortisone', 20.0),
        ('methylprednisolone', 4.0),
        ('prednisolone', 5.0),
        ('prednisone', 5.0),
        ('triamcinolone', 4.0),
    ]

    def steroid_name(x):
        if x is None:
            return None
        if isinstance(x, dict):
            for k in ('steroid', 'name', 'drug', 'medication', 'input steroid', 'target steroid'):
                if k in x:
                    s = steroid_name(x[k])
                    if s:
                        return s
            for v in x.values():
                s = steroid_name(v)
                if s:
                    return s
            return None
        if isinstance(x, (list, tuple)):
            for v in x:
                s = steroid_name(v)
                if s:
                    return s
            return None
        t = norm(x)
        for s, _ in steroids:
            if norm(s) in t:
                return s
        return None

    inp = find_key(relevant, 'input steroid')
    tgt = find_key(relevant, 'target steroid')
    inp_name = steroid_name(inp)
    tgt_name = steroid_name(tgt)
    dose = first_num(inp)
    if inp_name is None or tgt_name is None or dose is None:
        return 'N/A'

    eq = {}
    for s, v in steroids:
        eq[s] = v
    if inp_name not in eq or tgt_name not in eq:
        return 'N/A'
    return float(dose) * eq[tgt_name] / eq[inp_name]
