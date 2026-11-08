"""Template-based document generation (Jinja2) + DOCX / PDF export. The LLM never free-writes a legal document."""
import re, uuid
from datetime import date
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from . import config

PH = "[TO BE FILLED]"
TEMPLATES = {"deposit": "legal_notice_deposit.j2", "consumer": "consumer_complaint.j2", "salary": "wage_demand_notice.j2", "civil": "legal_notice_civil.j2"}
TITLES = {"deposit": "Legal Notice - Refund of Security Deposit", "consumer": "Consumer Complaint - Draft",
          "salary": "Demand Notice - Unpaid Salary", "civil": "Legal Notice - Civil Dispute / Breach of Contract"}

def inr(n):
    """Indian digit grouping: 1234567 -> 12,34,567"""
    try:
        s = str(int(round(float(n))))
    except (TypeError, ValueError):
        return PH
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
    return head + "," + tail

def _fmt_date(iso):
    try:
        y, m, d = map(int, str(iso)[:10].split("-"))
        return date(y, m, d).strftime("%d %B %Y")
    except (ValueError, TypeError):
        return PH

def build_context(facts, overrides=None):
    o = dict(overrides or {})
    ptype = facts.get("problem_type")
    ctx = {
        "today": date.today().strftime("%d %B %Y"), "year": date.today().year, "days": 15,
        "user_name": PH, "user_address": PH, "user_contact": PH,
        "other_party_name": facts.get("other_party_name") or PH, "other_party_address": PH,
        "premises_address": PH, "payment_mode": "", "requests_summary": "", "designation": PH, "period": PH,
        "item": PH, "district": PH, "user_city": PH, "enclosures": PH, "defect_description": PH, "prior_complaint": PH,
        "state": facts.get("state") or PH,
        "amount": inr(facts.get("amount_inr")) if facts.get("amount_inr") is not None else PH,
        "event_date": _fmt_date(facts.get("event_date")) if facts.get("event_date") else PH,
        "start_date": _fmt_date(facts.get("start_date")) if facts.get("start_date") else "",
        "what_happened": facts.get("what_happened") or PH,
        "agreement_sentence": {"written": "The arrangement was recorded in a written agreement.",
                               "none": "There was no written agreement; the arrangement was oral."}.get(facts.get("agreement"), ""),
        "resignation_sentence": "",
        "subject": "breach of contract / recovery of dues",
        "obligation": "perform your obligations / pay the agreed amount",
    }
    ev = [e for e in (facts.get("evidence") or [])]
    if ev:
        ctx["enclosures"] = "; ".join(ev) + " (copies)"
    for k, v in o.items():
        if v not in (None, ""):
            ctx[k] = v
    # time-limit note for consumer complaints
    ctx["limit_note"] = ""
    if ptype == "consumer" and facts.get("event_date"):
        try:
            y, m, d = map(int, str(facts["event_date"])[:10].split("-"))
            if (date.today() - date(y, m, d)).days > 730:
                ctx["limit_note"] = "[CHECK WITH A LAWYER: more than two years have passed since the cause of action; add a request to condone delay with reasons.]"
        except ValueError:
            pass
    return ctx

def render(ptype, ctx):
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATE_DIR)), autoescape=False)
    return env.get_template(TEMPLATES[ptype]).render(**ctx).strip()

NEXT_STEPS = {
 "deposit": """WHAT TO DO NEXT
1. Read the draft carefully, fill every [TO BE FILLED] and remove anything that is not true. Do not sign something you cannot back up with proof.
2. Print two copies. Sign them. Send one by Registered Post A.D. or Speed Post to the landlord's last known address; also send a copy by email/WhatsApp.
3. Keep: the postal receipt, tracking printout, the acknowledgement card when it returns, and your copy of the notice.
4. Wait for the deadline in the notice. Landlords often reply or pay after a notice.
5. If there is no reply: speak to a lawyer or your District Legal Services Authority (DLSA) about filing a civil recovery case. NALSA helpline: 15100.
6. Time limits apply to every claim. Do not wait for months.""",
 "consumer": """WHAT TO DO NEXT
1. Fill every [TO BE FILLED]. Attach copies (not originals) of the invoice, payment proof, photos/videos, and all messages or ticket numbers.
2. Before filing, it is wise to complain in writing to the seller/company (and to the National Consumer Helpline 1915 / consumerhelpline.gov.in) and keep proof.
3. File on the e-Daakhil portal (edaakhil.nic.in) or in person at the District Consumer Commission. Check the current fee for your claim amount on the portal.
4. Keep the filing acknowledgement and the case number. Attend the dates given by the Commission.
5. A lawyer is not compulsory but a free legal-aid lawyer may be available through your DLSA (NALSA helpline 15100).
6. If the amount you paid is more than Rs 50 lakh, a different (higher) Commission handles it.""",
 "salary": """WHAT TO DO NEXT
1. Fill every [TO BE FILLED]. State the exact months of unpaid salary and the amount.
2. Send the notice by Registered Post / Speed Post and also by email to the employer and HR. Keep proof of sending.
3. Wait for the deadline. If the employer pays, get a written acknowledgement or bank proof.
4. If not paid, approach your local labour office (Labour Commissioner's office / Inspector-cum-Facilitator) with this notice, your proof and your ID. Procedures differ by state.
5. Keep your salary slips, bank statements, offer letter and chats safe.
6. Claims have time limits. Act soon. Free legal aid: DLSA / NALSA helpline 15100.""",
 "civil": """WHAT TO DO NEXT
1. Read the draft carefully. Fill every [TO BE FILLED] and remove anything you cannot prove. Do not make claims without evidence.
2. Print two copies. Sign both. Send one by Registered Post A.D. / Speed Post to the other party's address; also send by email/WhatsApp.
3. Keep: the postal receipt, tracking printout, the acknowledgement card, and your copy.
4. Wait for the deadline (typically 15 days). Many disputes settle after a legal notice.
5. If no reply or unsatisfactory response: consult a lawyer about filing a civil suit for recovery, specific performance, injunction, or declaration as appropriate. File in the court having pecuniary and territorial jurisdiction.
6. Limitation period for contract/money suits is generally 3 years from when the cause of action arose. Do not delay. Free legal aid: DLSA / NALSA helpline 15100.""",
}

def _has_non_latin(s):
    return bool(re.search(r"[^\x00-\u024F\u2010-\u2027\u20A0-\u20CF]", s))

def export(text, title, outdir=None):
    """Write DOCX and PDF; return (docx_path, pdf_path, warning)."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    outdir = Path(outdir or (config.OUTPUT_DIR / uuid.uuid4().hex[:8]))
    outdir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")[:50]
    footer = "DRAFT generated by an AI tool. Review every line and get legal advice before sending or filing."
    lines = text.split("\n")

    d = Document()
    d.styles["Normal"].font.name = "Times New Roman"
    d.styles["Normal"].font.size = Pt(12)
    first = True
    for ln in lines:
        p = d.add_paragraph()
        r = p.add_run(ln)
        if first and ln.strip():
            r.bold = True
            r.font.size = Pt(14)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            first = False
    d.add_paragraph()
    fp = d.add_paragraph(footer)
    fp.runs[0].italic = True
    docx_path = outdir / f"{stem}.docx"
    d.save(docx_path)

    warning = ""
    font = "Helvetica"
    for f in sorted(config.FONT_DIR.glob("*.ttf")):
        pdfmetrics.registerFont(TTFont("UserFont", str(f)))
        font = "UserFont"
        break
    if font == "Helvetica" and _has_non_latin(text):
        warning = ("The PDF may not show Hindi/Bengali letters correctly because no font is installed. "
                   "Use the DOCX, or put a Noto Sans Devanagari/Bengali .ttf file in assets/fonts/.")
    style = ParagraphStyle("b", fontName=font, fontSize=11, leading=15)
    head = ParagraphStyle("h", parent=style, fontSize=14, leading=18, alignment=1)
    def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    story, first = [], True
    for ln in lines:
        if not ln.strip():
            story.append(Spacer(1, 6))
        else:
            story.append(Paragraph(esc(ln), head if first else style))
            first = False
    story += [Spacer(1, 14), Paragraph("<i>" + esc(footer) + "</i>", style)]
    pdf_path = outdir / f"{stem}.pdf"
    SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm).build(story)
    return str(docx_path), str(pdf_path), warning
