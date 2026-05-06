"""init_schema

Revision ID: 9d30203ca4c7
Revises:
Create Date: 2026-05-04 20:58:05.263133

"""
from typing import Sequence, Union
import os
import subprocess

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '9d30203ca4c7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_sql_file_path() -> str:
    """Return the absolute path to the initial schema SQL file."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, '..', 'migrations', 'V001__init_schema.sql')


def _get_db_url() -> str:
    """Extract database connection info from the current Alembic connection."""
    bind = op.get_bind()
    url = str(bind.engine.url)
    return url


def upgrade() -> None:
    """Execute the initial schema migration via psql."""
    sql_path = os.path.abspath(_get_sql_file_path())
    if not os.path.exists(sql_path):
        raise FileNotFoundError(f"Migration SQL file not found: {sql_path}")

    bind = op.get_bind()
    url = bind.engine.url
    host = url.host or 'localhost'
    port = url.port or 5432
    database = url.database or 'bidai'
    username = url.username or 'bidai'
    password = url.password or ''

    env = os.environ.copy()
    if password:
        env['PGPASSWORD'] = password

    cmd = [
        'psql',
        '-h', host,
        '-p', str(port),
        '-U', username,
        '-d', database,
        '-v', 'ON_ERROR_STOP=1',
        '-f', sql_path,
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"psql execution failed (code {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )


def downgrade() -> None:
    """Drop all schemas created by this migration."""
    schemas = ['audit', 'ai_task', 'bid', 'knowledge', 'project', 'auth']
    conn = op.get_bind()
    for schema in schemas:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
