def calc(relevant):
    def _norm(x):
        return ''.join(ch for ch in str(x).lower() if ch.isalnum())

    def _unwrap(v):
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return _unwrap(v[0])
        if isinstance(v, dict):
            for k, vv in v.items():
                nk = _norm(k)
                if nk in ('value', 'val', 'answer', 'result', 'data'):
                    return _unwrap(vv)
        return v

    def _find(obj, aliases, depth=0, max_depth=6):
        target = {_norm(a) for a in aliases}
        if depth > max_depth:
            return None, False
        if isinstance(obj, dict):
            for k, v in obj.items():
                if _norm(k) in target:
                    return v, True
            for v in obj.values():
                found, ok = _find(v, aliases, depth + 1, max_depth)
                if ok:
                    return found, True
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                found, ok = _find(item, aliases, depth + 1, max_depth)
                if ok:
                    return found, True
        return None, False

    def _parse_bool(v):
        v = _unwrap(v)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v != 0
        s = str(v).strip().lower()
        if s in ('true', 't', 'yes', 'y', '1', 'present', 'positive', 'pos', 'likely'):
            return True
        if s in ('false', 'f', 'no', 'n', '0', 'absent', 'negative', 'neg', 'unlikely'):
            return False
        return None

    def _parse_num(v):
        v = _unwrap(v)
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(',', '')
        try:
            return float(s)
        except Exception:
            num = ''
            started = False
            for ch in s:
                if ch.isdigit() or ch in '+-.':
                    num += ch
                    started = True
                elif started:
                    break
            try:
                return float(num) if num else None
            except Exception:
                return None

    if not isinstance(relevant, dict):
        return 'N/A'

    total = 0.0

    hr_v, ok = _find(relevant, ['Heart Rate or Pulse', 'Heart Rate', 'Pulse', 'HR', 'Tachycardia'])
    hr = _parse_num(hr_v) if ok else None
    if hr is not None and hr > 100:
        total += 1.5

    dvt_signs_v, ok = _find(relevant, ['Clinical signs and symptoms of Deep Vein Thrombosis', 'Clinical signs of DVT', 'Signs of Deep Vein Thrombosis', 'DVT signs'])
    dvt_signs = _parse_bool(dvt_signs_v) if ok else None
    if dvt_signs:
        total += 3.0

    pe_most_likely_v, ok = _find(relevant, ['Pulmonary Embolism is #1 diagnosis OR equally likely', 'PE is most likely', 'PE most likely', 'Pulmonary embolism most likely'])
    pe_most_likely = _parse_bool(pe_most_likely_v) if ok else None
    if pe_most_likely:
        total += 3.0

    imm_v, ok = _find(relevant, ['Immobilization for at least 3 days', 'Immobilization', 'Immobilised for at least 3 days', 'Immobilized for at least 3 days', 'Bedridden for at least 3 days'])
    surg_v, ok2 = _find(relevant, ['Surgery in the previous 4 weeks', 'Surgery within 4 weeks', 'Recent surgery'])
    imm = _parse_bool(imm_v) if ok else None
    surg = _parse_bool(surg_v) if ok2 else None
    if imm or surg:
        total += 1.5

    prev_pe_v, ok = _find(relevant, ['Previously Documented Pulmonary Embolism', 'Previous Pulmonary Embolism', 'Prior Pulmonary Embolism', 'History of Pulmonary Embolism'])
    prev_dvt_v, ok2 = _find(relevant, ['Previously documented Deep Vein Thrombosis', 'Previously Documented DVT', 'Previous Deep Vein Thrombosis', 'Prior Deep Vein Thrombosis', 'History of DVT'])
    prev_pe = _parse_bool(prev_pe_v) if ok else None
    prev_dvt = _parse_bool(prev_dvt_v) if ok2 else None
    if prev_pe or prev_dvt:
        total += 1.5

    hem_v, ok = _find(relevant, ['Hemoptysis', 'Hemoptysis present', 'Coughing blood'])
    hem = _parse_bool(hem_v) if ok else None
    if hem:
        total += 1.0

    mal_v, ok = _find(relevant, ['Malignancy with treatment within 6 months or palliative', 'Malignancy', 'Cancer', 'Active malignancy'])
    mal = _parse_bool(mal_v) if ok else None
    if mal:
        total += 1.0

    if float(total).is_integer():
        return int(total)
    return total
