"""Practice mode: the AI plays the other side so the user can rehearse; then gives feedback."""
from . import config, llm, mock, rag, validator

ROLE = {"deposit": "landlord", "consumer": "seller", "salary": "employer", "civil": "opponent"}
ROLE_LABEL = {"deposit": "landlord", "consumer": "seller", "salary": "employer", "civil": "other party"}
ROLE_DESC = {
    "landlord": "a stubborn but not abusive landlord who is keeping the tenant's deposit",
    "seller": "a customer-care / seller representative who is refusing a refund",
    "employer": "an employer / HR person who is delaying the employee's salary",
    "opponent": "the other party in a contract or money dispute who denies owing anything",
}

ROLE_SYSTEM = """You are role-playing {desc} so that an ordinary person can practise a difficult conversation.
Stay in character. Use the typical excuses real people use (deductions, 'no proof', 'policy', 'cash crunch').
Be realistic and a little firm, but never abusive, never threatening.
RULES: Do NOT cite any law, section, Act or court case. Do NOT give the user legal advice. 2-3 short sentences only.
Reply in {language}. Facts of the real dispute (for realism): {facts}"""

FEEDBACK_SYSTEM = """You are a kind, honest coach reviewing how a person argued their side in a practice dispute conversation.
Give: 1) three things they did well, 2) three things to improve (be specific: amount, dates, proof, tone, clear demand, next step),
3) a stronger 2-sentence version of their main demand.
RULES: Do not predict who would win. Make legal statements ONLY from the CONTEXT and cite chunk ids in [brackets]. Never mention an Act, section or case not in CONTEXT.
Write in {language}. Under 220 words."""

def opponent_reply(ptype, facts, history, user_text, lang, turn):
    role = ROLE[ptype]
    if config.is_mock():
        return mock.roleplay(role, user_text, turn)
    convo = "\n".join(f"{'USER' if h['who']=='user' else role.upper()}: {h['text']}" for h in history[-8:])
    system = ROLE_SYSTEM.format(desc=ROLE_DESC[role], language=config.LANG_NAMES.get(lang, "English"), facts={k: facts.get(k) for k in ("amount_inr", "event_date", "what_happened")})
    out = llm.chat(system, f"Conversation so far:\n{convo}\nUSER: {user_text}\n{role.upper()}:", temperature=0.7).strip()
    # The opponent must not cite law: if it does, swap in a neutral line (cheap, safe guard).
    res = validator.validate(out, [], rag.get_index().chunks)
    if res.violations:
        return {"en": "I don't agree. Show me your proof and we can talk.", "hi": "मैं सहमत नहीं हूँ। अपने सबूत दिखाइए, फिर बात करते हैं।",
                "hinglish": "Main sahmat nahi hoon. Apna proof dikhaiye, phir baat karte hain."}.get(lang, "I don't agree. Show me your proof and we can talk.")
    return out

def opening_line(ptype, facts, lang):
    role = ROLE[ptype]
    if config.is_mock():
        return mock.roleplay(role, "", 0)
    return opponent_reply(ptype, facts, [], "(The user has just called you about the dispute. Start the conversation.)", lang, 0)

def feedback(ptype, facts, history, lang):
    user_lines = [h["text"] for h in history if h["who"] == "user"]
    idx = rag.get_index()
    chunks = [c for c, _ in idx.search(f"{ptype} complaint notice evidence", k=3, topic=ptype)]
    if config.is_mock():
        return mock.feedback(facts, user_lines), chunks, None
    ctx = "\n".join(f"[{c.id}] {c.text}" for c in chunks)
    convo = "\n".join(f"{'USER' if h['who']=='user' else 'OTHER SIDE'}: {h['text']}" for h in history)
    raw = llm.chat(FEEDBACK_SYSTEM.format(language=config.LANG_NAMES.get(lang, "English")),
                   f"FACTS: {facts}\nCONVERSATION:\n{convo}\n\nCONTEXT:\n{ctx}", temperature=0.3)
    return raw, chunks, raw
