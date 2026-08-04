.PHONY: api-test web-test build up down logs ps verify clean

api-test:
	cd apps/api && \
	. .venv/bin/activate && \
	ruff check . && \
	mypy app tests && \
	pytest -q

web-test:
	cd apps/web && \
	npm run typecheck && \
	npm run build

build:
	docker compose build

up:
	docker compose up --detach --build

down:
	docker compose down --remove-orphans

logs:
	docker compose logs --follow

ps:
	docker compose ps

verify:
	./scripts/verify-production-stack.sh

clean:
	docker compose down \
		--remove-orphans \
		--volumes \
		--rmi local
