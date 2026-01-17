generate-migration:
	@alembic revision --autogenerate -m $(msg)

migrate-up:
	@alembic upgrade head

migrate-down:
	@alembic downgrade base

migrate-up-version:
	@alembic upgrade $(id)

migrate-down-version:
	@alembic downgrade $(id)

migrate-version:
	@alembic current
