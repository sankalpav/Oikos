# Oikos: home health intake agent

Every referral gets a next step: accepted patients get billed fully, rejected patients still get a care plan.

1. **Intake triage**: an LLM reads the discharge packet, then rules check insurance, skilled need, homebound status, face-to-face, and match a nurse (license, skills, radius, 48-hr start of care).
2. **Billing capture** (accept/fixable): diagnoses in the chart but missing from the nurse summary, with verified quotes and a nurse query, plus a rule-based (non-LLM) estimated dollar impact from PDGM comorbidity adjustments, when the payer is Medicare FFS.
3. **Home care qualification** (declined): IHSS, MSSP, VA Aid & Attendance, PACE, LTC insurance, private-pay agencies, plus a note added to the file for the hospital discharge planner. Oikos does not contact patients or families directly — only the hospital may.

All data in `data/` is synthetic.

## Run

```bash
cd "09 Hackathons/aws/oikos"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Without AWS credentials the app uses cached outputs (`data/mock/`), so the demo always works.

## Live model (GPT-5.6 Terra on Bedrock)

1. Open the workshop join link, sign in, then choose **Get AWS CLI credentials** on the event page.
2. Paste the `export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=...` lines into your terminal (not into git or chat).
3. `export AWS_REGION=us-east-1`, then run `streamlit run app.py` in that same terminal.
4. In the sidebar, turn on **Live model** and click **Test Bedrock connection**.

If a live call fails, that step falls back to the cached output and the reason is shown under the decision.

## Files

- `pipeline.py`: extraction, triage rules, nurse matching, billing, home care rules, PDGM comorbidity dollar estimate
- `llm.py`: Bedrock OpenAI-compatible Responses API client
- `app.py`: Streamlit UI (queue, referral detail, impact)
- `data/`: referrals, nurse roster, agencies, payers, zips, PACE areas, mock outputs
- `data/comorbidity_subgroups.json`: small illustrative ICD-10 → PDGM comorbidity subgroup lookup (see its `_caveat` field — not the verbatim CMS list)
