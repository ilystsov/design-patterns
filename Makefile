CODE_FOLDERS := server
TEST_FOLDERS := tests

.PHONY: update test lint security_checks

install:
	poetry install --no-root

update:
	poetry lock
	poetry install --no-root

test:
	poetry run pytest $(TEST_FOLDER) --cov=$(CODE_FOLDERS) --cov-report term --cov-report=html

format:
	poetry run black --line-length 79 .

lint:
	poetry run black --check .
	poetry run flake8 $(CODE_FOLDERS) $(TEST_FOLDERS)
	poetry run pylint $(CODE_FOLDERS) $(TEST_FOLDERS)
	poetry run mypy $(CODE_FOLDERS) $(TEST_FOLDERS)