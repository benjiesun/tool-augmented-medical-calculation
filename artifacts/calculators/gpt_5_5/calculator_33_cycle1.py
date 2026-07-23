def calc(relevant):
    def extract(v):
        while True:
            if isinstance(v, (list, tuple)):
                if len(v) == 0:
                    return None
                v = v[0]
                continue
            if isinstance(v, dict):
                for k in ('value', 'val', 'answer', 'result'):
                    if k in v:
                        v = v[k]
                        break
                else:
                    if len(v) == 1:
                        v = next(iter(v.values()))
                    else:
                        return v
                continue
            return v

    def is_yes(v):
        v = extract(v)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        if v is None:
            return False
        s = str(v).strip().lower()
        return s in ('yes', 'y', 'true', 't', '1')

    def norm_key(k):
        s = str(k).strip().lower()
        s = s.replace('≤', '<=')
        s = s.replace(' ', '')
        for ch in '_-:/.,;()[]{}"\'\n\r\t':
            s = s.replace(ch, '')
        return s

    if not isinstance(relevant, dict):
        return 0

    aliases = {
        'feverinpast24hours': 'fever',
        'absenceofcoughorcoryza': 'cough',
        'symptomonset<=3days': 'onset',
        'purulenttonsils': 'purulent',
        'severetonsilinflammation': 'severe',
    }

    seen = {'fever': False, 'cough': False, 'onset': False, 'purulent': False, 'severe': False}
    score = 0

    for k, v in relevant.items():
        nk = norm_key(k)
        canonical = aliases.get(nk)
        if canonical is not None and not seen[canonical]:
            if is_yes(v):
                score += 1
            seen[canonical] = True

    return int(score)
