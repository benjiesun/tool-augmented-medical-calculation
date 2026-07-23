def calc(relevant):
    def unwrap(x):
        if isinstance(x, dict):
            for k in ('value', 'val', 'amount', 'dose'):
                if k in x:
                    return x[k]
            return None
        if isinstance(x, (list, tuple)) and len(x) > 0:
            return x[0]
        return x

    def get(*names):
        if not isinstance(relevant, dict):
            return None
        for name in names:
            if name in relevant and relevant[name] is not None:
                return relevant[name]
        for k in relevant:
            kl = str(k).lower().replace('_', ' ').strip()
            for name in names:
                nl = str(name).lower().replace('_', ' ').strip()
                if kl == nl:
                    return relevant[k]
        for k in relevant:
            kl = str(k).lower().replace('_', ' ').strip()
            for name in names:
                nl = str(name).lower().replace('_', ' ').strip()
                if nl in kl or kl in nl:
                    return relevant[k]
        return None

    def to_float(x):
        x = unwrap(x)
        if x is None:
            return None
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            s = x.strip().replace(',', '')
            num = ''
            seen = False
            for i, ch in enumerate(s):
                if ch.isdigit() or ch == '.' or (ch == '-' and not seen):
                    num += ch
                    seen = True
                elif seen:
                    break
            try:
                if num not in ('', '-', '.'):
                    return float(num)
            except Exception:
                return None
        return None

    def to_bool(x):
        x = unwrap(x)
        if isinstance(x, bool):
            return x
        if x is None:
            return False
        if isinstance(x, (int, float)):
            return x != 0
        if isinstance(x, str):
            s = x.strip().lower()
            if s in ('yes', 'y', 'true', 't', '1', 'on'):
                return True
            if 'cpap' in s or 'vent' in s or 'mechanical' in s:
                if 'no' not in s and 'not' not in s and 'non' not in s:
                    return True
            if s in ('no', 'n', 'false', 'f', '0', 'off', 'none'):
                return False
        return False

    def text(x):
        x = unwrap(x)
        return str(x).strip().lower() if x is not None else ''

    total = 0

    pao2 = to_float(get('PaO2', 'PaO₂', 'arterial oxygen'))
    fio2 = to_float(get('FiO2', 'FiO₂'))
    resp = 0
    if pao2 is not None and fio2 is not None and fio2 > 0:
        if fio2 > 1:
            fio2 = fio2 / 100.0
        pf = pao2 / fio2
        vent = to_bool(get('On mechanical ventilation', 'mechanical ventilation', 'ventilated')) or to_bool(get('Continuous positive airway pressure', 'CPAP'))
        if pf >= 400:
            resp = 0
        elif pf >= 300:
            resp = 1
        elif pf >= 200:
            resp = 2
        else:
            if vent:
                resp = 4 if pf < 100 else 3
            else:
                resp = 2
    total += resp

    pltx = get('Platelet count', 'Platelets', 'platelet')
    plts = to_float(pltx)
    plt_score = 0
    ts = text(pltx)
    if '<20' in ts or 'less than 20' in ts:
        plt_score = 4
    elif '20-49' in ts or '20–49' in ts:
        plt_score = 3
    elif '50-99' in ts or '50–99' in ts:
        plt_score = 2
    elif '100-149' in ts or '100–149' in ts:
        plt_score = 1
    elif plts is not None:
        if plts > 1000:
            plts = plts / 1000.0
        if plts < 20:
            plt_score = 4
        elif plts < 50:
            plt_score = 3
        elif plts < 100:
            plt_score = 2
        elif plts < 150:
            plt_score = 1
        else:
            plt_score = 0
    total += plt_score

    gcsx = get('Glasgow Coma Score', 'Glasgow Coma Scale', 'GCS')
    gcs = to_float(gcsx)
    gcs_score = 0
    gs = text(gcsx)
    if '<6' in gs or 'less than 6' in gs:
        gcs_score = 4
    elif '6-9' in gs or '6–9' in gs:
        gcs_score = 3
    elif '10-12' in gs or '10–12' in gs:
        gcs_score = 2
    elif '13-14' in gs or '13–14' in gs:
        gcs_score = 1
    elif gcs is not None:
        if gcs < 6:
            gcs_score = 4
        elif gcs <= 9:
            gcs_score = 3
        elif gcs <= 12:
            gcs_score = 2
        elif gcs <= 14:
            gcs_score = 1
        else:
            gcs_score = 0
    total += gcs_score

    bilix = get('Bilirubin', 'bilirubin')
    bili = to_float(bilix)
    bili_score = 0
    bs = text(bilix)
    if '>=12' in bs or '≥12' in bs or '>12' in bs:
        bili_score = 4
    elif '6.0' in bs and '11.9' in bs:
        bili_score = 3
    elif '2.0' in bs and '5.9' in bs:
        bili_score = 2
    elif '1.2' in bs and '1.9' in bs:
        bili_score = 1
    elif bili is not None:
        if bili >= 12:
            bili_score = 4
        elif bili >= 6:
            bili_score = 3
        elif bili >= 2:
            bili_score = 2
        elif bili >= 1.2:
            bili_score = 1
        else:
            bili_score = 0
    total += bili_score

    cv_score = 0
    cvtext = text(get('Mean arterial pressure OR administration of vasoactive agents required', 'vasoactive agents', 'hypotension category'))
    if 'dopamine >15' in cvtext or 'epinephrine >0.1' in cvtext or 'norepinephrine >0.1' in cvtext:
        cv_score = 4
    elif 'dopamine >5' in cvtext or 'epinephrine' in cvtext or 'norepinephrine' in cvtext:
        cv_score = max(cv_score, 3)
    elif 'dopamine' in cvtext or 'dobutamine' in cvtext:
        cv_score = max(cv_score, 2)
    dopa = to_float(get('DOPamine', 'dopamine'))
    dobu = to_float(get('DOBUTamine', 'dobutamine'))
    epi = to_float(get('EPINEPHrine', 'epinephrine'))
    norepi = to_float(get('norEPINEPHrine', 'norepinephrine', 'noradrenaline'))
    if dopa is not None and dopa > 0:
        if dopa > 15:
            cv_score = max(cv_score, 4)
        elif dopa > 5:
            cv_score = max(cv_score, 3)
        else:
            cv_score = max(cv_score, 2)
    if dobu is not None and dobu > 0:
        cv_score = max(cv_score, 2)
    if epi is not None and epi > 0:
        cv_score = max(cv_score, 4 if epi > 0.1 else 3)
    if norepi is not None and norepi > 0:
        cv_score = max(cv_score, 4 if norepi > 0.1 else 3)
    if cv_score == 0:
        mapv = to_float(get('Mean arterial pressure', 'MAP'))
        sbp = to_float(get('Systolic Blood Pressure', 'SBP'))
        dbp = to_float(get('Diastolic Blood Pressure', 'DBP'))
        if mapv is None and sbp is not None and dbp is not None:
            mapv = (sbp + 2.0 * dbp) / 3.0
        if (mapv is not None and mapv < 70) or to_bool(get('Hypotension')) or 'map <70' in cvtext:
            cv_score = 1
    total += cv_score

    crx = get('creatinine', 'Creatinine')
    cr = to_float(crx)
    renal_score = 0
    rs = text(crx)
    if '>=5' in rs or '≥5' in rs or '>5' in rs:
        renal_score = 4
    elif '3.5' in rs and '4.9' in rs:
        renal_score = 3
    elif '2.0' in rs and '3.4' in rs:
        renal_score = 2
    elif '1.2' in rs and '1.9' in rs:
        renal_score = 1
    elif cr is not None:
        if cr >= 5:
            renal_score = 4
        elif cr >= 3.5:
            renal_score = 3
        elif cr >= 2:
            renal_score = 2
        elif cr >= 1.2:
            renal_score = 1
        else:
            renal_score = 0
    uop = to_float(get('Urine Output', 'UOP', 'urine output'))
    if uop is not None:
        if uop < 200:
            renal_score = max(renal_score, 4)
        elif uop < 500:
            renal_score = max(renal_score, 3)
    total += renal_score

    return int(total)
