import psycopg

conn_str = "postgresql://neondb_owner:npg_C4q2otINymiB@ep-hidden-star-alvwnl0y.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg.connect(conn_str)
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print('OK', cur.fetchone())
    conn.close()
except Exception as e:
    print('ERROR', type(e).__name__, e)
