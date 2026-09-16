from alembic import op


def upgrade():
    op.create_table("items")
    op.create_table("owners")
