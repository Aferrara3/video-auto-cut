.PHONY: install run-backend run-frontend dev clean

install:
	poetry install
	cd app/frontend && npm install

run-backend:
	.venv/bin/python -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000

run-frontend:
	cd app/frontend && npm run dev

# Run both in parallel (requires make -j2 dev)
dev:
	$(MAKE) -j2 run-backend run-frontend

clean:
	rm -f broll_library.json
	rm -rf uploads keyframes_output outputs
	mkdir -p uploads keyframes_output outputs
	@echo "Cleaned up B-roll library and artifacts."
