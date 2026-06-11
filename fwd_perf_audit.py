"""Forward performance audit for bp>=25, sq>=30 cohort."""
import asyncio
from datetime import datetime, timezone, timedelta
from app.db import engine
from sqlalchemy import text


async def main():
    async with engine.connect() as conn:

        # Candle coverage
        r = await conn.execute(text(
            "SELECT id AS iid FROM instruments WHERE symbol='LABUSDT'"
        ))
        iid = str(r.fetchone().iid)

        r2 = await conn.execute(text(
            "SELECT MIN(bucket_ts) as f, MAX(bucket_ts) as l, COUNT(*) as n "
            "FROM candles WHERE instrument_id = :iid AND interval = '1'"
        ), {"iid": iid})
        c = r2.fetchone()
        print(f"1-min candles: {c.n} rows  [{c.f}  ->  {c.l}]")
        candle_end = c.l
        print()

        # Pull cohort
        r3 = await conn.execute(text("""
            SELECT fs.bucket_ts,
                CAST(fs.breakout_probability AS float) AS bp,
                CAST(fs.squeeze_probability  AS float) AS sq,
                CAST(fs.expected_move_score  AS float) AS ems
            FROM feature_snapshots fs
            JOIN instruments i ON i.id = fs.instrument_id
            WHERE i.symbol = 'LABUSDT'
              AND CAST(fs.confidence AS float) >= 0.80
              AND fs.components->>'data_quality_status' = 'GOOD'
              AND CAST(fs.breakout_probability AS float) >= 25
              AND CAST(fs.squeeze_probability  AS float) >= 30
            ORDER BY fs.bucket_ts
        """))
        cohort = r3.fetchall()
        print(f"Cohort: {len(cohort)} snapshots")

        pump_ts = datetime(2026, 6, 6, 20, 52, tzinfo=timezone.utc)

        results = []
        for snap in cohort:
            ts = snap.bucket_ts
            row = {"ts": ts, "bp": snap.bp, "sq": snap.sq, "ems": snap.ems,
                   "pre": ts < pump_ts}

            # entry price
            re = await conn.execute(text("""
                SELECT CAST(close AS float) as cp
                FROM candles WHERE instrument_id = :iid AND interval = '1'
                  AND bucket_ts BETWEEN :a AND :b
                ORDER BY ABS(EXTRACT(EPOCH FROM bucket_ts - :ts)) LIMIT 1
            """), {"iid": iid,
                   "a": ts - timedelta(minutes=5),
                   "b": ts + timedelta(minutes=5),
                   "ts": ts})
            er = re.fetchone()
            if not er:
                continue
            entry = er.cp
            row["entry"] = entry

            # horizons: only request those within candle range
            for h in [1, 4, 12]:
                tgt = ts + timedelta(hours=h)
                if tgt > candle_end + timedelta(minutes=30):
                    continue  # no data

                rp = await conn.execute(text("""
                    SELECT CAST(close AS float) as cp
                    FROM candles WHERE instrument_id = :iid AND interval = '1'
                      AND bucket_ts BETWEEN :a AND :b
                    ORDER BY ABS(EXTRACT(EPOCH FROM bucket_ts - :tgt)) LIMIT 1
                """), {"iid": iid,
                       "a": tgt - timedelta(minutes=15),
                       "b": tgt + timedelta(minutes=15),
                       "tgt": tgt})
                pr = rp.fetchone()

                rm = await conn.execute(text("""
                    SELECT MAX(CAST(high AS float)) as mh,
                           MIN(CAST(low  AS float)) as ml
                    FROM candles WHERE instrument_id = :iid AND interval = '1'
                      AND bucket_ts >= :ts AND bucket_ts <= :tgt
                """), {"iid": iid, "ts": ts, "tgt": tgt})
                mr = rm.fetchone()

                if pr and pr.cp and entry > 0:
                    ret = (pr.cp - entry) / entry * 100
                    row[f"ret{h}"] = ret

                if mr and mr.mh and entry > 0:
                    mfe_u = (mr.mh - entry) / entry * 100
                    mfe_d = (entry - mr.ml) / entry * 100
                    row[f"mfe{h}u"] = mfe_u
                    row[f"mfe{h}d"] = mfe_d
                    row[f"mfe{h}b"] = max(mfe_u, mfe_d)

            results.append(row)

        pre  = [r for r in results if r["pre"]]
        post = [r for r in results if not r["pre"]]

        def avg(g, k):
            v = [x[k] for x in g if k in x]
            return round(sum(v)/len(v), 2) if v else None

        def hit(g, k, t):
            v = [x[k] for x in g if k in x]
            return round(100*sum(1 for x in v if x >= t)/len(v), 1) if v else None

        def show(g, label):
            n = len(g)
            print(f"  {label}  (n={n})")
            for h in [1, 4, 12]:
                ret = avg(g, f"ret{h}")
                mu  = avg(g, f"mfe{h}u")
                md  = avg(g, f"mfe{h}d")
                mb  = avg(g, f"mfe{h}b")
                n_h = sum(1 for x in g if f"ret{h}" in x)
                if ret is None and mu is None:
                    print(f"    {h}h : no candle coverage")
                    continue
                print(f"    {h}h (n_valid={n_h}): ret={ret}%  mfe_up={mu}%  mfe_dn={md}%  mfe_best={mb}%")
            # hit rates on 4h window where available
            h4u = hit(g, "mfe4u", 3); h4u5 = hit(g, "mfe4u", 5)
            h4d = hit(g, "mfe4d", 3); h4d5 = hit(g, "mfe4d", 5)
            h4b = hit(g, "mfe4b", 3); h4b5 = hit(g, "mfe4b", 5); h4b10 = hit(g, "mfe4b", 10)
            # 1h hits
            h1u = hit(g, "mfe1u", 3); h1d = hit(g, "mfe1d", 3)
            h1u5 = hit(g, "mfe1u", 5); h1d5 = hit(g, "mfe1d", 5)
            print(f"    1h hits: UP_3%={h1u}%  UP_5%={h1u5}%  DOWN_3%={h1d}%  DOWN_5%={h1d5}%")
            if h4b is not None:
                print(f"    4h hits: best_3%={h4b}%  best_5%={h4b5}%  best_10%={h4b10}%")
                print(f"             UP_3%={h4u}%  UP_5%={h4u5}%  DOWN_3%={h4d}%  DOWN_5%={h4d5}%")
            print()

        print()
        print("="*60)
        print("FORWARD PERFORMANCE")
        print("="*60)
        show(pre,  "PRE-PUMP  (06-05 20:36 - 22:29)")
        show(post, "POST-PUMP (06-07 08:43 - 11:01)")
        show(results, "ALL COMBINED")

        # Candle coverage explanation
        print("CANDLE COVERAGE NOTE:")
        print(f"  Candles end at: {candle_end}")
        print(f"  Pre-pump last snapshot: {pre[-1]['ts'] if pre else 'N/A'}")
        print(f"  Pre-pump +4h target: ~06-06 02:30  -> gap in DB (no candles)")
        print(f"  Post-pump last snapshot: ~06-07 11:01")
        print(f"  Post-pump +4h target: ~06-07 15:01  -> beyond candle end")
        print(f"  Only 1h horizon has full coverage for both groups.")
        print()

        # Summary comparison table
        print("="*60)
        print("SUMMARY COMPARISON TABLE")
        print("="*60)
        print(f"  Metric              Pre-pump (n=42)   Post-pump (n=73)")
        print(f"  ------------------  ---------------   ----------------")
        for label, k in [
            ("avg_ret_1h",    "ret1"),
            ("avg_mfe_1h_up", "mfe1u"),
            ("avg_mfe_1h_dn", "mfe1d"),
        ]:
            pv = avg(pre,  k)
            ov = avg(post, k)
            print(f"  {label:<20}  {str(pv):>12}%   {str(ov):>12}%")
        for label, k, t in [
            ("hit_1h_UP_3%",  "mfe1u", 3),
            ("hit_1h_UP_5%",  "mfe1u", 5),
            ("hit_1h_DN_3%",  "mfe1d", 3),
            ("hit_1h_DN_5%",  "mfe1d", 5),
        ]:
            pv = hit(pre,  k, t)
            ov = hit(post, k, t)
            print(f"  {label:<20}  {str(pv):>11}%    {str(ov):>11}%")


asyncio.run(main())
