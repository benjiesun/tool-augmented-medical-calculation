def calc(relevant):
    def _scalar(v):
        while True:
            if isinstance(v, dict):
                for k in ('value', 'text', 'label', 'name', 'answer', 'response', 'best', 'data'):
                    if k in v:
                        v = v[k]
                        break
                else:
                    if len(v) == 0:
                        return ''
                    v = next(iter(v.values()))
                continue
            if isinstance(v, (list, tuple)):
                if not v:
                    return ''
                v = v[0]
                continue
            return v

    def _norm(v):
        v = _scalar(v)
        if v is None:
            return ''
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if int(v) == v:
                return str(int(v))
            return str(v).strip().lower()
        s = str(v).strip().lower()
        for ch in '_-/,;:()[]{}.|':
            s = s.replace(ch, ' ')
        return ' '.join(s.split())

    def _find(keys):
        if not isinstance(relevant, dict):
            return None
        aliases = [_norm(k) for k in keys]
        def walk(obj):
            if isinstance(obj, dict):
                for k, val in obj.items():
                    nk = _norm(k)
                    for a in aliases:
                        if nk == a or nk in a or a in nk:
                            return val
                for val in obj.values():
                    found = walk(val)
                    if found is not None:
                        return found
            elif isinstance(obj, (list, tuple)):
                for val in obj:
                    found = walk(val)
                    if found is not None:
                        return found
            return None
        return walk(relevant)

    def _score_eye(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            n = int(v)
            return n if 1 <= n <= 4 else None
        s = _norm(v)
        if not s:
            return None
        if 'not testable' in s or s == 'nt' or 'unable to assess' in s:
            return None
        if 'no eye opening' in s or ('no' in s and 'eye' in s and ('open' in s or 'opening' in s)):
            return 1
        if 'pain' in s:
            return 2
        if 'verbal command' in s or ('verbal' in s and 'command' in s) or 'to speech' in s:
            return 3
        if 'spontan' in s:
            return 4
        return None

    def _score_verbal(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            n = int(v)
            return n if 1 <= n <= 5 else None
        s = _norm(v)
        if not s:
            return None
        if 'not testable' in s or 'intubated' in s or s == 'nt' or 'unable to assess' in s:
            return None
        if 'disoriented' in s:
            return None
        if 'oriented' in s:
            return 5
        if 'confused' in s:
            return 4
        if 'inappropriate words' in s or ('inappropriate' in s and 'words' in s):
            return 3
        if 'incomprehensible sounds' in s or ('incomprehensible' in s and 'sounds' in s):
            return 2
        if 'no verbal response' in s or ('no' in s and 'verbal' in s and 'response' in s):
            return 1
        return None

    def _score_motor(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            n = int(v)
            return n if 1 <= n <= 6 else None
        s = _norm(v)
        if not s:
            return None
        if 'not testable' in s or s == 'nt' or 'unable to assess' in s:
            return None
        if 'obeys commands' in s or 'obeys command' in s or ('obeys' in s and 'command' in s):
            return 6
        if 'localizes pain' in s or 'localises pain' in s or ('localiz' in s and 'pain' in s):
            return 5
        if 'withdrawal from pain' in s or ('withdraw' in s and 'pain' in s):
            return 4
        if 'flexion to pain' in s or ('flexion' in s and 'pain' in s):
            return 3
        if 'extension to pain' in s or ('extension' in s and 'pain' in s):
            return 2
        if 'no motor response' in s or ('no' in s and 'motor' in s and 'response' in s):
            return 1
        return None

    eye = _score_eye(_find(('Best eye response', 'Eye response', 'eye opening')))
    verbal = _score_verbal(_find(('Best verbal response', 'Verbal response', 'verbal')))
    motor = _score_motor(_find(('Best motor response', 'Motor response', 'motor')))

    if eye is None or verbal is None or motor is None:
        return None
    return int(eye + verbal + motor)
