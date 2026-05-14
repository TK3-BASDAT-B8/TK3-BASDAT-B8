import uuid
from django.db import connection


def _serialize(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_serialize(v) for v in value)
    return value


def _row_to_dict(cols, row):
    return {col: _serialize(val) for col, val in zip(cols, row)}


def fetch_all(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        cols = [col[0] for col in cursor.description]
        return [_row_to_dict(cols, row) for row in cursor.fetchall()]


def fetch_one(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        if cursor.description is None:
            return None
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        return _row_to_dict(cols, row) if row else None


def execute_query(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])


def execute_returning(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        return _row_to_dict(cols, row) if row else None


def db_error_message(exc):
    msg = str(exc).strip().split('\n')[0]
    for prefix in ('ERROR:  ', 'ERROR: '):
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
    return msg
