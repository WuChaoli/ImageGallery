"""Alembic runtime for the DatasetManager control plane。"""

from alembic import context
from sqlalchemy import text

from image_gallery.dataset_manager.control import metadata

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("DatasetManager migrations require an explicit connection")

# Alembic 会在执行首个 revision 前创建版本表，因此版本表所在 schema 必须先存在。
connection.execute(text("CREATE SCHEMA IF NOT EXISTS control"))

context.configure(
    connection=connection,
    target_metadata=metadata,
    compare_type=True,
    version_table_schema="control",
)
with context.begin_transaction():
    context.run_migrations()
