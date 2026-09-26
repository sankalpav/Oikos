# Healthcare AI Hackathon: Project Submission (v2)

## 1. Team members' names

Sankalpa Venkatraghavan: Currently pursuing an MS in Biodesign at Stanford, worked as a forward deployed PM intern at Qualified Health over the summer and is a former McKinsey consultant.

Terry Lin: Current PM at Qualified Health with an MS in Clinical Informatics Management at Stanford, with a background in CS. Founder of ConciCare, an agentic intake solution that helps home health agencies capture more referrals while reducing manual workload.

Himani Shah: Software Engineer, most recently worked within the Go To Market and Finance team at LinkedIn. Currently exploring and building personal projects.

## 2. Project name

Oikos, an AI intake agent for home health agencies that gives every hospital referral a next step: accepted patients get a nurse and a complete bill, and declined patients get a home care plan, passed to the hospital's discharge planner in a note on the referral file.

## 3. What problem are you solving, and why does it matter?

Intake teams at home health agencies select discharges from hospitals and nursing facilities. Referrals arrive through CarePort, fax or phone, with a coordinator in charge of reading each discharge packet, checking insurance eligibility, homebound status, and whether a nurse is free near the patient's home. Speed decides who gets the patient: WellSky reports that agencies who respond first are about 22% more likely to secure the placement (company-reported, March 2026), so slow manual review loses patients.

Agencies now accept only about 24% of home health referrals, down from roughly 46% in 2019, driven by staffing challenges and rising patient complexity (WellSky 2023 Evolution of Care Report). Demand is still rising: referrals grew 4.6% last year, with comorbidity burden up 34% since 2019 (WellSky data, December 2025). Nurses, not patients, are the bottleneck.

This matters for everyone involved. Agencies lose revenue twice. They serve fewer patients than they could, and for patients they accept, the coder sees only the intake nurse's short summary, so documented conditions never make it onto the claim. With a 21.2% margin on traditional Medicare but only 5.0% across all payers (MedPAC, December 2025), which patients an agency accepts decides whether it makes money. Patients who are rejected usually get no further support, even if they may qualify for state Medicaid in-home programs such as California's IHSS, VA Aid & Attendance, PACE or long-term care insurance.

The timing is right because LLMs can parse long, unstructured discharge packets and pull out the facts intake decisions depend on, with a quote from the record for each one. LLMs combined with simple, auditable rules let an agency make a fast, capacity-aware decision on every referral without hiring more intake staff.

## 4. Describe what you built today

We built a working web app that optimizes an intake coordinator's referral queue. For every referral in the queue, Oikos reads the discharge packet using GPT-5.6 Terra on Amazon Bedrock. It pulls out diagnoses with ICD-10 codes, homebound status, skilled need, face-to-face documentation, the services ordered and the patient's daily-living needs. Every extracted fact is paired with an exact quote from the record, and the app checks each quote word for word against the source.

Rules, not the model, then make the decision. Oikos checks insurance and prior authorization, skilled need, homebound status and paperwork. It then matches real clinicians from the agency roster by license, skills, travel distance and open slots, with an RN required within Medicare's 48-hour start-of-care window (42 CFR 484.55). Each referral comes out as accept, fixable or decline, with a reason.

What happens next depends on the decision:
- For fixable referrals, Oikos drafts the missing face-to-face request to the discharge planner and the prior authorization request.
- For accepted and fixable referrals, it compares the full chart with the nurse's summary and lists the diagnoses the coder would miss, with chart quotes and a draft query to the nurse. For Original Medicare patients, a rule-based estimate shows how much the missed comorbidities could change the PDGM payment per 30-day period, using the CY2026 base rate and comorbidity adjustment tiers.
- For declined referrals, it checks home care programs and private-pay agencies, then writes a note to the referral file for the hospital discharge planner. The note lists the options the patient may qualify for, flags whether they still need skilled care from another agency, and records the family's preferred language for whoever reaches out. Oikos never contacts patients or families; only the hospital does.
- An impact view compares Oikos with the manual process and estimates the revenue gain for one agency.

To test it, we wrote five realistic synthetic referrals, each covering a different outcome:
- A hip fracture with undocumented diabetes and kidney disease.
- A heart failure patient on a Medicare Advantage plan with missing paperwork.
- A wound-vac patient in Gilroy whose only qualified nurse is free after the 48-hour window.
- A recovered pneumonia patient, a veteran who lives alone.
- A stroke patient whose employer plan is out of network.

In these illustrative tests, the live model reached the expected decision on all five:
- **Speed:** each referral took 8 to 24 seconds, and all five took about 20 seconds in parallel. Our assumed manual baseline is 2.5 to 4 hours per referral.
- **Acceptance:** Oikos accepted or recovered 2 of 5 referrals, compared with 1 under the manual process.
- **Billing:** it surfaced 5 to 7 missed diagnoses on each of the two accepted referrals, depending on the run.
- **Declined referrals:** all 3 went back with a discharge-planner note listing home care options, such as IHSS for a Medi-Cal patient and VA Aid & Attendance for a veteran.
- **Guardrail at work:** in one run the model paraphrased a quote instead of copying it, and the verification check flagged it in the interface.

Extraction, triage rules, nurse matching, fix-action drafts, billing capture with the PDGM estimate, home care qualification and discharge-planner notes all work today.

Several parts are mocked or simplified:
- Referrals load from a file rather than from CarePort.
- The nurse roster and schedules are a static table.
- Send buttons don't send anything.
- Home care program rules cover California, Texas, Florida, New York, Illinois and Pennsylvania, with a general fallback for other states; they are simplified summaries, not official eligibility determinations.
- The PDGM comorbidity mapping covers a small, hand-curated subset of CMS subgroups and is illustrative, not validated against the current CMS table.
- PACE service areas and all facilities, payers other than Original Medicare, clinicians and agencies are fictional.
- ICD-10 suggestions have not yet been reviewed by a certified coder.

We used only synthetic data, with no real patients and no real patient information. The prototype uses Python, Streamlit and GPT-5.6 Terra through Bedrock's OpenAI-compatible API, and it falls back to cached outputs if a live call fails.

## 5. What is the path to real-world impact?

The first users are intake coordinators and directors of nursing at independent and mid-sized home health agencies, starting in California. The buyers are agency owners and administrators, who would pay a flat monthly fee per branch. A second revenue stream comes from private-pay home care agencies matched through the discharge planner. The case for agencies is simple: faster, capacity-aware decisions win more of the right patients, and full billing raises revenue per nurse without hiring.

Our next step would be a pilot with two or three California-based agencies, after baseline measurement. We'd track:
- Time from referral to decision.
- Acceptance rate for insurance-eligible referrals.
- Share of care initiation within 48 hours.
- Number of missed diagnoses that coders confirm.
- Share of declined referrals where the hospital acts on the note's next steps.
- Whether responding first actually raises our pilot agencies' placement rate, to verify WellSky's 22% figure independently.

For validation, a nurse would confirm every coding suggestion, and a second reviewer would audit a random 10% of decisions.

To scale beyond a pilot, our dependencies are as follows:
- Oikos needs reliable access to referrals through each agency's own portal accounts, or through EHR and referral-platform integrations.
- It needs live roster and schedule data from agency systems such as WellSky or HCHB.
- It must run under a HIPAA business associate agreement.
- The PDGM estimate needs to grow from a curated comorbidity subset to the full, annually recalibrated CMS grouping, and the state program rules need official, maintained sources.

We see four main risks:
- **Referral access:** Oikos depends on referral platforms that don't offer a public API. We'd start with the agency's own accounts and pursue formal integrations.
- **Coding compliance:** Suggestions could be seen as upcoding. We address that with chart evidence for every suggestion, clinician confirmation and no automatic coding.
- **Referral payment rules:** Federal anti-kickback law restricts payments tied to referrals. We charge flat software fees, never pay for hospital referrals, and limit referral fees to private-pay home care, pending legal review.
- **Accepting patients the agency can't serve:** Oikos only recommends accepting when a real clinician slot exists, and its note tells the discharge planner when a declined patient still needs skilled care.

Existing tools route referrals. Oikos decides based on real nurse capacity, fixes the paperwork that causes avoidable declines, captures full revenue, and sends every declined referral back with a next step.

## 6. Live prototype or demo link

https://oikos-ai.streamlit.app/

The public link runs on cached model outputs so anyone can open it without AWS credentials. Our live demo runs the same app on GPT-5.6 Terra through Amazon Bedrock.

## 7. Code repository link

https://github.com/sankalpav/Oikos

The repository includes the full source, all synthetic data, a README with run instructions, and a system design summary (docs/Oikos_System_Design.pdf) covering our decisions and how the synthetic data was created.

## 8. Slides or additional material (videos)

[Demo video link: upload Oikos_pitch_v3.mp4 (2:06) to YouTube or Google Drive and paste a view link here]

## Hackathon submission confirmation

☑ We confirm this submission is our team's own work from the hackathon.
