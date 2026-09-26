import os

import pandas as pd
import streamlit as st

import llm
import pipeline as p

APP_NAME = "Oikos"
st.set_page_config(page_title=f"{APP_NAME}: home health intake", layout="wide")

BADGE = {"accept": ":green-background[ACCEPT]", "fixable": ":orange-background[FIXABLE]", "decline": ":red-background[DECLINE]"}
ICON = {"pass": "✅", "fix": "🟠", "fail": "❌"}
REASON = {"staffing": "No nurse in time", "insurance": "Out of network", "clinical": "No skilled need", None: ""}

referrals = p.load_referrals()
by_id = {r["id"]: r for r in referrals}
st.session_state.setdefault("results", {})

with st.sidebar:
    st.header(APP_NAME)
    st.caption("Every referral gets a next step.")
    has_creds = bool(os.getenv("OPENAI_API_KEY") or os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE"))
    live = st.toggle("Live model (GPT-5.6 Terra on Bedrock)", value=has_creds)
    if live and st.button("Test Bedrock connection"):
        try:
            llm.reset_client()
            st.success(f"Model replied: {llm.ping()}")
        except Exception as e:  # noqa: BLE001
            st.error(f"{type(e).__name__}: {str(e)[:200]}")
    st.caption("Falls back to cached outputs if a live call fails. All patient data is synthetic.")
    if st.button("Run agent on all referrals", type="primary", width="stretch"):
        from concurrent.futures import ThreadPoolExecutor

        with st.spinner("Triaging referrals in parallel..."):
            with ThreadPoolExecutor(max_workers=5) as pool:
                for r, res in zip(referrals, pool.map(lambda r: p.run(r, live=live), referrals)):
                    st.session_state.results[r["id"]] = res
    if st.button("Reset", width="stretch"):
        st.session_state.results = {}

results = st.session_state.results

st.title(f"{APP_NAME}: home health intake agent")
st.markdown("**Accepted patients get billed fully. Rejected patients still get a care plan.**")

tab_overview, tab_queue, tab_detail, tab_impact = st.tabs(["Overview", "Referral queue", "Referral detail", "Impact"])

with tab_overview:
    st.markdown("Hospitals and SNFs send more patients home every year. Agencies turn most of them away, "
                "bill the ones they accept incompletely, and send the rest home with no next step.")

    st.subheader("The market")
    c = st.columns(4)
    c[0].metric("Medicare-certified agencies", "12,000+")
    c[1].metric("Medicare patients / yr", "2.7M")
    c[2].metric("Medicare spend / yr", "$16.0B")
    c[3].metric("Medicare margin vs. all-payer", "21.2% vs 5.0%")
    st.caption("MedPAC, Dec 2025 (2024 data). Most agencies are small independents, and Medicare Advantage and Medicaid "
               "pay far less, so which patients an agency accepts decides whether it makes money.")

    st.subheader("The breakdown")
    c = st.columns(4)
    c[0].metric("Home health referral acceptance", "~24%", "down from ~46% in 2019", delta_color="inverse")
    c[1].metric("Faster responders win more referrals", "+22%", "WellSky, self-reported")
    c[2].metric("Referrals, year over year", "+4.6%")
    c[3].metric("Comorbidity burden vs 2019", "+34%")
    st.caption("Acceptance rate: WellSky's 2023 Evolution of Care Report (CarePort network, first-party). "
               "Response-speed advantage: WellSky, Mar 2026. "
               "Referral growth and comorbidity (Van Walraven index): WellSky network data, Dec 2025.")

    st.subheader("Where the money and patients leak")
    c = st.columns(4)
    leaks = [
        ("1. Slow manual screening", "Coordinators read long discharge packets by hand. WellSky reports agencies who "
         "respond first are ~22% more likely to secure the placement — Oikos plans to verify this independently "
         "with a pilot agency."),
        ("2. Nurse capacity", "Medicare requires the first visit within 48 hours of referral or discharge "
         "(42 CFR 484.55), so agencies decline referrals they can't staff in time."),
        ("3. Incomplete billing", "Coders see only the intake nurse's short summary, so documented comorbidities never "
         "reach the claim."),
        ("4. Dead-end rejections", "Declined patients get no next step, even when they qualify for IHSS, VA benefits, "
         "PACE, or long-term care insurance."),
    ]
    for col, (title, body) in zip(c, leaks):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.write(body)

    st.subheader(f"What {APP_NAME} does")
    c = st.columns(3)
    for col, (title, body) in zip(c, [
        ("Triage in seconds", "Reads the discharge packet, checks insurance, homebound status, skilled need and paperwork, "
         "and matches a real nurse by license, skills, distance and schedule."),
        ("Bill every accepted patient fully", "Surfaces diagnoses missing from the nurse summary, with chart quotes, "
         "for the nurse and coder to confirm."),
        ("Give every rejection a next step", "Checks home care programs and private-pay agencies, then adds a note "
         "to the file for the hospital discharge planner to share with the family."),
    ]):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.write(body)

    with st.expander("Sources"):
        st.markdown(
            "- [MedPAC, Home health update, Dec 2025](https://www.medpac.gov/wp-content/uploads/2025/12/Tab-H-HHA-update-Dec-2025.pdf): "
            "agencies, users, spend, margins\n"
            "- [WellSky, 2023 Evolution of Care Report, via Home Health Care News](https://homehealthcarenews.com/2023/07/referral-rejection-rates-patient-complexity-in-home-health-care-reaching-all-time-highs/): "
            "home health referral rejection rose from 54% (2019) to 76% (Dec 2022), avg. referral response time "
            "~24 min — first-party CarePort network data\n"
            "- [Home Health Care News, Dec 2025](https://homehealthcarenews.com/2025/12/home-health-referrals-increase-4-6-year-over-year-as-patient-complexity-rises/): "
            "referral growth and patient complexity (WellSky data)\n"
            "- [Fisher et al., J Am Geriatr Soc](https://www.sciencedirect.com/science/article/pii/S1525861020310513): "
            "peer-reviewed Medicare claims analysis; home health referral *fulfillment* fell from 66% (2016) to 59% "
            "(2022) — a related but distinct metric from agency acceptance rate\n"
            "- [42 CFR 484.55(a)(1)](https://www.law.cornell.edu/cfr/text/42/484.55): initial assessment within 48 hours "
            "of referral or return home\n"
            "- [McKnight's Home Care](https://www.mcknightshomecare.com/news/home-health-referrals-increase-but-acceptances-decline-report-finds/): "
            "referrals up, acceptances down\n"
            "- [WellSky, \"WellSky Centralizes Post-Acute Referral Intake With Intelligent AI Integration\" (Mar 2026)]"
            "(https://wellsky.com/wellsky-centralizes-post-acute-referral-intake-with-intelligent-ai-integration/): "
            "\"providers who respond first are 22% more likely to secure patient placement\" — WellSky's own data, "
            "no published methodology, sample size, or study design, from a release announcing WellSky's own AI referral "
            "product. Directionally useful but self-interested; no independent study corroborates the specific magnitude. "
            "Oikos plans to measure this directly with a pilot agency before treating it as verified.\n"
            "- Note: an earlier version of this page cited a \"77% of providers cite staffing\" statistic sourced to "
            "a vendor blog; that figure traces to [ANCOR's 2023 direct-support workforce survey](https://www.ancor.org/wp-content/uploads/2023/12/2023-State-of-Americas-Direct-Support-Workforce-Crisis_Final.pdf), "
            "which covers IDD/direct-support providers, not home health — removed as a citation error."
        )

with tab_queue:
    rows = []
    for r in referrals:
        res = results.get(r["id"])
        t = res["triage"] if res else None
        next_step = ""
        if res and t["decision"] == "decline":
            next_step = f"Home care plan: {len(res['home_care']['programs'])} programs"
        elif res:
            next_step = f"{len(res['billing']['missed'])} missed diagnoses surfaced"
            if res["actions"]:
                next_step = f"{len(res['actions'])} fix actions drafted; " + next_step
        rows.append({"Referral": r["id"], "Patient": f"{r['patient']['name']}, {r['patient']['age']}{r['patient']['sex']}",
                     "Source": f"{r['facility_type']}: {r['referring_facility'].replace(' (synthetic)', '')}",
                     "Payer": p.REF["payers"][r["payer_id"]]["type"], "Zip": r["patient"]["zip"],
                     "Manual decision": f"{r['manual']['decision']} ({r['manual']['minutes_to_decision'] // 60}h{r['manual']['minutes_to_decision'] % 60:02d}m)",
                     "Agent decision": t["decision"].upper() if t else "not run",
                     "Reason": REASON[t["decline_reason"]] if t else "", "Next step": next_step})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if not results:
        st.info("Click **Run agent on all referrals** in the sidebar.")

with tab_detail:
    rid = st.selectbox("Referral", list(by_id), format_func=lambda i: f"{i}: {by_id[i]['patient']['name']}")
    r = by_id[rid]
    if st.button("Run agent on this referral"):
        with st.spinner("Reading discharge packet..."):
            results[rid] = p.run(r, live=live)
    res = results.get(rid)

    left, right = st.columns([2, 3])
    with left:
        st.subheader("Incoming referral")
        st.markdown(f"**{r['patient']['name']}**, {r['patient']['age']}{r['patient']['sex']} · zip {r['patient']['zip']}  \n"
                    f"{r['referring_facility']} · discharge {r['discharge_datetime'].replace('T', ' ')}  \n"
                    f"Payer: {p.REF['payers'][r['payer_id']]['name']}")
        with st.expander("Discharge summary", expanded=not res):
            st.text(r["discharge_summary"])
        with st.expander("Nurse intake summary (what the coder sees today)"):
            st.text(r["nurse_summary"])
        st.caption(f"Manual process: {r['manual']['note']}")

    with right:
        if not res:
            st.info("Run the agent to see the decision.")
        else:
            t, ext = res["triage"], res["extraction"]
            st.subheader(f"Decision: {BADGE[t['decision']]}")
            st.caption(f"Decided in {res['seconds']}s · " + " · ".join(res["log"]))
            st.markdown(f"_{ext['summary']}_")
            for c in t["checks"]:
                st.markdown(f"{ICON[c['status']]} **{c['check']}**: {c['detail']}")
            if t["staffing"]:
                st.markdown("**Nurse matching**")
                st.dataframe(pd.DataFrame([{"Service": s["service"], "Clinician": s["clinician"] or "-",
                                            "Miles": s["miles"], "First slot": s["slot"] or "-",
                                            "Covered": "yes" if s["ok"] else "no"} for s in t["staffing"]]),
                             hide_index=True, width="stretch")

            if t["decision"] == "fixable":
                st.markdown("### Recover this referral")
                for a in res["actions"]:
                    with st.container(border=True):
                        st.markdown(f"**{a['title']}** → {a['to']}")
                        st.write(a["body"])
                        st.button("Send (demo)", key=f"send-{rid}-{a['title']}")

            if "billing" in res:
                b = res["billing"]
                st.markdown(f"### Billing capture: {len(b['missed'])} diagnoses missing from the nurse summary")
                st.dataframe(pd.DataFrame([{"Diagnosis": m["name"], "ICD-10": m["icd10"], "Why it matters": m["why_it_matters"],
                                            "Evidence (from chart)": m["evidence"], "Quote verified": "✅" if m["verified"] else "⚠️"}
                                           for m in b["missed"]]), hide_index=True, width="stretch")
                for n in b["coding_notes"]:
                    st.markdown(f"- {n}")

                pdgm = b.get("pdgm")
                if pdgm and not pdgm["applicable"]:
                    st.caption(f"PDGM billing estimate: not applicable — {pdgm['reason']}")
                elif pdgm and not pdgm["tier"]:
                    st.caption(f"PDGM billing estimate: \\$0 — {pdgm['note']}")
                elif pdgm:
                    st.markdown(f"**Estimated PDGM impact: +\\${pdgm['per_period']:,}/30-day period** "
                                f"(~\\${pdgm['per_admission']:,}/admission)")
                    st.caption(f"{pdgm['tier'].title()} comorbidity adjustment from: {', '.join(pdgm['subgroups'])}. "
                              "Illustrative estimate only — uses the CY2026 base rate and example adjustment "
                              "percentages; actual payment depends on the full PDGM case-mix calculation (admission "
                              "source, timing, clinical group, functional level), which this demo does not model.")

                st.markdown("**Query to start-of-care nurse**")
                st.info(b["nurse_query"])
                st.caption("Suggestions only. The nurse confirms and the coder codes. Nothing is auto-billed.")

            if "home_care" in res:
                hc, note = res["home_care"], res["discharge_note"]
                st.markdown("### Home care qualification")
                if hc["skilled_followup"]:
                    st.warning(hc["skilled_followup"])
                st.markdown(f"Needs help with: **{', '.join(hc['needs']) or 'none documented'}** · est. {hc['est_hours_week']} hrs/week")
                for prog in hc["programs"]:
                    with st.container(border=True):
                        st.markdown(f"**{prog['name']}** · {prog['status']}  \n{prog['why']}  \n→ {prog['next_step']}")
                if hc["agencies"]:
                    st.markdown("**Matched private-pay agencies**")
                    st.dataframe(pd.DataFrame([{"Agency": a["name"], "$/hr": a["hourly_rate"], "Est. $/month": a["est_monthly"],
                                                "LTC insurance": "yes" if a["accepts_ltc_insurance"] else "no",
                                                "Languages": a["languages"]} for a in hc["agencies"]]),
                                 hide_index=True, width="stretch")
                with st.expander("Checked, not a fit"):
                    for x in hc["ruled_out"]:
                        st.markdown(f"- **{x['name']}**: {x['reason']}")
                st.markdown(f"### Note added to file for {r['referring_facility']}'s discharge planner")
                with st.container(border=True):
                    st.markdown(note["note"].replace("$", "\\$"))
                st.caption("Oikos does not contact patients or families directly — only the hospital discharge "
                           "planner may do that. Eligibility is an estimate from general program rules; the county, "
                           "VA, or insurer makes the final decision.")

with tab_impact:
    done = [by_id[i] for i in results]
    if done:
        dec = {i: results[i]["triage"]["decision"] for i in results}
        manual_acc = sum(r["manual"]["decision"] == "accept" for r in done)
        agent_acc = sum(d in ("accept", "fixable") for d in dec.values())
        declined = [i for i, d in dec.items() if d == "decline"]
        routed = sum(bool(results[i]["home_care"]["programs"] or results[i]["home_care"]["agencies"]) for i in declined)
        missed = sum(len(results[i].get("billing", {}).get("missed", [])) for i in results)
        manual_min = sorted(r["manual"]["minutes_to_decision"] for r in done)[len(done) // 2]
        c = st.columns(4)
        c[0].metric("Accepted (skilled)", f"{agent_acc}/{len(done)}", f"+{agent_acc - manual_acc} vs manual")
        c[1].metric("Declined patients with a care plan", f"{routed}/{len(declined)}", "manual: 0")
        c[2].metric("Missed diagnoses surfaced", missed)
        c[3].metric("Time to decision (slowest)", f"{max(r['seconds'] for r in results.values()):.0f}s",
                    f"vs {manual_min // 60}h{manual_min % 60:02d}m manual median", delta_color="off")
    else:
        st.info("Run the agent first.")

    st.markdown("### Scale it to one agency (illustrative)")
    a, b, c = st.columns(3)
    monthly = a.slider("Referrals per month", 50, 1000, 200, 50)
    base_rate = b.slider("Current acceptance rate", 0.1, 0.8, 0.35, 0.05)
    recover = c.slider("Share of eligible declines recovered", 0.0, 0.5, 0.15, 0.05)
    d, e, f = st.columns(3)
    eligible_share = d.slider("Declines that are insurance-eligible", 0.1, 0.9, 0.45, 0.05)
    hc_share = e.slider("Declines placed in home care", 0.0, 0.5, 0.2, 0.05)
    fee = f.number_input("Referral fee per private-pay placement ($)", 0, 2000, 300, 50)
    declines = monthly * (1 - base_rate)
    recovered = declines * eligible_share * recover
    rev = recovered * p.AVG_PAYMENT_PER_PERIOD * p.AVG_PERIODS_PER_ADMISSION
    placements = declines * hc_share
    m = st.columns(3)
    m[0].metric("Recovered admissions / month", f"{recovered:.0f}")
    m[1].metric("Added agency revenue / year", f"${rev * 12:,.0f}")
    m[2].metric("Home care placements / month", f"{placements:.0f}", f"${placements * fee * 12:,.0f}/yr referral fees")
    st.caption(f"Assumes \\${p.AVG_PAYMENT_PER_PERIOD:,} per 30-day period (MedPAC Dec 2025: \\$16.0B / 8.3M periods, 2024) "
               f"× {p.AVG_PERIODS_PER_ADMISSION} periods per admission. Excludes billing-capture uplift.")
