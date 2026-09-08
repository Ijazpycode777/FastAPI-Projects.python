import psycopg2

from config import settings


conn = psycopg2.connect(
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
        user=settings.database_user,
        password=settings.database_password
    )
cur=conn.cursor()
