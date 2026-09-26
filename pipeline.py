"""Intake triage -> billing capture (accepted) or home care qualification (declined)."""

import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

import llm

DATA = Path(__file__).parent / "data"

# MedPAC Dec 2025: $16.0B FFS spend / 8.3M 30-day periods (2024). Periods per admission is an assumption.
AVG_PAYMENT_PER_PERIOD = 1928
AVG_PERIODS_PER_ADMISSION = 1.5

ADLS = ["bathing", "dressing", "toileting", "transferring", "eating", "continence"]
IADLS = ["meal preparation", "housekeeping", "medication reminders", "transportation", "shopping"]
DISCIPLINES = ["RN", "PT", "OT", "SLP"]


def load_referrals():
    return json.loads((DATA / "referrals.json").read_text())


def load_nurses():
    return pd.read_csv(DATA / "nurses.csv", parse_dates=["next_open_slot"])


def load_agencies():
    return pd.read_csv(DATA / "homecare_agencies.csv")


REF = json.loads((DATA / "reference.json").read_text())
NURSES = load_nurses()
AGENCIES = load_agencies()
SKILLS = sorted({s for row in NURSES.skills for s in row.split(";")})


def load_mock(referral_id):
    return json.loads((DATA / "mock" / f"{referral_id}.json").read_text())


def miles(zip_a, zip_b):
    a, b = REF["zips"].get(zip_a), REF["zips"].get(zip_b)
    if not a or not b:
        return float("inf")
    lat1, lon1, lat2, lon2 = map(math.radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def quote_verified(quote, text):
    norm = lambda s: " ".join(s.lower().split())
    return bool(quote) and norm(quote) in norm(text)


# ---------- LLM steps (live Bedrock with mock fallback) ----------

EXTRACT_SYSTEM = (
    "You are a home health intake clinician assistant. Extract facts from a hospital or SNF discharge packet. "
    "Use only information stated in the text. Every 'evidence' field must be an exact quote copied from the text. "
    "Use home health (aftercare/sequela) ICD-10 conventions. Respond with JSON only."
)

EXTRACT_SCHEMA = {
    "summary": "2-sentence clinical summary",
    "primary_diagnosis": {"name": "str", "icd10": "str", "evidence": "exact quote"},
    "diagnoses": [{"name": "str", "icd10": "str", "evidence": "exact quote"}],
    "homebound": {"value": "bool", "evidence": "exact quote"},
    "skilled_need": {"value": "bool", "evidence": "exact quote"},
    "services": [{"discipline": "one of " + "|".join(DISCIPLINES), "skills": "list, at most 2, from allowed skills"}],
    "face_to_face_documented": {"value": "bool", "evidence": "exact quote or empty string"},
    "adl_needs": "list from allowed ADL/IADL needs",
    "cognitive_impairment": "bool",
}


def extract(referral):
    user = (
        f"Allowed skills: {SKILLS}\nAllowed ADL/IADL needs: {ADLS + IADLS}\n"
        f"'diagnoses' = secondary diagnoses only (exclude the primary).\n"
        f"Return JSON matching this shape:\n{json.dumps(EXTRACT_SCHEMA, indent=1)}\n\n"
        f"DISCHARGE PACKET:\n{referral['discharge_summary']}"
    )
    return llm.complete_json(EXTRACT_SYSTEM, user)


BILLING_SYSTEM = (
    "You are a home health coding assistant helping a nurse and coder. Compare the full discharge summary with the "
    "intake nurse's summary (the only document the coder sees). List diagnoses documented in the discharge summary "
    "that are relevant to the home health plan of care but missing from the nurse summary, including ICD-10 "
    "combination/'with' conventions. Exclude any condition the nurse summary already mentions, even by abbreviation "
    "(e.g. 'CHF', 'hip ORIF', 'HTN'), unless the documented code should change (say so in why_it_matters). "
    "Never invent conditions; every evidence field must be an exact quote. "
    "Suggestions require clinician confirmation. Respond with JSON only."
)


def billing(referral, extraction):
    shape = {
        "missed": [{"name": "str", "icd10": "str", "evidence": "exact quote", "why_it_matters": "1 sentence"}],
        "coding_notes": ["str"],
        "nurse_query": "short message to the start-of-care nurse asking them to confirm and document",
    }
    user = (
        f"Return JSON matching: {json.dumps(shape)}\n\nDISCHARGE SUMMARY:\n{referral['discharge_summary']}\n\n"
        f"NURSE SUMMARY:\n{referral['nurse_summary']}\n\nEXTRACTED DIAGNOSES:\n"
        f"{json.dumps([extraction['primary_diagnosis']] + extraction['diagnoses'])}"
    )
    return llm.complete_json(BILLING_SYSTEM, user)


FAMILY_SYSTEM = (
    "You write warm, plain-language care plans for families of patients leaving the hospital. 6th-grade reading "
    "level. Say 'likely' or 'may qualify', never guarantee eligibility. Write in the family's preferred language. "
    "Lead with the home care options that can help now; mention any skilled follow-up after that. "
    "Respond with JSON only."
)


def family_message(referral, hc):
    shape = {"sms": "under 320 characters", "plan_markdown": "short plan with numbered next steps"}
    user = (
        f"Return JSON matching: {json.dumps(shape)}\nPreferred language: {referral['family_intake']['preferred_language']}\n"
        f"Patient first name: {referral['patient']['name'].split()[0]}\n"
        f"Family contact: {referral['family_intake']['contact']} ({referral['family_intake']['relationship']})\n"
        f"Home care options: {json.dumps(hc['programs'])}\nMatched agencies: {json.dumps(hc['agencies'])}\n"
        f"Skilled follow-up note: {hc.get('skilled_followup') or 'none'}"
    )
    return llm.complete_json(FAMILY_SYSTEM, user)


def family_message_template(referral, hc):
    first = referral["patient"]["name"].split()[0]
    contact = referral["family_intake"]["contact"].split()[0]
    top = hc["programs"][0] if hc["programs"] else None
    sms = f"Hi {contact}, this is the intake team. We couldn't start home health for {first}, but we found help"
    sms += f": {first} {top['status'].lower()} qualifies for {top['name']}. Tap for next steps." if top else ". Tap for next steps."
    steps = [f"{i}. **{p['name']}** ({p['status']}): {p['next_step']}" for i, p in enumerate(hc["programs"], 1)]
    if hc["agencies"]:
        a = hc["agencies"][0]
        steps.append(f"{len(steps) + 1}. **Private-pay backup:** {a['name']}, about ${a['hourly_rate']}/hr.")
    plan = f"### Care plan for {first}\n" + "\n".join(steps)
    if hc.get("skilled_followup"):
        plan += f"\n\n**Important:** {hc['skilled_followup']}"
    return {"sms": sms, "plan_markdown": plan}


def _run_step(name, live, live_fn, mock_fn, log):
    if live:
        try:
            t = time.time()
            out = live_fn()
            log.append(f"{name}: live model ({time.time() - t:.1f}s)")
            return out
        except Exception as e:  # noqa: BLE001 - demo must never crash
            log.append(f"{name}: live call failed ({type(e).__name__}: {str(e)[:120]}); used mock")
    else:
        log.append(f"{name}: mock")
    return mock_fn()


# ---------- Rules ----------

def match_staff(referral, extraction):
    discharge = datetime.fromisoformat(referral["discharge_datetime"])
    zip_ = referral["patient"]["zip"]
    services = extraction.get("services", [])
    soc = next((s["discipline"] for s in services if s["discipline"] == "RN"), services[0]["discipline"] if services else None)
    results = []
    for svc in services:
        disc, skills = svc["discipline"], set(svc.get("skills", []))
        window = timedelta(hours=48) if disc == soc else timedelta(days=5)
        deadline = discharge + window
        pool = NURSES[NURSES.license == disc].copy()
        pool["miles"] = pool.home_zip.astype(str).map(lambda z: miles(z, zip_))
        pool["has_skills"] = pool.skills.map(lambda s: skills <= set(s.split(";")))
        qualified = pool[pool.has_skills & (pool.miles <= pool.max_radius_miles)]
        ok = qualified[qualified.next_open_slot <= deadline].sort_values("next_open_slot")
        label = f"{disc} ({'start of care, 48 hrs' if disc == soc else 'within 5 days'})"
        if len(ok):
            n = ok.iloc[0]
            results.append({"service": label, "ok": True, "clinician": n["name"], "miles": round(n.miles, 1),
                            "slot": n.next_open_slot.strftime("%a %b %d %H:%M"), "detail": f"Skills: {', '.join(sorted(skills)) or 'any'}"})
        elif len(qualified):
            n = qualified.sort_values("next_open_slot").iloc[0]
            results.append({"service": label, "ok": False, "clinician": n["name"], "miles": round(n.miles, 1),
                            "slot": n.next_open_slot.strftime("%a %b %d %H:%M"),
                            "detail": f"Nearest qualified {disc} first free {n.next_open_slot:%a %b %d %H:%M}, after the deadline ({deadline:%a %b %d %H:%M})"})
        else:
            results.append({"service": label, "ok": False, "clinician": None, "miles": None, "slot": None,
                            "detail": f"No {disc} with {', '.join(sorted(skills)) or 'required skills'} within travel radius"})
    return results


def triage(referral, extraction):
    checks = []
    payer = REF["payers"].get(referral["payer_id"])
    if not payer or not payer["contracted"]:
        checks.append(("Insurance", "fail", f"{payer['name'] if payer else referral['payer_id']} is out of network", "insurance"))
    elif payer["prior_auth"]:
        checks.append(("Insurance", "fix", f"{payer['name']}: eligible, prior authorization required", "prior_auth"))
    else:
        checks.append(("Insurance", "pass", f"{payer['name']}: eligible, no auth needed", None))

    sn, hb, f2f = extraction["skilled_need"], extraction["homebound"], extraction["face_to_face_documented"]
    checks.append(("Skilled need", "pass" if sn["value"] else "fail", sn["evidence"] or "Not documented", None if sn["value"] else "clinical"))
    checks.append(("Homebound", "pass" if hb["value"] else "fail", hb["evidence"] or "Not documented", None if hb["value"] else "clinical"))
    checks.append(("Face-to-face", "pass" if f2f["value"] else "fix", f2f["evidence"] or "Not documented", None if f2f["value"] else "f2f"))

    staffing = match_staff(referral, extraction)
    if staffing:
        all_ok = all(s["ok"] for s in staffing)
        checks.append(("Staffing", "pass" if all_ok else "fail",
                       "Every discipline covered in time" if all_ok else "; ".join(s["detail"] for s in staffing if not s["ok"]),
                       None if all_ok else "staffing"))

    statuses = [c[1] for c in checks]
    decision = "decline" if "fail" in statuses else "fixable" if "fix" in statuses else "accept"
    reason = next((c[3] for c in checks if c[1] == "fail"), None)
    return {"decision": decision, "decline_reason": reason, "payer": payer,
            "checks": [dict(zip(["check", "status", "detail", "code"], c)) for c in checks], "staffing": staffing}


def fix_actions(referral, tri):
    p, codes = referral["patient"], {c["code"] for c in tri["checks"] if c["status"] == "fix"}
    actions = []
    if "f2f" in codes:
        actions.append({"title": "Request face-to-face documentation", "to": f"Discharge planner, {referral['referring_facility']}",
                        "body": f"Hi, we can accept {p['name']} (ref {referral['id']}) and have a nurse scheduled within 48 hours. "
                                "The face-to-face encounter note isn't in the packet. Could the attending or PCP document it "
                                "(date, findings supporting homebound status and skilled need)? We'll hold the slot for 4 hours."})
    if "prior_auth" in codes:
        actions.append({"title": "Submit prior authorization", "to": tri["payer"]["name"],
                        "body": f"Prior auth request for {p['name']}, age {p['age']}, discharge {referral['discharge_datetime'][:10]}. "
                                "Requesting skilled nursing and therapy visits per attached orders. Clinical summary and "
                                "homebound evidence attached from discharge packet."})
    return actions


def home_care(referral, extraction, tri):
    fi, p = referral["family_intake"], referral["patient"]
    needs = extraction.get("adl_needs", [])
    adls = [n for n in needs if n in ADLS]
    iadls = [n for n in needs if n in IADLS]
    heavy = len(adls) >= 2 or extraction.get("cognitive_impairment")
    county = REF["zips"].get(p["zip"], {}).get("county", "your")
    programs, ruled_out = [], []

    def add(ok, name, status, why, step, no_reason):
        (programs.append({"name": name, "status": status, "why": why, "next_step": step}) if ok
         else ruled_out.append({"name": name, "reason": no_reason}))

    add(fi["medi_cal"] and bool(needs), "IHSS (In-Home Supportive Services)", "Likely",
        f"On Medi-Cal and needs help with {', '.join(needs)}.",
        f"Apply with {county} County IHSS. A family member can enroll as the paid caregiver.",
        "Requires Medi-Cal" if not fi["medi_cal"] else "No daily-living needs documented")
    add(fi["medi_cal"] and p["age"] >= 65 and heavy, "Medi-Cal MSSP care management", "Possible",
        "Age 65+ on Medi-Cal with high care needs.", "Ask the county Area Agency on Aging for an MSSP screening.",
        "Requires Medi-Cal, age 65+, and high care needs")
    vet = fi["wartime_veteran"] or fi["surviving_spouse_of_veteran"]
    add(vet and bool(adls), "VA Aid & Attendance", "Possible",
        f"Wartime veteran who needs help with {', '.join(adls)}. Income and asset limits apply.",
        "Contact a county Veterans Service Officer (free) to file VA Form 21-2680.",
        "Requires wartime service (or surviving spouse) and help with daily activities")
    pace = next((name for name, zips in REF["pace_areas"].items() if p["zip"] in zips), None)
    add(p["age"] >= 55 and pace and heavy, pace or "PACE", "Possible",
        "Age 55+, lives in a PACE service area, needs nursing-home level help.",
        f"Call {pace} for an intake assessment." if pace else "",
        "Requires age 55+, PACE service area, and nursing-home level needs")
    add(fi["ltc_insurance"] and heavy, "Long-term care insurance benefit", "Likely",
        f"Has a policy and needs help with {len(adls)} daily activities (most policies trigger at 2).",
        "Call the insurer to open a claim; ask about the elimination period.",
        "No policy, or fewer than 2 daily activities")

    hours = min(40, 4 * len(adls) + 2 * len(iadls)) or 4
    agencies = AGENCIES[AGENCIES.zips_served.str.contains(p["zip"])].copy()
    if fi["ltc_insurance"]:
        agencies = agencies.sort_values("accepts_ltc_insurance", ascending=False)
    agencies = [{"name": a["name"], "hourly_rate": int(a.hourly_rate), "languages": a.languages.replace(";", ", "),
                 "accepts_ltc_insurance": bool(a.accepts_ltc_insurance), "est_monthly": round(a.hourly_rate * hours * 4.33, -1)}
                for _, a in agencies.iterrows()]

    followup = None
    if extraction["skilled_need"]["value"] and tri["decline_reason"] in ("staffing", "insurance"):
        followup = ("This patient still needs skilled home health. Tell the discharge planner right away so another "
                    "agency (in-network or with coverage in this area) can accept the skilled referral.")
    return {"needs": needs, "adls": adls, "iadls": iadls, "est_hours_week": hours, "programs": programs,
            "ruled_out": ruled_out, "agencies": agencies, "skilled_followup": followup}


# ---------- Orchestration ----------

def run(referral, live=False):
    t0, log = time.time(), []
    mock = load_mock(referral["id"])
    ext = _run_step("Extraction", live, lambda: extract(referral), lambda: mock["extraction"], log)
    tri = triage(referral, ext)
    out = {"extraction": ext, "triage": tri, "log": log}
    if tri["decision"] in ("accept", "fixable"):
        out["billing"] = _run_step("Billing capture", live, lambda: billing(referral, ext),
                                   lambda: mock.get("billing", {"missed": [], "coding_notes": [], "nurse_query": ""}), log)
        out["actions"] = fix_actions(referral, tri)
    else:
        hc = home_care(referral, ext, tri)
        out["home_care"] = hc
        out["family"] = _run_step("Family care plan", live, lambda: family_message(referral, hc),
                                  lambda: family_message_template(referral, hc), log)
    for d in [ext["primary_diagnosis"]] + ext.get("diagnoses", []) + out.get("billing", {}).get("missed", []):
        d["verified"] = quote_verified(d.get("evidence", ""), referral["discharge_summary"])
    out["seconds"] = round(time.time() - t0, 1)
    return out
