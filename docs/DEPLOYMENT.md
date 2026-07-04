# DEPLOYMENT

Standard deployment flow:

Git commit

↓

Push

↓

Docker build

↓

Docker restart

↓

Logs check

↓

Telegram verification

↓

Update ENGINEERING_CHECKLIST

↓

Feature COMPLETE

---

## 1. Push

Deploy only committed and pushed code
(ENGINEERING_CHECKLIST.md — Verification Rule).

```
git push origin research/v2.8
```

## 2. Docker build

```
docker compose build api
```

## 3. Docker restart

```
docker compose up -d api
```

Postgres keeps running; only the application container is
recreated.

## 4. Logs check

```
docker compose logs --tail=100 api
```

Verify:

- no ERROR records
- no repeated WARNING records
- scheduler started
- Telegram listener started

## 5. Telegram verification

Run in the Telegram console:

```
/status
/health
/metrics
```

If research commands were touched, additionally:

```
/daily
/report YYYY-MM-DD
/analyze SYMBOL
```

## 6. Post-deploy

- Complete POST_DEPLOY_CHECKLIST.md
- Update ENGINEERING_CHECKLIST.md
- Confirm deployed git revision matches HEAD
