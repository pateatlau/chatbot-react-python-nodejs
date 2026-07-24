.PHONY: backend

# Ensure local Postgres (docker) is up, then start the Python API on :8000.
backend:
	@./scripts/ensure-postgres.sh
	@./scripts/ensure-dev-api-port.sh
	$(MAKE) -C backend-python run
