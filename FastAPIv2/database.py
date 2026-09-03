import psycopg2
from config import settings


conn = psycopg2.connect(
    host=settings.database_host,
    database=settings.database_name,
    user=settings.database_user,
    password=settings.database_password,
    port=settings.database_port,
)
cur = conn.cursor()
