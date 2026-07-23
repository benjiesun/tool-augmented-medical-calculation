def calc(relevant):
    def parse_text(v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v)

    def parse_number(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, (list, tuple)):
            for item in v:
                n = parse_number(item)
                if n is not None:
                    return n
            return None
        if isinstance(v, dict):
            for key in ('value', 'val', 'amount', 'number', 'reading', 'result'):
                if key in v:
                    n = parse_number(v.get(key))
                    if n is not None:
                        return n
            for item in v.values():
                n = parse_number(item)
                if n is not None:
                    return n
            return None
        s = parse_text(v)
        if s is None:
            return None
        s = s.replace(',', '').strip()
        try:
            return float(s)
        except Exception:
            return None

    def parse_quantity(v):
        if v is None:
            return (None, None)
        if isinstance(v, bool):
            return (1.0 if v else 0.0, None)
        if isinstance(v, (int, float)):
            return (float(v), None)
        if isinstance(v, (list, tuple)):
            if len(v) == 2:
                n = parse_number(v[0])
                if n is not None:
                    return (n, parse_text(v[1]))
            for item in v:
                n, u = parse_quantity(item)
                if n is not None:
                    return (n, u)
            return (None, None)
        if isinstance(v, dict):
            unit = None
            for key in ('unit', 'units', 'uom', 'measure'):
                if key in v:
                    unit = parse_text(v.get(key))
                    if unit:
                        break
            for key in ('value', 'val', 'amount', 'number', 'reading', 'result'):
                if key in v:
                    n, u = parse_quantity(v.get(key))
                    if n is not None:
                        if not unit:
                            unit = u
                        return (n, unit)
            for item in v.values():
                n, u = parse_quantity(item)
                if n is not None:
                    if not unit:
                        unit = u
                    return (n, unit)
            return (None, None)
        s = parse_text(v)
        if s is None:
            return (None, None)
        s = s.replace(',', '').strip()
        try:
            return (float(s), None)
        except Exception:
            parts = s.split()
            if len(parts) >= 2:
                n = parse_number(parts[0])
                if n is not None:
                    return (n, ' '.join(parts[1:]))
            return (None, s)

    def get_val(data, names):
        if not isinstance(data, dict):
            return None
        lower_map = {}
        for k, v in data.items():
            if isinstance(k, str):
                lower_map[k.strip().lower()] = v
        for name in names:
            v = lower_map.get(name.lower())
            if v is not None:
                n = parse_number(v)
                if n is not None:
                    return n
        return None

    def get_val_and_unit(data, names):
        if not isinstance(data, dict):
            return (None, None)
        lower_map = {}
        for k, v in data.items():
            if isinstance(k, str):
                lower_map[k.strip().lower()] = v
        for name in names:
            v = lower_map.get(name.lower())
            if v is not None:
                n, u = parse_quantity(v)
                if n is not None:
                    return (n, u)
        return (None, None)

    sodium = get_val(relevant, ('sodium', 'na', 'na+', 'sod'))
    chloride = get_val(relevant, ('chloride', 'cl', 'cl-'))
    bicarbonate = get_val(relevant, ('bicarbonate', 'hco3', 'hco3-', 'co2', 'total co2', 'tco2'))
    albumin, albumin_unit = get_val_and_unit(relevant, ('albumin', 'alb'))

    if sodium is None or chloride is None or bicarbonate is None or albumin is None:
        return None

    if albumin_unit is not None:
        u = albumin_unit.strip().lower().replace(' ', '')
        if 'g/l' in u or 'gperl' in u or 'gram/l' in u or 'grams/l' in u:
            albumin = albumin / 10.0
    elif albumin > 10:
        albumin = albumin / 10.0

    anion_gap = sodium - (chloride + bicarbonate)
    corrected_anion_gap = anion_gap + (2.5 * (4.0 - albumin))
    return float(corrected_anion_gap)
