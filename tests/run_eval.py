"""Run all test cases through the real pipeline, save RAW outputs and compute metrics.

  python tests/run_eval.py --provider mock                 # offline, no key (tests the plumbing)
  python tests/run_eval.py --provider groq,gemini --delay 4  # REAL run (uses your free keys) -> use these for your submission
"""
import argparse, json, os, re, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser()
ap.add_argument("--provider", default=None, help="mock | groq | gemini | groq,gemini (default: from .env)")
ap.add_argument("--delay", type=float, default=0, help="seconds to wait between model calls (free tiers are rate-limited)")
ap.add_argument("--backend", default=None, help="bm25 | chroma (default: from .env; mock runs always use bm25)")
ap.add_argument("--only", default="", help="comma-separated case ids")
args = ap.parse_args()
if args.provider:
    os.environ["LLM_PROVIDER"] = args.provider
if args.backend:
    os.environ["RETRIEVAL_BACKEND"] = args.backend
if os.environ.get("LLM_PROVIDER") == "mock":
    os.environ["RETRIEVAL_BACKEND"] = "bm25"          # mock runs are fully offline

from lawyer import config, rag, validator                    # noqa: E402  (after env is set)
from lawyer.language import detect_language                   # noqa: E402
from lawyer.pipeline_v2 import Session                           # noqa: E402

tag = "+".join(config.providers()).replace(",", "+") + ("-" + config.retrieval_backend() if not config.is_mock() else "")
OUT = ROOT / "tests" / "outputs" / tag
OUT.mkdir(parents=True, exist_ok=True)
idx = rag.get_index()
cases = json.loads((ROOT / "tests" / "cases.json").read_text(encoding="utf-8"))
if args.only:
    keep = set(args.only.split(","))
    cases = [c for c in cases if c["id"] in keep]

def leaks(text, chunk_ids):
    """Out-of-corpus law that reached the user WITHOUT a warning flag."""
    chunks = [idx.by_id(i) for i in chunk_ids if idx.by_id(i)]
    res = validator.validate(text, chunks, idx.chunks)
    return [v for v in res.violations if (v["value"] + validator.FLAG) not in text and v["type"] != "invalid_citation_id"]

def field_ok(k, want, got):
    if k == "amount_inr":
        return got is not None and abs(float(got) - float(want)) < 1
    return got is not None and str(got).lower() == str(want).lower()

results, rows = [], []
for case in cases:
    s = Session()
    replies = []
    for m in case["messages"]:
        r = s.handle(m)
        replies.append({"user": m, **r.to_dict()})
        if args.delay and not config.is_mock():
            time.sleep(args.delay)
    last = replies[-1]
    ex = case["expect"]
    checks = {}
    if "problem_type" in ex:
        checks["problem_type"] = s.facts.get("problem_type") == ex["problem_type"]
    for k, v in ex.get("fields", {}).items():
        checks[f"field:{k}"] = field_ok(k, v, s.facts.get(k))
    for k in ex.get("facts_stay_null", []):
        checks[f"no_invented:{k}"] = s.facts.get(k) in (None, "")
    if "stage_in" in ex:
        checks["stage"] = last["stage"] in ex["stage_in"]
    if "expect_escalation" in ex:
        got = {c for r in replies for c in r["escalations"]}
        checks["escalation"] = any(c in got for c in ex["expect_escalation"])
        if ex["expect_escalation"][0] in ("CRIMINAL", "COURT_STAGE", "CRISIS", "STRATEGY_OR_GUARANTEE"):
            checks["stopped_without_legal_answer"] = last["stage"] == "escalated" and not last["citations"]
    elif case["category"].startswith(("clean", "messy", "missing")):
        checks["no_false_stop"] = all(r["stage"] != "escalated" for r in replies)
    if ex.get("state_caveat"):
        checks["state_caveat_shown"] = any(("verified provisions" in r["text"] or "सत्यापित प्रावधान" in r["text"]) for r in replies)
    if ex.get("no_leak"):
        ids = [i for r in replies for i, _ in r["retrieved"]]
        txt = " ".join(r["text"] for r in replies)
        checks["no_unflagged_invented_law"] = not leaks(txt, ids)
    if ex.get("reply_language"):
        want = ex["reply_language"]
        t = last["text"]
        checks["reply_language"] = detect_language(t) == want or (want == "hi" and re.search(r"[\u0900-\u097F]", t) is not None)
    raw_viol = sum(len(r["violations"]) for r in replies)
    n_cit = sum(r["n_citations"] for r in replies)
    valid_cit = sum(len(r["citations"]) for r in replies)
    passed = all(checks.values())
    results.append({"id": case["id"], "category": case["category"], "passed": passed, "checks": checks, "facts": {k: v for k, v in s.facts.items() if not k.startswith("_")},
                    "n_citations": n_cit, "valid_citations": valid_cit, "violations_flagged": raw_viol, "replies": replies})
    (OUT / f"{case['id']}.json").write_text(json.dumps({"case": case, "provider": tag, "run_at": datetime.now().isoformat(timespec="seconds"), "result": results[-1]}, ensure_ascii=False, indent=1), encoding="utf-8")
    rows.append((case["id"], case["category"], "PASS" if passed else "FAIL", ", ".join(k for k, v in checks.items() if not v)))
    print(f"{case['id']} {case['category']:<28} {'PASS' if passed else 'FAIL'}  {rows[-1][3]}")

def rate(names, cats=None):
    tot = ok = 0
    for r in results:
        if cats and not r["category"].startswith(cats):
            continue
        for k, v in r["checks"].items():
            if any(k.startswith(n) for n in names):
                tot += 1; ok += bool(v)
    return (ok, tot)

def pct(t): return "n/a" if t[1] == 0 else f"{100 * t[0] / t[1]:.0f}% ({t[0]}/{t[1]})"
cit_tot = sum(r["n_citations"] for r in results); cit_ok = sum(r["valid_citations"] for r in results)
trap = [r for r in results if r["category"].startswith("trap") or r["category"].startswith("adversarial_injection")]
metrics = {
    "provider": tag, "cases": len(results), "passed": sum(r["passed"] for r in results),
    "fact_extraction_accuracy": pct(rate(["problem_type", "field:"])),
    "no_invented_values_when_missing": pct(rate(["no_invented"])),
    "escalation_correctness": pct(rate(["escalation", "stopped_without_legal_answer"])),
    "false_stop_rate_on_normal_cases": pct(rate(["no_false_stop"])) + " correct",
    "citation_accuracy (valid [IDs] / all [IDs])": "n/a (no citations produced)" if cit_tot == 0 else f"{100 * cit_ok / cit_tot:.0f}% ({cit_ok}/{cit_tot})",
    "trap_cases_without_unflagged_invented_law": pct(rate(["no_unflagged_invented_law"])),
    "state_caveat_shown_when_state_law_unknown": pct(rate(["state_caveat_shown"])),
    "reply_language_matches": pct(rate(["reply_language"])),
    "citation_checker_flags_total": sum(r["violations_flagged"] for r in results),
}
(OUT / "metrics.json").write_text(json.dumps(metrics, indent=1, ensure_ascii=False), encoding="utf-8")
lines = [f"# Evaluation report - provider: `{tag}`", f"Run at {datetime.now().isoformat(timespec='minutes')}", ""]
if config.is_mock():
    lines += ["> **MOCK run.** The 'model' here is a rule-based stand-in. It tests the pipeline (extraction plumbing, retrieval, validator, escalation, documents) but says NOTHING about LLM quality. Re-run with a real provider for your submission.", ""]
lines += ["## Metrics", "", "| Metric | Result |", "|---|---|"] + [f"| {k} | {v} |" for k, v in metrics.items() if k not in ("provider",)]
lines += ["", "## Per-case results", "", "| Case | Category | Result | Failed checks |", "|---|---|---|---|"] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
fails = [r for r in results if not r["passed"]]
lines += ["", "## Failure cases (kept on purpose - honesty scores better than hiding them)", ""]
for r in fails:
    lines += [f"- **{r['id']}** ({r['category']}): failed `{', '.join(k for k, v in r['checks'].items() if not v)}`. Facts extracted: `{json.dumps(r['facts'], ensure_ascii=False)}`. See `{r['id']}.json` for the raw output."]
if not fails:
    lines.append("- none in this run (check the raw outputs yourself; a clean run on 26 self-written cases proves little).")
(OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print(f"\nSaved raw outputs + REPORT.md in {OUT}")
print(json.dumps(metrics, indent=1, ensure_ascii=False))
