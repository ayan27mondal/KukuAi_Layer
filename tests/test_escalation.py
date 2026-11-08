from datetime import date
from lawyer import escalation as E

def codes(t): return {e.code for e in E.check_text(t)}
def level(t, code): return next(e.level for e in E.check_text(t) if e.code == code)

def test_criminal_is_a_hard_stop(): assert level("The landlord is threatening to call the police", "CRIMINAL") == "stop"
def test_hinglish_criminal(): assert "CRIMINAL" in codes("woh dhamki de raha hai")
def test_word_fir_does_not_match_first_or_confirm(): assert codes("first confirm the firm date") == set()
def test_domestic_violence_leads_with_safety_info_but_does_not_block():
    e = next(x for x in E.check_text("my husband beats me") if x.code == "DOMESTIC_VIOLENCE")
    assert e.level == "advise" and e.lead and "181" in e.message("en")
def test_family_is_advise_not_stop(): assert level("I want a divorce and custody of my son", "FAMILY_MATTER") == "advise"
def test_cheque_bounce_is_advise(): assert level("my cheque bounced, section 138 notice", "CHEQUE_BOUNCE") == "advise"
def test_court_stage(): assert level("I received a summons, hearing date is 5 Dec", "COURT_STAGE") == "stop"
def test_hindi_court(): assert "COURT_STAGE" in codes("मुझे अदालत का सम्मन मिला है")
def test_guarantee(): assert level("promise me I will win", "STRATEGY_OR_GUARANTEE") == "stop"
def test_crisis_stop_and_no_legal_footer():
    assert level("I want to end my life", "CRISIS") == "stop"
    assert "DLSA" not in E.Escalation("CRISIS", "stop").message("en")
def test_normal_problem_no_escalation(): assert codes("My landlord has not returned my deposit of Rs 20000") == set()
def test_hinglish_date_word_is_not_court(): assert "COURT_STAGE" not in codes("10 tarikh ko ghar khaali kiya")
def test_large_amount(): assert any(e.code == "LARGE_AMOUNT" for e in E.check_facts({"amount_inr": 2_000_000}))
def test_limitation():
    assert any(e.code == "LIMITATION_NEAR" for e in E.check_facts({"problem_type": "deposit", "event_date": "2020-01-01"}, date(2026, 11, 6)))
    assert not any(e.code == "LIMITATION_NEAR" for e in E.check_facts({"problem_type": "deposit", "event_date": "2026-09-01"}, date(2026, 11, 6)))
def test_llm_can_add_but_not_remove():
    found = [E.Escalation("CRIMINAL", "stop")]
    merged = E.merge(found, [E.from_llm("crisis"), E.from_llm("none"), E.from_llm("criminal")])
    assert [e.code for e in merged] == ["CRIMINAL", "CRISIS"]
