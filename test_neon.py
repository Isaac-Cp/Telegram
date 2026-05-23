import psycopg

conn_str = 'postgresql://neondb_owner:npg_rMkD7GZj2JBv@ep-flat-sound-alma08c0-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

try:
    conn = psycopg.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
    tables = cursor.fetchall()
    print('Existing tables:', [table[0] for table in tables])
    conn.close()
except Exception as e:
    print('connect error', type(e).__name__, e)