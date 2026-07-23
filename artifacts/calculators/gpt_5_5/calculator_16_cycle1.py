def calc(relevant):
    def yes(v):
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        if isinstance(v, (int, float)):
            return v != 0
        return str(v).strip().lower() in ('yes', 'true', '1')

    score = 0.0
    if yes(relevant.get('Active cancer')):
        score += 1
    if yes(relevant.get('Bedridden recently >3 days')) or yes(relevant.get('Major surgery within 12 weeks')):
        score += 1
    if yes(relevant.get('Calf swelling >3 centimeters compared to the other leg')):
        score += 1
    if yes(relevant.get('Collateral (nonvaricose) superficial veins present')):
        score += 1
    if yes(relevant.get('Entire Leg Swollen')):
        score += 1
    if yes(relevant.get('Localized tenderness along the deep venous system')):
        score += 1
    if yes(relevant.get('Pitting edema, confined to symptomatic leg')):
        score += 1
    if yes(relevant.get('Paralysis, paresis, or recent plaster immobilization of the lower extremity')):
        score += 1
    if yes(relevant.get('Previously documented Deep Vein Thrombosis')):
        score += 1
    if yes(relevant.get('Alternative diagnosis to Deep Vein Thrombosis as likely or more likely')):
        score -= 2
    return float(score)
