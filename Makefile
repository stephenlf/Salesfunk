.PHONY: lint format test build clean

# Lint with ruff
lint:
	uvx ruff check -- src/

# Format with black
format:
	uvx black -- src/ tests/

# Run tests with pytest
test:
	uv run pytest --cov=salesfunk --cov-report=term --cov-report=html

# Clean build artifacts
clean:
	rm -rf dist/ build/ *.egg-info
