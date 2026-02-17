import os
from psycopg2 import pool

_pool: pool.SimpleConnectionPool = None


def _init_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(1, 5, dsn=os.environ['DATABASE_URL'])
    return _pool


def get_conn():
    return _init_pool().getconn()


def release_conn(conn):
    _init_pool().putconn(conn)
