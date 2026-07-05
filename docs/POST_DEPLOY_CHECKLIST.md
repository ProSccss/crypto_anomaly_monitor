# POST DEPLOY CHECKLIST

After every deployment verify the following.

---

## Infrastructure

□ Docker containers are healthy

□ Database migrations applied

□ Scheduler started

□ Scanner started

□ Telegram Listener started

---

## Telegram Console

□ /help

□ /status

□ /health

□ /metrics

□ /daily

□ /report YYYY-MM-DD

□ /analyze LABUSDT

□ /why LABUSDT

---

## Scanner

□ Scanner cycle is running

□ Feature snapshots are being created

□ New anomalies appear

□ Setup detection works

---

## Reports

□ Daily report generated

□ Historical report generated

---

## Logs

□ No ERROR records

□ No repeated WARNING records

□ Telegram listener started

□ Scheduler initialized

---

## Final Verification

□ Git revision matches deployed revision

□ PROJECT_STATUS updated (if required)

□ Deployment recorded in CHANGELOG (if applicable)