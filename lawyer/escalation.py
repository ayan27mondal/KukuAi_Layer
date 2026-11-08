"""HARD-CODED escalation rules. These do NOT depend on the LLM, so they cannot be talked out of.

level 'stop'   -> the bot does not give an answer, only the escalation message.
level 'advise' -> the bot still answers, but shows a prominent 'see a lawyer' banner.
"""
import re
from dataclasses import dataclass
from datetime import date
from . import config

FOOTER = {
    "en": "Free legal aid: your District Legal Services Authority (DLSA) or the NALSA helpline 15100.",
    "hi": "मुफ़्त कानूनी सहायता: अपने ज़िले की DLSA (ज़िला विधिक सेवा प्राधिकरण) या NALSA हेल्पलाइन 15100।",
    "hinglish": "Free legal aid: apne zile ki DLSA (District Legal Services Authority) ya NALSA helpline 15100.",
}

MSG = {
    "CRISIS": {
        "en": "I'm really sorry you're going through this. Your safety matters more than any legal problem. Please call 112 (emergency) or Tele-MANAS 14416 right now, or reach out to someone you trust. I'm here to help with the legal side whenever you're ready.",
        "hi": "आपके साथ जो हो रहा है उसके लिए मुझे बहुत दुख है। आपकी सुरक्षा किसी भी कानूनी समस्या से ज़्यादा ज़रूरी है। कृपया अभी 112 (आपातकाल) या Tele-MANAS 14416 पर कॉल करें, या किसी भरोसेमंद व्यक्ति से बात करें।",
        "hinglish": "Mujhe bahut dukh hai ki aap yeh sab jhel rahe hain. Aapki safety kisi bhi legal problem se zyada zaroori hai. Please abhi 112 (emergency) ya Tele-MANAS 14416 par call karein, ya kisi apne se baat karein.",
    },
    "CRIMINAL": {
        "en": "This looks like a criminal or police matter (arrest, FIR, cheating, threats or a bounced cheque). That is outside what I can safely help with. Please speak to a criminal lawyer or free legal aid before you do or sign anything. If you are in danger, call 112.",
        "hi": "यह आपराधिक या पुलिस से जुड़ा मामला लगता है (गिरफ़्तारी, FIR, धोखाधड़ी, धमकी या चेक बाउंस)। इसमें मैं सुरक्षित रूप से मदद नहीं कर सकता। कुछ भी करने या हस्ताक्षर करने से पहले कृपया आपराधिक मामलों के वकील या मुफ़्त कानूनी सहायता से मिलें। ख़तरा हो तो 112 पर कॉल करें।",
        "hinglish": "Yeh criminal ya police matter lagta hai (arrest, FIR, cheating, threat ya cheque bounce). Isme main safely help nahi kar sakta. Kuch bhi karne ya sign karne se pehle please criminal lawyer ya free legal aid se milein. Khatra ho to 112 par call karein.",
    },
    "DOMESTIC_VIOLENCE": {
        "en": "If you or someone close to you is being hurt or threatened at home, please get help now: call 112 for emergencies or the Women Helpline 181. A lawyer, a protection officer or a legal-aid clinic can act on this. Below is general information about legal protections.",
        "hi": "अगर आप या आपका कोई अपना घर में मारपीट या धमकी झेल रहा है, तो अभी मदद लें: आपातकाल में 112 या महिला हेल्पलाइन 181 पर कॉल करें। वकील, संरक्षण अधिकारी या विधिक सहायता केंद्र इसमें कार्रवाई कर सकते हैं। नीचे क़ानूनी सुरक्षा की सामान्य जानकारी है।",
        "hinglish": "Agar aap ya aapka koi apna ghar mein maarpeet ya dhamki jhel raha hai, to abhi madad lein: emergency mein 112 ya Women Helpline 181 par call karein. Vakeel, protection officer ya legal-aid clinic is par karwai kar sakte hain. Neeche legal protection ki general jaankari hai.",
    },
    "COURT_STAGE": {
        "en": "A court summons, notice or hearing date has already been issued. Deadlines in court cases are strict and missing one can hurt you badly. Please take the papers to a lawyer or your DLSA immediately. I can help you understand general processes, but not handle a live court case.",
        "hi": "आपके मामले में अदालत का समन, नोटिस या सुनवाई की तारीख़ आ चुकी है। अदालती समय-सीमाएँ सख़्त होती हैं और चूकने से भारी नुकसान हो सकता है। कृपया कागज़ात लेकर तुरंत वकील या अपनी DLSA से मिलें।",
        "hinglish": "Aapke case mein court ka summons, notice ya hearing date aa chuki hai. Court ki deadlines strict hoti hain, chook gaye to bahut nuksaan ho sakta hai. Please papers lekar turant vakeel ya apni DLSA se milein.",
    },
    "STRATEGY_OR_GUARANTEE": {
        "en": "I can't promise you'll win or predict the outcome, and I won't give litigation strategy. Nobody honest can guarantee a result. What I can do is explain your options, list what proof you have or lack, and prepare a draft. For strategy, please consult a lawyer.",
        "hi": "मैं जीत की गारंटी या नतीजे की भविष्यवाणी नहीं दे सकता, और मुकदमे की रणनीति भी नहीं बताऊँगा। कोई ईमानदार व्यक्ति नतीजे की गारंटी नहीं दे सकता। मैं आपके विकल्प समझा सकता हूँ, सबूतों की सूची बना सकता हूँ और मसौदा तैयार कर सकता हूँ। रणनीति के लिए वकील से मिलें।",
        "hinglish": "Main jeet ki guarantee ya result ki prediction nahi de sakta, aur litigation strategy bhi nahi bataunga. Koi imaandar insaan result guarantee nahi kar sakta. Main aapke options samjha sakta hoon, proof ki list bana sakta hoon aur draft tayyar kar sakta hoon. Strategy ke liye vakeel se milein.",
    },
    "OUT_OF_SCOPE": {
        "en": "This is outside the problems I can help with safely (I only cover: security deposit not returned, refund / defective goods or services, and unpaid salary). Family, property, inheritance and eviction matters especially need a real lawyer.",
        "hi": "यह उन समस्याओं से बाहर है जिनमें मैं सुरक्षित रूप से मदद कर सकता हूँ (मैं सिर्फ़ ये कवर करता हूँ: सिक्योरिटी डिपॉज़िट वापसी, रिफ़ंड / ख़राब सामान या सेवा, और बकाया वेतन)। परिवार, संपत्ति, विरासत और बेदख़ली के मामलों में असली वकील ज़रूरी है।",
        "hinglish": "Yeh un problems se bahar hai jinme main safely help kar sakta hoon (main sirf yeh cover karta hoon: security deposit wapas, refund / kharab saaman ya service, aur pending salary). Family, property, inheritance aur eviction ke matters mein asli vakeel zaroori hai.",
    },
    "LARGE_AMOUNT": {
        "en": "The amount involved is large. With this much at stake, please have a lawyer review your case before you send any notice or file anything.",
        "hi": "इसमें रकम बड़ी है। इतनी रकम में कोई नोटिस भेजने या शिकायत दर्ज करने से पहले कृपया वकील से अपना मामला दिखवा लें।",
        "hinglish": "Isme amount bada hai. Itne amount mein notice bhejne ya complaint file karne se pehle please vakeel se apna case dikhwa lein.",
    },
    "LIMITATION_NEAR": {
        "en": "Time limits apply to legal claims, and yours may be close to expiring or may already be late. Please speak to a lawyer or your DLSA soon.",
        "hi": "कानूनी दावों की समय-सीमा होती है, और आपकी समय-सीमा नज़दीक हो सकती है या निकल भी चुकी हो सकती है। कृपया जल्दी वकील या अपनी DLSA से बात करें।",
        "hinglish": "Legal claims ki time limit hoti hai, aur aapki limit paas ho sakti hai ya nikal bhi chuki ho sakti hai. Please jaldi vakeel ya apni DLSA se baat karein.",
    },
    "FAMILY_MATTER": {
        "en": "Family matters (marriage, divorce, custody, maintenance, inheritance) depend heavily on your religion, your facts and the court's discretion. What follows is general information only. Please see a family lawyer or your DLSA before you act.",
        "hi": "पारिवारिक मामले (विवाह, तलाक़, कस्टडी, भरण-पोषण, विरासत) आपके धर्म, तथ्यों और अदालत के विवेक पर बहुत निर्भर करते हैं। आगे सिर्फ़ सामान्य जानकारी है। कोई कदम उठाने से पहले कृपया पारिवारिक मामलों के वकील या DLSA से मिलें।",
        "hinglish": "Family matters (shaadi, divorce, custody, maintenance, inheritance) aapke dharm, facts aur court ke vivek par bahut nirbhar karte hain. Aage sirf general jaankari hai. Koi kadam uthane se pehle please family vakeel ya DLSA se milein.",
    },
    "CHEQUE_BOUNCE": {
        "en": "A bounced cheque can become a criminal case with very short, strict deadlines for sending notice. Please speak to a lawyer quickly. Do not wait.",
        "hi": "चेक बाउंस आपराधिक मामला बन सकता है और नोटिस भेजने की समय-सीमाएँ बहुत छोटी और सख़्त होती हैं। कृपया जल्दी वकील से बात करें। देर न करें।",
        "hinglish": "Cheque bounce criminal case ban sakta hai aur notice bhejne ki deadlines bahut chhoti aur strict hoti hain. Please jaldi vakeel se baat karein. Der na karein.",
    },
    "CASE_LAW": {
        "en": "I don't cite court judgments, because AI tools often get these wrong. A lawyer or legal-aid clinic can find the right ones for you.",
        "hi": "मैं अदालती फ़ैसलों के हवाले नहीं देता, क्योंकि AI अक्सर इनमें ग़लती करता है। वकील या विधिक सहायता केंद्र सही फ़ैसले ढूँढ सकते हैं।",
        "hinglish": "Main court judgments ke reference nahi deta, kyunki AI aksar inme galti karta hai. Vakeel ya legal-aid clinic sahi judgments dhoondh sakte hain.",
    },
}

@dataclass
class Escalation:
    code: str
    level: str  # stop | advise
    lead: bool = False   # True = put the message at the TOP of the reply text (life-safety information)

    def message(self, lang="en"):
        m = MSG[self.code]
        lang = lang if lang in m else "en"
        body = m[lang]
        if self.code != "CRISIS":
            body += " " + FOOTER.get(lang, FOOTER["en"])
        return body

def _any(patterns, text):
    return any(re.search(p, text, re.I) for p in patterns)

CRISIS = [r"\bsuicide\b", r"kill myself", r"end my life", r"want to die", r"aatmahatya", r"mar jaunga", r"khud ko khatam", r"आत्महत्या", r"मर जाऊँगा", r"जान दे दूँ"]
CRIMINAL = [r"\bpolice\b", r"\bpulis\b", r"\bthana\b", r"\bfir\b", r"\barrest", r"\bjail\b", r"\bwarrant\b", r"\b420\b", r"\bcheating case\b", r"threat(?:en|s)? (?:to|me)", r"dhamki", r"dhamkaya", r"kill me", r"जेल", r"पुलिस", r"एफआईआर", r"गिरफ़?्तार", r"धमकी", r"चेक बाउंस", r"thok denge", r"जान से मार"]
DV = [r"domestic violence", r"husband beats", r"beats me", r"\b498\s?a\b", r"dowry", r"gharelu hinsa", r"maarpeet", r"maar peet", r"marpeet", r"घरेलू हिंसा", r"मारपीट", r"दहेज"]
COURT = [r"summons?\b", r"\bsamman\b", r"\bsammon", r"court notice", r"hearing date", r"next hearing", r"hearing is on", r"court hearing", r"\bdecree\b", r"court ne bulaya", r"court.{0,15}(?:tareekh|tarikh)", r"(?:agli|next) (?:tareekh|tarikh)", r"सम्मन", r"समन", r"सुनवाई", r"अगली तारीख", r"already filed a case against me", r"case filed against me", r"ex.?parte"]
STRATEGY = [r"will i win", r"guarantee", r"100\s?% sure", r"promise me", r"i will win", r"i'll win", r"sure.?shot", r"jeet jaunga", r"jeet jaaunga", r"jitunga", r"win the case for sure", r"best strategy to (?:beat|defeat|destroy)", r"how (?:to|do i) (?:fool|trick|cheat)", r"जीत जाऊँगा", r"गारंटी"]
FAMILY = [r"divorce", r"custody", r"alimony", r"maintenance case", r"\bmaintenance\b.{0,20}(?:wife|husband|spouse)", r"inherit", r"\btalaq\b", r"\bkhula\b", r"matrimonial", r"adoption", r"restitution of conjugal", r"\bdowry\b", r"vasiyat", r"तलाक", r"भरण.?पोषण", r"गुज़ारा भत्ता", r"गुजारा भत्ता", r"विरासत", r"कस्टडी"]
CHEQUE = [r"che(?:que|ck) bounc", r"bounc\w*.{0,25}che(?:que|ck)", r"che(?:que|ck).{0,80}bounc", r"dishonou?red che(?:que|ck)", r"\bsection 138\b", r"चेक बाउंस"]
OUT_OF_SCOPE = []   # nothing is blocked by keyword any more: the LLM may still report category 'out_of_scope' (criminal/emergency)
CASE_LAW = [r"supreme court (?:judg|case|ruling|order|verdict)", r"high court (?:judg|case|ruling|order|verdict)", r"cite the case", r"case name", r"high court judg", r"case law", r"precedent", r"landmark (?:case|judg)", r"which judgment", r"kaunsa judgment", r"नजीर", r"फ़ैसले का हवाला"]

def check_text(text):
    """Escalations triggered purely by what the user wrote."""
    out = []
    if _any(CRISIS, text):
        out.append(Escalation("CRISIS", "stop"))
    if _any(DV, text):
        out.append(Escalation("DOMESTIC_VIOLENCE", "advise", lead=True))
    if _any(CRIMINAL, text):
        out.append(Escalation("CRIMINAL", "stop"))
    if _any(COURT, text):
        out.append(Escalation("COURT_STAGE", "stop"))
    if _any(STRATEGY, text):
        out.append(Escalation("STRATEGY_OR_GUARANTEE", "stop"))
    if _any(OUT_OF_SCOPE, text):
        out.append(Escalation("OUT_OF_SCOPE", "stop"))
    if _any(FAMILY, text):
        out.append(Escalation("FAMILY_MATTER", "advise"))
    if _any(CHEQUE, text):
        out.append(Escalation("CHEQUE_BOUNCE", "advise"))
    if _any(CASE_LAW, text):
        out.append(Escalation("CASE_LAW", "advise"))
    return out

# (warn after N years, 'probably late' after N years). Conservative; see corpus for the sources.
LIMITATION_YEARS = {"deposit": (2.5, 3.0), "consumer": (1.5, 2.0), "salary": (0.9, 3.0), "civil": (2.5, 3.0)}

def check_facts(facts, today=None):
    """Escalations triggered by extracted facts (amount, limitation)."""
    today = today or date.today()
    out = []
    amt = facts.get("amount_inr")
    try:
        if amt is not None and float(amt) >= config.LARGE_AMOUNT_THRESHOLD():
            out.append(Escalation("LARGE_AMOUNT", "advise"))
    except (TypeError, ValueError):
        pass
    ptype, ev = facts.get("problem_type"), facts.get("event_date")
    if ptype in LIMITATION_YEARS and ev:
        try:
            y, m, d = map(int, str(ev)[:10].split("-"))
            years = (today - date(y, m, d)).days / 365.25
            if years >= LIMITATION_YEARS[ptype][0]:
                out.append(Escalation("LIMITATION_NEAR", "advise"))
        except (ValueError, TypeError):
            pass
    return out


# The LLM may ADD escalations (it understands context better than keywords) but can never remove one.
LLM_TYPES = {"crisis": ("CRISIS", "stop", False), "criminal": ("CRIMINAL", "stop", False), "court_stage": ("COURT_STAGE", "stop", False),
             "strategy_guarantee": ("STRATEGY_OR_GUARANTEE", "stop", False), "domestic_violence": ("DOMESTIC_VIOLENCE", "advise", True),
             "family_law": ("FAMILY_MATTER", "advise", False), "cheque_bounce": ("CHEQUE_BOUNCE", "advise", False)}

def from_llm(escalation_type):
    t = LLM_TYPES.get((escalation_type or "").strip().lower())
    return Escalation(t[0], t[1], t[2]) if t else None

def merge(found, extra):
    codes = {e.code for e in found}
    return found + [e for e in extra if e and e.code not in codes]
