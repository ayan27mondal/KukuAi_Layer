"""Structured fact extraction (LLM with JSON output, or the offline mock) + follow-up question logic."""

PROBLEM_TYPES = ["deposit", "consumer", "salary", "other", "unknown"]

# Fields we must know (or have asked about twice) before giving a "where you stand" answer.
REQUIRED = {
    "deposit":  ["state", "other_party_name", "amount_inr", "event_date", "agreement"],
    "consumer": ["state", "other_party_name", "amount_inr", "event_date"],
    "salary":   ["state", "other_party_name", "amount_inr", "event_date"],
    "civil":    ["state", "other_party_name", "amount_inr", "event_date"],
    # "family": nothing is collected - we only give general information and send the person to a family lawyer
}

QUESTIONS = {
    "problem_type": {
        "en": "Could you tell me a little more about your problem? (For example: a deposit a landlord won't return, a refund or defective product, or unpaid salary.)",
        "hi": "क्या आप अपनी समस्या थोड़ा और बता सकते हैं? (जैसे: मकान मालिक डिपॉज़िट नहीं लौटा रहा, रिफ़ंड या ख़राब सामान, या वेतन नहीं मिला।)",
        "hinglish": "Kya aap apni problem thoda aur bata sakte hain? (Jaise: landlord deposit wapas nahi kar raha, refund ya kharab product, ya salary nahi mili.)"},
    "state": {
        "en": "Which state are you in? (Rules can differ by state.)",
        "hi": "आप किस राज्य में हैं? (नियम राज्य के हिसाब से अलग हो सकते हैं।)",
        "hinglish": "Aap kis state mein hain? (Rules state ke hisaab se alag ho sakte hain.)"},
    "other_party_name": {
        "en": "Who is the other side? (Landlord's name, company / seller name, or employer's name.)",
        "hi": "दूसरा पक्ष कौन है? (मकान मालिक का नाम, कंपनी / विक्रेता या नियोक्ता का नाम।)",
        "hinglish": "Doosri taraf kaun hai? (Landlord ka naam, company / seller ya employer ka naam.)"},
    "amount_inr": {
        "en": "How much money is involved (in rupees)?",
        "hi": "कितनी रकम का मामला है (रुपयों में)?",
        "hinglish": "Kitne paise ka matter hai (rupees mein)?"},
    "event_date": {
        "en": "Roughly when did this happen? (Date you vacated / bought the item / last got salary. An approximate month is fine.)",
        "hi": "यह लगभग कब हुआ? (घर ख़ाली करने / सामान ख़रीदने / आख़िरी वेतन मिलने की तारीख़। अंदाज़न महीना भी चलेगा।)",
        "hinglish": "Yeh lagbhag kab hua? (Ghar khaali karne / saaman kharidne / aakhri salary milne ki date. Approx month bhi chalega.)"},
    "agreement": {
        "en": "Do you have anything in writing (rent agreement, invoice, offer letter)? Or was it only verbal?",
        "hi": "क्या आपके पास कुछ लिखित है (किराया समझौता, बिल, ऑफ़र लेटर)? या सिर्फ़ ज़ुबानी बात थी?",
        "hinglish": "Kya aapke paas kuch likhit hai (rent agreement, bill, offer letter)? Ya sirf zubaani baat thi?"},
}

def merge(facts, new):
    """Merge new extraction into session facts without overwriting known values with nulls."""
    for k, v in (new or {}).items():
        if v in (None, "", [], "unknown") and k != "problem_type":
            continue
        if k == "problem_type" and v in (None, "", "unknown"):
            continue
        if k == "evidence":
            cur = facts.setdefault("evidence", [])
            for e in v:
                if e and e.lower() not in [c.lower() for c in cur]:
                    cur.append(e)
        elif k == "amount_inr":
            try:
                facts[k] = float(v)
            except (TypeError, ValueError):
                pass
        elif k in ("what_happened", "english_summary"):
            prev = facts.get(k)
            facts[k] = v if not prev else (prev if v in prev else (prev + " " + v)[-600:])
        else:
            facts[k] = v
    return facts

def missing_fields(facts):
    ptype = facts.get("problem_type")
    if ptype not in REQUIRED:
        return []
    return [f for f in REQUIRED[ptype] if facts.get(f) in (None, "", [])]

CIVIL_OVERRIDE = {"event_date": {
    "en": "Roughly when did the problem or breach happen? (An approximate month is fine.)",
    "hi": "समस्या या उल्लंघन लगभग कब हुआ? (अंदाज़न महीना भी चलेगा।)",
    "hinglish": "Problem ya breach lagbhag kab hua? (Approx month bhi chalega.)"}}

def question_for(field, lang, category=None):
    q = (CIVIL_OVERRIDE.get(field) if category == "civil" else None) or QUESTIONS[field]
    return q.get(lang) or q["en"]
