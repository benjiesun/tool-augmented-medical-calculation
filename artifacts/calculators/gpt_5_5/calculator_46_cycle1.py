def calc(relevant):
    def nrm(s):
        return ''.join(ch for ch in str(s).lower() if ch.isalnum())

    def scalar(x):
        while isinstance(x, (list, tuple)) and x:
            x = x[0]
        if isinstance(x, dict):
            for k in ('value', 'amount', 'val', 'data', 'result'):
                if k in x:
                    return scalar(x[k])
            if len(x) == 1:
                return scalar(next(iter(x.values())))
        return x

    def find(d, key):
        if isinstance(d, dict):
            nk = nrm(key)
            for k in d:
                if nrm(k) == nk:
                    return scalar(d[k])
            aliases = {
                'highdensitylipoproteincholesterol': ('hdl', 'hdlcholesterol', 'high density lipoprotein cholesterol'),
                'systolicbloodpressure': ('sbp', 'systolicbp'),
                'bloodpressurebeingtreatedwithmedicines': ('treated', 'treatment for blood pressure', 'bp treated'),
                'totalcholesterol': ('cholesterol', 'tc'),
                'smoker': ('smoking', 'smokes'),
                'sex': ('gender',),
                'age': ('years',)
            }
            for a in aliases.get(nk, ()):
                na = nrm(a)
                for k in d:
                    if nrm(k) == na:
                        return scalar(d[k])
        return scalar(d)

    def num(x):
        return float(scalar(x))

    def boo(x):
        x = scalar(x)
        if isinstance(x, bool):
            return x
        if isinstance(x, (int, float)):
            return x != 0
        return str(x).strip().lower() in ('yes', 'y', 'true', 't', '1')

    def ln(x):
        x = float(x)
        if x <= 0.0:
            return float('nan')
        h = x.hex()
        p = h.rfind('p')
        e = int(h[p + 1:])
        m = float.fromhex(h[:p] + 'p+0')
        z = (m - 1.0) / (m + 1.0)
        z2 = z * z
        term = z
        s = 0.0
        n = 1.0
        for _ in range(30):
            s += term / n
            term *= z2
            n += 2.0
        return 2.0 * s + e * 0.6931471805599453

    age = num(find(relevant, 'age'))
    sex = str(scalar(find(relevant, 'sex'))).strip().lower()
    smoker = 1 if boo(find(relevant, 'Smoker')) else 0
    tc = num(find(relevant, 'Total cholesterol'))
    hdl = num(find(relevant, 'high-density lipoprotein cholesterol'))
    sbp = num(find(relevant, 'Systolic Blood Pressure'))
    treated = 1 if boo(find(relevant, 'Blood pressure being treated with medicines')) else 0

    la = ln(age)
    ltc = ln(tc)
    lhdl = ln(hdl)
    lsbp = ln(sbp)

    if sex.startswith('m'):
        las = ln(70.0 if age > 70.0 else age)
        L = 52.00961 * la + 20.014077 * ltc - 0.905964 * lhdl + 1.305784 * lsbp + 0.241549 * treated + 12.096316 * smoker - 4.605038 * la * ltc - 2.84367 * las * smoker - 2.93323 * la * la - 172.300168
        r = 1.0 - (0.9402 ** (2.718281828459045 ** L))
    else:
        las = ln(78.0 if age > 78.0 else age)
        L = 31.764001 * la + 22.465206 * ltc - 1.187731 * lhdl + 2.552905 * lsbp + 0.420251 * treated + 13.07543 * smoker - 5.060998 * la * ltc - 2.996945 * las * smoker - 146.5933061
        r = 1.0 - (0.98767 ** (2.718281828459045 ** L))

    if r < 0.0:
        r = 0.0
    if r > 1.0:
        r = 1.0
    return r * 100.0
