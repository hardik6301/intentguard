from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_grant_currency"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "authorization_grants",
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
    )
    op.create_unique_constraint("uq_payments_grant_id", "payments", ["grant_id"])


def downgrade() -> None:
    op.drop_constraint("uq_payments_grant_id", "payments", type_="unique")
    op.drop_column("authorization_grants", "currency")
