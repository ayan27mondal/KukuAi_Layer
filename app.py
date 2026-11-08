"""Streamlit UI:  streamlit run app.py"""
import streamlit as st
from lawyer import config, rag, voice, escalation
from lawyer.pipeline_v2 import Session, INTRO

st.set_page_config(page_title="AI Lawyer India", page_icon="⚖️", layout="centered")

def new_case():
    st.session_state.session = Session(lang_override=st.session_state.get("lang_pick") or None)
    st.session_state.msgs = [{"role": "assistant", "text": INTRO["en"], "reply": None}]
    st.session_state.audio_seen = None

if "session" not in st.session_state:
    new_case()
S: Session = st.session_state.session

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("⚖️ AI Lawyer India")
    st.caption("Legal **information**, not legal advice.")
    provs = config.providers()
    if config.is_mock():
        st.warning("MOCK mode (no AI model). Set LLM_PROVIDER and a free API key in .env for real answers.")
    else:
        ok = [p for p in provs if (p == "groq" and config.GROQ_API_KEY()) or (p == "gemini" and config.GEMINI_API_KEY())]
        (st.success if ok else st.error)(f"LLM: {', '.join(ok) if ok else 'no API key found in .env'}")
    idx = rag.get_index()
    st.caption("Retrieval: " + ("🧠 " if idx.backend == "chroma" else "🔍 ") + idx.backend_label)
    n_ver = sum(c.verified for c in idx.chunks)
    st.caption(f"Knowledge base: {len(idx.chunks)} notes, {n_ver} human-verified.")
    if n_ver < len(idx.chunks):
        st.warning("Some notes are NOT yet human-verified. See README → 'Verify the corpus'.")
    st.selectbox("Language", ["", "en", "hi", "hinglish", "bn", "as"], key="lang_pick", format_func=lambda x: {"": "Auto-detect", "en": "English", "hi": "हिन्दी", "hinglish": "Hinglish", "bn": "বাংলা", "as": "অসমীয়া"}[x],
                 on_change=lambda: setattr(S, "lang_override", st.session_state.lang_pick or None))
    tts = st.checkbox("🔊 Read replies aloud", value=False)
    if st.button("🆕 New case", use_container_width=True):
        new_case(); st.rerun()
    st.divider()
    st.subheader("🎤 Speak instead of typing")
    audio = st.audio_input("Record your problem") if hasattr(st, "audio_input") else None
    if audio is None and not hasattr(st, "audio_input"):
        audio = st.file_uploader("Upload a voice note", type=["wav", "mp3", "m4a", "ogg", "webm"])
    st.divider()
    st.subheader("📄 Draft a document")
    with st.expander("Your details (optional)"):
        ov = {"user_name": st.text_input("Your name"), "user_address": st.text_area("Your address", height=70), "user_contact": st.text_input("Phone / email"),
              "other_party_address": st.text_area("Other side's address", height=70), "premises_address": st.text_input("Rented premises address"),
              "item": st.text_input("Item / service (consumer)"), "district": st.text_input("District (consumer)"), "user_city": st.text_input("Your city"),
              "designation": st.text_input("Your job title (salary)"), "period": st.text_input("Unpaid months (salary), e.g. May-July 2026"),
              "payment_mode": st.text_input("How you paid the deposit (bank transfer / UPI / cash)")}
    c1, c2 = st.columns(2)
    do_doc = c1.button("Create draft", use_container_width=True)
    do_prac = c2.button("🎭 Practice" if not S.practice_active else "⏹ End", use_container_width=True)

# ---------------- actions ----------------
def push(reply, user_text=None):
    if user_text:
        st.session_state.msgs.append({"role": "user", "text": user_text})
    mp3 = voice.speak(reply.text, S.lang) if tts else None
    st.session_state.msgs.append({"role": "assistant", "text": reply.text, "reply": reply, "audio": mp3})

if do_doc:
    push(S.generate_document(ov), "📄 Create a draft document")
if do_prac:
    push(S.end_practice() if S.practice_active else S.start_practice(), "🎭 Practice" if not S.practice_active else "⏹ End practice")

prompt = st.chat_input("Describe your problem in your own words…")
if audio is not None:
    raw = audio.getvalue()
    h = hash(raw)
    if h != st.session_state.audio_seen:
        st.session_state.audio_seen = h
        try:
            with st.spinner("Listening…"):
                prompt = voice.transcribe(raw, getattr(audio, "name", None) or "audio.wav", S.lang_override)
            st.sidebar.success(f"Heard: {prompt}")
        except voice.VoiceError as e:
            st.sidebar.error(str(e))
if prompt:
    with st.spinner("Thinking…"):
        push(S.handle(prompt), prompt)

# ---------------- render ----------------
st.title("⚖️ AI Lawyer for everyday problems")
st.caption("Deposit · Refund / defective goods · Unpaid salary · Contract / money / property · Family (information only) — English, हिन्दी, Hinglish and more.")
for i, m in enumerate(st.session_state.msgs):
    with st.chat_message(m["role"]):
        r = m.get("reply")
        if r:
            for e in r.escalations:
                if e.level == "advise" and not e.lead:
                    st.warning("⚠️ " + e.message(S.lang))
            if r.stage == "escalated":
                st.error("🚨 Please see a real lawyer / legal aid")
            if r.warning and not r.document_text:
                st.info(r.warning)
        if r and r.summary_text:
            with st.expander("📋 Case summary & proof checklist", expanded=True):
                st.markdown(r.summary_text)
        st.markdown(m["text"])
        if m.get("audio"):
            st.audio(m["audio"], format="audio/mp3")
        if r:
            if r.document_text:
                with st.expander("Preview draft"):
                    st.text(r.document_text)
                if r.warning:
                    st.info(r.warning)
                for f in r.files:
                    with open(f, "rb") as fh:
                        st.download_button(f"⬇️ {f.rsplit('/', 1)[-1]}", fh.read(), file_name=f.rsplit("/", 1)[-1], key=f"dl{i}{f}")
            if r.retrieved:
                with st.expander("🔎 Sources used (knowledge-base notes)"):
                    for cid, score in r.retrieved:
                        c = rag.get_index().by_id(cid)
                        flag = "✅ verified" if c.verified else "⚠️ not human-verified"
                        st.markdown(f"**[{cid}]** {c.act} {('§' + c.section) if c.section else ''} — {flag} — score {score}")
                        st.caption(c.text)
            if r.violations:
                with st.expander(f"🛡️ Citation checker flagged {len(r.violations)} item(s)"):
                    st.json(r.violations)
st.divider()
st.caption(config.DISCLAIMER["en"])
