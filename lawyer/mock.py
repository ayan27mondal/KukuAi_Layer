"""Offline MOCK 'LLM' used for tests and demos without any API key.
It is rule-based on purpose: it shows the pipeline, retrieval, validator and escalation work
independently of any particular model. Real quality numbers come from running with a real model."""
import re
from datetime import date, timedelta

HI_STATES = {"बिहार": "Bihar", "असम": "Assam", "महाराष्ट्र": "Maharashtra", "कर्नाटक": "Karnataka", "दिल्ली": "Delhi", "उत्तर प्रदेश": "Uttar Pradesh",
             "तमिलनाडु": "Tamil Nadu", "पश्चिम बंगाल": "West Bengal", "राजस्थान": "Rajasthan", "गुजरात": "Gujarat", "पटना": "Bihar", "लखनऊ": "Uttar Pradesh"}
STATES = ["andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana", "himachal pradesh",
          "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha",
          "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal", "delhi",
          "jammu and kashmir", "ladakh", "chandigarh", "puducherry"]
CITIES = {"guwahati": "Assam", "mumbai": "Maharashtra", "pune": "Maharashtra", "bangalore": "Karnataka", "bengaluru": "Karnataka",
          "chennai": "Tamil Nadu", "kolkata": "West Bengal", "hyderabad": "Telangana", "lucknow": "Uttar Pradesh", "jaipur": "Rajasthan",
          "patna": "Bihar", "ahmedabad": "Gujarat", "noida": "Uttar Pradesh", "gurgaon": "Haryana", "gurugram": "Haryana",
          "dibrugarh": "Assam", "silchar": "Assam", "jorhat": "Assam", "bhopal": "Madhya Pradesh", "kochi": "Kerala"}
KW = {
    "deposit": ["deposit", "advance", "landlord", "tenant", "rent ", "makaan malik", "makan malik", "kiraya", "kiraydar", "security money", "मकान मालिक", "डिपॉज़िट", "डिपॉजिट", "किराए", "किराये", "flat"],
    "consumer": ["refund", "defective", "product", "order", "seller", "amazon", "flipkart", "coaching", "warranty", "delivered", "faulty", "replacement", "return policy", "रिफ़ंड", "रिफंड", "खराब", "ख़राब", "सामान", "fees back"],
    "salary": ["salary", "wages", "employer", "tankhwah", "tankha", "unpaid", "not paid", "boss", "hr ", "resign", "full and final", "f&f", "वेतन", "तनख्वाह", "सैलरी", "salary nahi"],
    "civil": ["borrowed", "repay", "lent ", "owes me", "contract", "breach", "agreement", "property", "dispute", "recovery", "injunction", "specific performance", "partition", "declaration", "suit", "civil court", "damages", "money owed", "loan", "promissory note", "cheque bounce", "title", "possession", "easement", "mutation", "अनुबंध", "भंग", "संपत्ति", "विवाद", "वसूली", "निषेधाज्ञा", "विभाजन", "घोषणा", "मुकदमा", "सिविल कोर्ट", "क्षतिपूर्ति", "उधार", "चेक बाउंस", "arbitration", "arbitration agreement", "commercial court", "rera", "real estate", "insolvency", "bankruptcy", "msme", "delayed payment", "summary suit", "interpleader", "rectification", "rescission", "cancellation", "negotiable instrument", "cheque", "hundi", "promissory note", "guarantee", "guarantor"],
    "family": ["divorce", "custody", "maintenance", "alimony", "adultery", "cruelty", "desertion", "dowry", "domestic violence", "498a", "husband", "wife", "marriage", "separation", "mutual consent", "khula", "talaq", "annulment", "void marriage", "voidable marriage", "restitution", "conjugal rights", "child custody", "visitation", "guardian", "adoption", "inheritance", "succession", "stridhan", "coparcener", "ancestral property", "self-acquired property", "women property rights", "parents maintenance", "senior citizen", "family court", "family dispute", "matrimonial", "live in relationship", "protection order", "residence order", "monetary relief", "compensation", "muslim law", "christian divorce", "special marriage", "interfaith marriage", "husband affair", "wife affair", "cheating spouse", "extra marital", "infidelity", "बेवफाई", "धोखा", "तलाक", "भरण पोषण", "गुजारा भत्ता", "बच्चों की कस्टडी", "घरेलू हिंसा", "दहेज", "स्त्रीधन", "पैतृक संपत्ति", "guarantee"],
}
EVIDENCE_KW = {"WhatsApp chats": ["whatsapp", "chat", "message", "sms", "text me"], "emails": ["email", "e-mail", "mail "],
               "payment receipt / bank proof": ["receipt", "bank", "upi", "transfer", "gpay", "paytm", "payment proof", "statement"],
               "written agreement": ["agreement", "lease", "contract", "offer letter", "appointment letter"],
               "photos/videos": ["photo", "video", "picture"], "invoice": ["invoice", "bill ", "order confirmation"],
               "salary slips": ["salary slip", "payslip", "pay slip"]}
MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
NUMW = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

def _amount(t):
    tl = t.lower().replace(",", "")
    m = re.search(r"(?:₹|rs\.?|inr|rupees?)\s*(\d+(?:\.\d+)?)\s*(lakh|lac|crore|k|thousand|hazaar|हज़ार)?", tl) or \
        re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac|crore|k|thousand|hazaar|हज़ार)?\s*(?:rupees?|rs\b|₹|रुपये|रुपए|रुपया)", tl) or \
        re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac|crore)\b", tl)
    if not m:
        return None
    v = float(m.group(1)); u = m.group(2) or ""
    return v * {"lakh": 1e5, "lac": 1e5, "crore": 1e7, "k": 1e3, "thousand": 1e3, "hazaar": 1e3, "हज़ार": 1e3}.get(u, 1)

def _date(t, today):
    tl = t.lower()
    m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", tl)
    if m: return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", tl)
    if m: return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    m = re.search(r"\b(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?(" + "|".join(MONTHS) + r")[a-z]*,?\s+(20\d{2})\b", tl)
    if m: return date(int(m[3]), MONTHS[m[2]], int(m[1] or 1)).isoformat()
    m = re.search(r"\b(\d+|a|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(day|week|month|year)s?\s+(?:ago|pehle)", tl)
    if not m:
        h = re.search(r"(\d+)\s*(दिन|हफ्ते|हफ़्ते|महीने|महीना|साल)\s*पहले", tl)
        if h:
            days = {"दिन": 1, "हफ्ते": 7, "हफ़्ते": 7, "महीने": 30, "महीना": 30, "साल": 365}[h[2]] * int(h[1])
            return (today - timedelta(days=days)).isoformat()
    if not m:
        m2 = re.search(r"\b(\d+)\s+(?:mahine|mahina|din|saal)\s+pehle", tl)
        if m2:
            unit = re.search(r"(mahine|mahina|din|saal)", m2[0])[1]
            return (today - timedelta(days={"mahine": 30, "mahina": 30, "din": 1, "saal": 365}[unit] * int(m2[1]))).isoformat()
    if m:
        n = int(m[1]) if m[1].isdigit() else NUMW[m[1]]
        days = {"day": 1, "week": 7, "month": 30, "year": 365}[m[2]] * n
        return (today - timedelta(days=days)).isoformat()
    return None

def extract(text, known=None, today=None):
    today = today or date.today()
    tl = " " + text.lower() + " "
    # If problem_type is already known, don't re-classify
    if known and known.get("problem_type") in KW:
        ptype = known["problem_type"]
    else:
        scores = {k: sum(1 for w in ws if w in tl) for k, ws in KW.items()}
        ptype = max(scores, key=scores.get) if max(scores.values()) > 0 else "unknown"
    state = next((s.title() if s != "delhi" else "Delhi" for s in STATES if re.search(r"\b" + s + r"\b", tl)), None)
    state = state or next((v for c, v in CITIES.items() if c in tl), None) or next((v for c, v in HI_STATES.items() if c in text), None)
    party = None
    m = re.search(r"(?:landlord|employer|seller|company|owner|malik)\s+(?:is\s+|named\s+|called\s+)?([A-Z][A-Za-z\.]+(?:\s[A-Z][A-Za-z\.]+)?)", text)
    if m and m[1].lower() not in {"is", "has", "wont", "won't", "refuses", "not", "did", "will"}:
        party = m[1]
    elif re.search(r"\b(landlord|owner)\b|मकान मालिक", tl): party = "the landlord"
    elif re.search(r"\b(employer|company|boss)\b|कंपनी", tl) and ptype == "salary": party = "the employer"
    elif re.search(r"\b(seller|company|shop|store|coaching)\b", tl) and ptype == "consumer": party = "the seller"
    elif re.search(r"\b(party|opponent|defendant|respondent)\b", tl) and ptype == "civil": party = "the opposing party"
    agreement = "written" if re.search(r"(?<!no )(?<!without )(rent agreement|written agreement|agreement|lease|offer letter)", tl) and not re.search(r"no (written )?(rent )?agreement|without (a )?(written )?agreement|verbal|oral|zubaani", tl) else \
                ("none" if re.search(r"no (written )?(rent )?agreement|without (a )?(written )?agreement|verbal|oral|zubaani|nothing in writing", tl) else None)
    evidence = [name for name, ws in EVIDENCE_KW.items() if any(w in tl for w in ws)]
    if agreement != "written" and "written agreement" in evidence:
        evidence.remove("written agreement")
    summary = text.strip()[:300]
    return {"problem_type": ptype, "state": state, "other_party_name": party, "amount_inr": _amount(text), "start_date": None,
            "event_date": _date(text, today), "agreement": agreement, "evidence": evidence, "what_happened": summary,
            "english_summary": summary, "desired_outcome": None}

def answer(facts, question, chunks, lang):
    """Extractive stand-in for the grounded answer: quotes the top chunks and cites their IDs."""
    parts = ["Where you stand (based on the verified notes I retrieved):"]
    for c, _ in chunks[:3]:
        first = re.split(r"(?<=[.!?])\s", c.text.strip())[0]
        parts.append(f"- {first} [{c.id}]")
    parts.append("Next step: if the other side does not respond, consider sending a written notice and then the forum described above. If anything here is unclear, speak to a lawyer or free legal aid.")
    return "\n".join(parts)

OPPONENT_LINES = {
    "landlord": ["I deducted for repainting and cleaning. The flat was left in a bad state.", "You have no written proof that I owe you anything. Why should I pay now?", "Fine, show me the receipts. I'll think about it, but don't expect the full amount."],
    "seller": ["Our policy says no refund after delivery. You used the product.", "The defect is not covered by warranty. This is physical damage.", "Send us photos again; we'll escalate, but it takes 30 working days."],
    "employer": ["The company is going through a cash crunch. Salary will come when funds arrive.", "You didn't complete the notice period, so your dues are on hold.", "Submit the clearance form first, then we will process everything."],
    "opponent": ["The contract doesn't say that. You're misinterpreting the terms.", "I don't owe you anything. The work was completed as agreed.", "If you have a problem, go to court. I'm not paying without a judge's order.", "This is a civil matter. Get a lawyer and we'll see."],
}
def roleplay(role, user_text, turn):
    lines = OPPONENT_LINES.get(role, OPPONENT_LINES["landlord"])
    return lines[turn % len(lines)]

def feedback(facts, transcript_user_lines):
    joined = " ".join(transcript_user_lines).lower()
    good, improve = [], []
    (good if re.search(r"\d{3,}|lakh|₹|rs", joined) else improve).append(("You stated the exact amount.", "Mention the exact amount."))
    (good if re.search(r"20\d{2}|january|february|march|april|may|june|july|august|september|october|november|december|ago", joined) else improve).append(("You gave dates.", "Mention dates."))
    (good if re.search(r"proof|receipt|chat|whatsapp|email|bank|agreement|invoice|screenshot|photo", joined) else improve).append(("You pointed to your proof.", "Refer to your proof."))
    (good if re.search(r"notice|complaint|forum|commission|labour", joined) else improve).append(("You said what you will do next.", "Say clearly what you will do next if it is not resolved."))
    good = [g[0] for g in good if isinstance(g, tuple)]
    improve = [i[1] for i in improve if isinstance(i, tuple)]
    return "What you did well: " + (" ".join(good) or "You stayed engaged.") + "\nWhat to improve: " + (" ".join(improve) or "Keep it calm and specific.")


# ============ Offline stand-in for the LLM "understanding" step (same JSON schema as the real LLM) ============
def understand(text, known=None, today=None):
    from . import escalation as E
    today = today or date.today()
    tl = text.lower()
    extracted = extract(text, known, today)
    found = E.check_text(text)
    esc_type = next((k for k, v in E.LLM_TYPES.items() if any(e.code == v[0] for e in found)), "none")
    intent = "legal_info"
    if re.search(r"practice|practise|role.?play|rehears", tl):
        intent = "practice"
    elif re.search(r"draft|notice|complaint|letter|likh|banao", tl):
        intent = "draft_notice"
    return {
        "problem_category": extracted["problem_type"],
        "escalation_type": esc_type,
        "key_facts": {"state": extracted.get("state"), "other_party": extracted.get("other_party_name"),
                      "amount_inr": extracted.get("amount_inr"), "start_date": None, "event_date": extracted.get("event_date"),
                      "has_written_agreement": {"written": True, "none": False}.get(extracted.get("agreement")),
                      "evidence_mentioned": extracted.get("evidence", [])},
        "user_intent": intent,
        "search_query": f"{extracted['problem_type']} {' '.join(tl.split()[:20])}",
        "summary_english": text.strip()[:300], "summary_for_user": text.strip()[:300], "language": "en",
    }
