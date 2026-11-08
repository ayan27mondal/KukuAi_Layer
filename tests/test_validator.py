"""Run:  python -m pytest tests -q"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lawyer import rag, validator

idx = rag.get_index()
def chunks(*ids): return [idx.by_id(i) for i in ids]

def test_fake_section_is_flagged():
    r = validator.validate("You can claim under Section 999 of the Consumer Protection Act, 2019 [CPA2019-S69-LIMITATION].", chunks("CPA2019-S69-LIMITATION"), idx.chunks)
    assert any(v["type"] == "unknown_section" for v in r.violations)
    assert "Section 999" + validator.FLAG in r.text

def test_real_section_in_retrieved_chunk_is_kept():
    r = validator.validate("File within two years (Section 69 of the Consumer Protection Act, 2019) [CPA2019-S69-LIMITATION].", chunks("CPA2019-S69-LIMITATION"), idx.chunks)
    assert r.violations == [] and r.cited_ids == ["CPA2019-S69-LIMITATION"]

def test_section_not_in_retrieved_context_is_flagged_even_if_in_corpus():
    # Section 69 exists in the corpus but was NOT given to the model for this answer
    r = validator.validate("Section 69 applies.", chunks("CPA2019-S35-FILING"), idx.chunks)
    assert any(v["type"] == "unknown_section" for v in r.violations)

def test_invented_chunk_id_is_removed():
    r = validator.validate("Your claim is strong [MADE-UP-ID].", chunks("CPA2019-S69-LIMITATION"), idx.chunks)
    assert "[MADE-UP-ID]" not in r.text and r.invalid_ids == ["MADE-UP-ID"] and r.citation_accuracy == 0

def test_case_law_is_always_flagged():
    r = validator.validate("In Sharma v. Union of India the court awarded triple damages. See also AIR 1999 SC 123.", chunks("CPA2019-S69-LIMITATION"), idx.chunks)
    assert sum(v["type"] == "case_law" for v in r.violations) >= 1

def test_unknown_act_is_flagged_known_act_is_not():
    bad = validator.validate("The Fictional Tenants Protection Act, 2031 gives you triple the deposit.", chunks("MTA2021-S11-DEPOSIT-CAP"), idx.chunks)
    assert any(v["type"] == "unknown_act" for v in bad.violations)
    good = validator.validate("The Model Tenancy Act, 2021 caps deposits [MTA2021-S11-DEPOSIT-CAP].", chunks("MTA2021-S11-DEPOSIT-CAP"), idx.chunks)
    assert good.violations == []

def test_citation_accuracy_math():
    r = validator.validate("A [CPA2019-S69-LIMITATION]. B [NOPE-123].", chunks("CPA2019-S69-LIMITATION"), idx.chunks)
    assert r.n_citations == 2 and len(r.cited_ids) == 1 and r.citation_accuracy == 0.5

def test_strip_removes_flagged_sentences_but_keeps_good_ones():
    r = validator.validate("The deposit cap is two months [MTA2021-S11-DEPOSIT-CAP]. In Sharma v. Union of India the court awarded triple damages under Section 88 of the Tenant Safety Act, 2015.",
                           chunks("MTA2021-S11-DEPOSIT-CAP"), idx.chunks)
    text, n = validator.strip_flagged(r.text)
    assert n == 1 and "Sharma" not in text and "Section 88" not in text and "two months" in text and "removed 1 statement" in text
