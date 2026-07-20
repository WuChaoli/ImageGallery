"""增加 Dataset 名称 durable reservation。"""

from alembic import op

revision = "0002_dataset_name_reservation"
down_revision = "0001_dataset_manager_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建名称预留关系并为既有 Dataset 回填永久占用。"""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS control.dataset_name_reservations (
            repo_id VARCHAR(32) NOT NULL REFERENCES control.repos(repo_id),
            name_key VARCHAR(255) NOT NULL,
            operation_id VARCHAR(32) NOT NULL UNIQUE REFERENCES control.operations(operation_id),
            target_dataset_id VARCHAR(32) NOT NULL UNIQUE,
            PRIMARY KEY (repo_id, name_key)
        )
        """
    )
    op.execute(
        """
        INSERT INTO control.dataset_name_reservations (
            repo_id,
            name_key,
            operation_id,
            target_dataset_id
        )
        SELECT
            dataset.repo_id,
            dataset.name_key,
            MIN(operation.operation_id),
            dataset.dataset_id
        FROM control.datasets AS dataset
        JOIN control.operations AS operation
          ON operation.repo_id = dataset.repo_id
         AND operation.dataset_id = dataset.dataset_id
        GROUP BY dataset.repo_id, dataset.name_key, dataset.dataset_id
        ON CONFLICT (repo_id, name_key) DO NOTHING
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON control.dataset_name_reservations TO dataset_manager_control")


def downgrade() -> None:
    """删除 Dataset 名称预留关系。"""
    op.execute("DROP TABLE IF EXISTS control.dataset_name_reservations")
