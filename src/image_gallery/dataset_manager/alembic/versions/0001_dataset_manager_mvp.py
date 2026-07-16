"""建立 DatasetManager MVP control 与 vectors schema。"""

from alembic import op

from image_gallery.dataset_manager.control import metadata

revision = "0001_dataset_manager_mvp"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建职责隔离 schema、pgvector extension 与业务关系。"""
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dataset_manager_control') THEN
            CREATE ROLE dataset_manager_control NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dataset_manager_vectors') THEN
            CREATE ROLE dataset_manager_vectors NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dataset_manager_catalog') THEN
            CREATE ROLE dataset_manager_catalog NOLOGIN;
          END IF;
        END
        $$
        """
    )
    op.execute("CREATE SCHEMA IF NOT EXISTS control")
    op.execute("CREATE SCHEMA IF NOT EXISTS vectors")
    op.execute("CREATE SCHEMA IF NOT EXISTS iceberg_catalog")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    metadata.create_all(bind=op.get_bind())
    op.execute("GRANT USAGE ON SCHEMA control TO dataset_manager_control")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA control TO dataset_manager_control")
    op.execute("GRANT USAGE ON SCHEMA vectors TO dataset_manager_vectors")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA vectors TO dataset_manager_vectors")
    op.execute("GRANT DELETE ON vectors.pending_asset_vectors TO dataset_manager_vectors")
    op.execute("GRANT USAGE, CREATE ON SCHEMA iceberg_catalog TO dataset_manager_catalog")
    op.execute("GRANT dataset_manager_control, dataset_manager_vectors, dataset_manager_catalog TO CURRENT_USER")


def downgrade() -> None:
    """删除当前 revision 创建的业务关系。"""
    metadata.drop_all(bind=op.get_bind())
