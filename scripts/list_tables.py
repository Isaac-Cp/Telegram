import psycopg
from urllib.parse import urlparse, parse_qs

conn_str = "postgresql://neondb_owner:npg_C4q2otINymiB@ep-hidden-star-alvwnl0y.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

try:
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
            rows = cur.fetchall()
            print('tables:', [r[0] for r in rows])
except Exception as e:
    print('ERROR', type(e).__name__, e)
