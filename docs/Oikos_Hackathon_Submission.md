# Healthcare AI Hackathon: Project Submission

## 1. Team members' names

Sankalpa Venkatraghavan [role and background, from LinkedIn] came up with the home health intake idea and led product, the system design and the build.

Terry Lin [role and background, from LinkedIn].

Himani Shah [role and background, from LinkedIn].

## 2. Project name

Oikos, an AI intake agent for home health agencies that gives every hospital referral a next step: accepted patients get a nurse and a complete bill, and declined referrals go back to the hospital with a note of next steps.

## 3. What problem are you solving, and why does it matter?

We're starting with intake teams at home health agencies, the people who decide which hospital and nursing facility discharges their agency can take. Referrals arrive through CarePort, fax and phone, and a coordinator reads each discharge packet by hand to check insurance, homebound status, skilled need, paperwork and whether a nurse is free near the patient's home. The first agency to say yes usually gets the patient, so slow manual review loses patients.

Agencies now accept only about 30% of referrals, down from roughly 80% before the pandemic, and 77% of providers say they have turned referrals away because of staffing. Demand is still rising: referrals grew 4.6% last year, and patients are sicker, with comorbidity burden up 34% since 2019 (WellSky data, December 2025). Nurses, not patients, are the bottleneck.

This matters for everyone involved. Agencies lose revenue twice. They decline patients they could have served, and for patients they accept, the coder sees only the intake nurse's short summary, so documented conditions never make it onto the claim. With a 21.2% margin on traditional Medicare but only 5.0% across all payers (MedPAC, December 2025), which patients an agency accepts decides whether it makes money. Referrals that are declined usually go back with no next step at all, even when they qualify for help such as California's IHSS program, VA Aid & Attendance, PACE or long-term care insurance.

The timing is right because large language models can now read long, unstructured discharge packets and pull out the facts intake decisions depend on, with a quote from the record for each one. Combined with simple, auditable rules, that lets an agency make a fast, capacity-aware decision on every referral without hiring more intake staff.

## 4. Describe what you built today

We built a working web app that follows an intake coordinator's day. Referrals appear in a queue. With one click, Oikos reads each discharge packet using GPT-5.6 Terra on Amazon Bedrock. It pulls out diagnoses with ICD-10 codes, homebound status, skilled need, face-to-face documentation, the services ordered and the patient's daily-living needs. Every extracted fact is paired with an exact quote from the record, and the app checks each quote word for word against the source.

Rules, not the model, then make the decision. Oikos checks insurance and prior authorization, skilled need, homebound status and paperwork. It then matches real clinicians from the agency roster by license, skills, travel distance and open slots, with an RN required within Medicare's 48-hour start-of-care window. Each referral comes out as accept, fixable or decline, with a reason.

What happens next depends on the decision:
- For fixable referrals, Oikos drafts the missing face-to-face request to the discharge planner and the prior authorization request.
- For accepted and fixable referrals, it compares the full chart with the nurse's summary and lists the diagnoses the coder would miss, with chart quotes and a draft query to the nurse.
- For declined referrals, it checks home care programs and private-pay agencies, then adds a rejection note to the referral file for the hospital's discharge planner. The note gives the reason, what would change the decision, whether the patient still needs skilled care elsewhere, and home care options to review with the patient. Oikos never contacts patients or families; only the hospital does.
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
- **Billing:** it surfaced 5 and 7 missed diagnoses on the two accepted referrals.
- **Declined referrals:** all 3 went back with a rejection note listing the reason and home care options, such as IHSS for a Medi-Cal patient and VA Aid & Attendance for a veteran.
- **A guardrail at work:** in one run the model paraphrased a quote instead of copying it, and the verification check flagged it in the interface.

Extraction, triage rules, nurse matching, fix-action drafts, billing capture, home care qualification and rejection notes all work today.

Several parts are mocked or simplified:
- Referrals load from a file rather than from CarePort.
- The nurse roster and schedules are a static table.
- Send buttons don't send anything.
- Program eligibility uses general California rules.
- PACE service areas and all facilities, payers other than Original Medicare, clinicians and agencies are fictional.
- ICD-10 suggestions have not yet been reviewed by a certified coder.

We used only synthetic data, with no real patients and no real patient information. The prototype uses Python, Streamlit and GPT-5.6 Terra through Bedrock's OpenAI-compatible API, and it falls back to cached outputs if a live call fails.

## 5. What is the path to real-world impact?

The first users are intake coordinators and directors of nursing at independent and mid-sized home health agencies in California. The buyers are agency owners and administrators, who would pay a flat monthly fee per branch. A second revenue stream comes from private-pay home care agencies that receive matched families. The case for agencies is simple: faster, capacity-aware decisions win more of the right patients, and full billing raises revenue per nurse without hiring.

Our next step is a four-week pilot with two or three California agencies, after one week of baseline measurement. We'd track:
- Time from referral to decision.
- Acceptance rate for insurance-eligible referrals.
- Share of starts of care within 48 hours.
- Number of missed diagnoses that coders confirm.
- Share of declined referrals where the hospital acts on the note's next steps.

For safety, a nurse confirms every coding suggestion, and a second reviewer would audit a random 10% of decisions.

To scale beyond a pilot, a few things have to be true:
- Oikos needs reliable access to referrals through each agency's own portal accounts, or through EHR and referral-platform integrations.
- It needs live roster and schedule data from agency systems such as WellSky or HCHB.
- It must run under a HIPAA business associate agreement on AWS.
- Program rules must be maintained state by state.
- It needs full PDGM payment logic so it can put a dollar value on each missed diagnosis.

We see four main risks:
- **Referral access:** Oikos depends on referral platforms that don't offer a public API. We'd start with the agency's own accounts and pursue formal integrations.
- **Coding compliance:** suggestions could be seen as upcoding. We address that with chart evidence for every suggestion, clinician confirmation and no automatic coding.
- **Referral payment rules:** federal anti-kickback law restricts payments tied to referrals. We charge flat software fees, never pay for hospital referrals, and limit referral fees to private-pay home care, pending legal review.
- **Accepting patients the agency can't serve:** Oikos only recommends accepting when a real clinician slot exists, and it tells the discharge planner right away when a declined patient still needs skilled care.

Existing tools route referrals. Oikos decides based on real nurse capacity, fixes the paperwork that causes avoidable declines, captures full revenue, and sends every declined referral back with a next step.

## 6. Live prototype or demo link

[Streamlit Community Cloud link, e.g. https://oikos-demo.streamlit.app]

The public link runs on cached model outputs so anyone can open it without AWS credentials. Our live demo runs the same app on GPT-5.6 Terra through Amazon Bedrock.

## 7. Code repository link

https://github.com/sankalpav/Oikos

The repository includes the full source, all synthetic data, a README with run instructions, and a system design summary (docs/Oikos_System_Design.pdf) covering our decisions and how the synthetic data was created.

## 8. Slides or additional material (videos)

[Demo video link, 3 minutes or less]

[Slides link]

System design summary: docs/Oikos_System_Design.pdf in the repository.

## Hackathon submission confirmation

☑ We confirm this submission is our team's own work from the hackathon.

Sources: MedPAC home health update (December 2025); Home Health Care News on WellSky referral data (December 2025); Luna and McKnight's Home Care on referral acceptance and staffing. All patient data is synthetic.
