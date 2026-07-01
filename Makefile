.PHONY: mypy ruff lint fix test test-unit test-integration api worker migrate revision upgrade downgrade

package ?= app tests


mypy:
	uv run python -m mypy app/

ruff:
	uv run python -m ruff check $(package)

lint: ruff mypy

fix:
	uv run python -m ruff format $(package)
	uv run python -m ruff check $(package) --fix

test: lint test-unit

test-unit:
	uv run python -m pytest tests/unit/ -v

test-integration:
	uv run python -m pytest tests/integration/ -v

api:
	uv run python -m app api

worker:
	uv run python -m app worker


migrate:
	uv run python -m app migrate

revision:
	uv run alembic revision --autogenerate -m "$(m)"

upgrade:
	uv run alembic upgrade head

downgrade:
	uv run alembic downgrade -1
