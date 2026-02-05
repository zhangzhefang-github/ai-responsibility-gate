.PHONY: run test replay replay-diff clean

run:
	python3 -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000

test:
	PYTHONPATH=. python3 -m pytest tests/ -v

replay:
	PYTHONPATH=. python3 -m src.replay.run

replay-diff:
	PYTHONPATH=. python3 -m src.replay.diff --base matrices/v0.1.yaml --cand matrices/v0.2.yaml --cases cases/

clean:
	rm -f replay_*.md
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
