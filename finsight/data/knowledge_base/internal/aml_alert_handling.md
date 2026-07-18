---
doc_id: aml_alert_handling
title: AML Alert Handling Playbook
doc_type: sop
effective_date: 2025-04-01
access_role: staff
source: synthetic_internal
---

# AML Alert Handling Playbook

## Severity ranking
1. **Critical** — confirmed sanctions hit, structuring with prior SAR, insider abuse indicators
2. **High** — rapid movement of funds, geo-anomaly with high-risk jurisdiction, mule-pattern scoring
3. **Medium** — atypical merchant category, amount outlier vs. profile
4. **Low** — single soft rule breach with compensating history

## Investigation steps
1. Freeze disposition only with dual control when loss is imminent
2. Pull 90-day transaction history and counterparties
3. Document rationale in the case management system within **2 business days**
4. Escalate for SAR consideration when suspicion remains after review

## SAR timing
File Suspicious Activity Reports within **30 calendar days** of initial detection when required. Do **not** tip off the customer that a SAR has been or will be filed.

## Tooling note
FinSight Fraud/Risk Triage summarizes system alerts; final SAR decisions remain with the BSA Officer or designated investigator.
