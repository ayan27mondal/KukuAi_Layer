"""Citation validator: the last line of defence against invented law.

Checks every model output against the chunks that were actually retrieved:
  1. [CHUNK-ID] citations must refer to a retrieved chunk -> otherwise removed.
  2. 'Section/Sec./Article/Rule N' mentions must appear in a retrieved chunk -> otherwise flagged.
  3. Names of Acts/Codes/Rules must exist in the corpus -> otherwise flagged.
  4. Case-law style citations (X v. Y, AIR 1999, SCC) are always flagged (case law is excluded by design).
"""
import re
from dataclasses import dataclass, field

FLAG = " [⚠ not verified in corpus]"

SEC_RE = re.compile(r"\b(?:Sections?|Sec\.|Secs\.|Article|Articles|Rule|Rules|Order)\s+(\d+[A-Za-z]?(?:\(\w+\))*(?:\s*(?:,|and|&|to|-)\s*\d+[A-Za-z]?(?:\(\w+\))*)*)", re.I)
ACT_RE = re.compile(r"\b((?:The\s+)?(?:[A-Z][\w’'\-\(\)]*\s+){0,8}?(?:Act|Code|Rules|Regulations)(?:,?\s*(?:19|20)\d{2})?)")
CASE_RE = re.compile(r"\b[A-Z][\w\.]+(?:\s[A-Z][\w\.]+)*\s+(?:v\.|vs\.?|versus)\s+[A-Z][\w\.]+(?:\s[A-Z][\w\.]+)*|\bAIR\s+\d{4}|\b\d{4}\s+\(?\d*\)?\s*SCC\b|\bSCC\s+\d+", re.U)
CITE_RE = re.compile(r"\[([A-Z0-9][A-Z0-9\-_\.]{2,})\]")

def _norm(s):
    s = re.sub(r"^the\s+", "", s.strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

@dataclass
class Result:
    text: str
    violations: list = field(default_factory=list)   # dicts: {type, value}
    cited_ids: list = field(default_factory=list)    # valid ids
    invalid_ids: list = field(default_factory=list)
    n_citations: int = 0

    @property
    def citation_accuracy(self):
        return None if self.n_citations == 0 else len(self.cited_ids) / self.n_citations

def _section_numbers(chunks):
    nums = set()
    for c in chunks:
        if c.section:
            nums.update(re.findall(r"\d+[A-Za-z]?", c.section))
        # numbers written after 'Section'/'Rule'... inside the chunk text itself
        for m in SEC_RE.finditer(c.text):
            nums.update(re.findall(r"\d+[A-Za-z]?", m.group(1)))
    return {n.lower() for n in nums}

def _known_acts(all_chunks):
    acts = set()
    for c in all_chunks:
        if c.act:
            acts.add(_norm(c.act))
            acts.add(_norm(re.sub(r",?\s*(19|20)\d{2}", "", c.act)))
        for m in ACT_RE.finditer(c.text):
            acts.add(_norm(m.group(1)))
            acts.add(_norm(re.sub(r",?\s*(19|20)\d{2}", "", m.group(1))))
    return acts

def validate(text, retrieved_chunks, all_chunks=None, extra_text=""):
    """retrieved_chunks: chunks given to the model. all_chunks: whole corpus (for Act-name check)."""
    all_chunks = all_chunks or retrieved_chunks
    res = Result(text=text)
    ret_ids = {c.id for c in retrieved_chunks}
    allowed_nums = _section_numbers(retrieved_chunks)
    if extra_text:
        for m in SEC_RE.finditer(extra_text):
            allowed_nums.update(n.lower() for n in re.findall(r"\d+[A-Za-z]?", m.group(1)))
    acts = _known_acts(all_chunks)

    # 1. chunk-id citations
    def fix_cite(m):
        cid = m.group(1)
        res.n_citations += 1
        if cid in ret_ids:
            if cid not in res.cited_ids:
                res.cited_ids.append(cid)
            return m.group(0)
        res.invalid_ids.append(cid)
        res.violations.append({"type": "invalid_citation_id", "value": cid})
        return ""
    out = CITE_RE.sub(fix_cite, text)

    # 4. case law (flag first so later regexes don't double count)
    def fix_case(m):
        res.violations.append({"type": "case_law", "value": m.group(0)})
        return m.group(0) + FLAG
    out = CASE_RE.sub(fix_case, out)

    # 2. section numbers
    def fix_sec(m):
        nums = [n.lower() for n in re.findall(r"\d+[A-Za-z]?", m.group(1))]
        bad = [n for n in nums if n not in allowed_nums]
        if bad:
            res.violations.append({"type": "unknown_section", "value": m.group(0)})
            return m.group(0) + FLAG
        return m.group(0)
    out = SEC_RE.sub(fix_sec, out)

    # 3. Act names
    def fix_act(m):
        name = m.group(1)
        n = _norm(name)
        n_noyear = _norm(re.sub(r",?\s*(19|20)\d{2}", "", name))
        # Exact match first
        if n in acts or n_noyear in acts:
            return name
        # Fuzzy match: only for longer names (avoid matching "act" in "fictional tenants protection act")
        # Skip fuzzy match for very short n_noyear (< 10 chars) to prevent "act" matching everything
        if len(n_noyear) >= 10 and any(n_noyear and (n_noyear in a or a in n_noyear) and len(a) >= 10 for a in acts):
            return name
        # ignore generic words
        if n_noyear in {"act", "code", "rules", "this act", "the act", "labour code"}:
            return name
        res.violations.append({"type": "unknown_act", "value": name})
        return name + FLAG
    out = ACT_RE.sub(fix_act, out)
    res.text = out
    return res

NOTE = "(I removed {n} statement(s) from this answer because I could not verify them in my knowledge base.)"
_PROTECT = re.compile(r"\b(v|vs|Sec|Secs|No|Rs|Mr|Mrs|Dr|Art)\.")

def strip_flagged(text):
    """Remove every sentence that carries a ⚠ flag, so unverified law never reaches the user. Returns (text, n_removed)."""
    mark = FLAG.strip()
    out, removed = [], 0
    for line in text.split("\n"):
        if mark not in line:
            out.append(line)
            continue
        prot = _PROTECT.sub(lambda m: m.group(1) + "\u2024", line)
        sents = re.split(r"(?<=[.!?।])\s+", prot)
        keep = [x.replace("\u2024", ".") for x in sents if mark not in x]
        removed += len(sents) - len(keep)
        if keep:
            out.append(" ".join(keep))
    t = "\n".join(out).strip()
    if removed:
        t += "\n\n" + NOTE.format(n=removed)
    return t, removed
