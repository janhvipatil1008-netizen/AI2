"""Repository layer for AI² DB access.

Functions accept an injected psycopg2 connection and do not open connections
themselves. Callers use database.pool.get_conn() to obtain a connection.

Not wired into routes or services yet — this package is additive preparation.
"""
