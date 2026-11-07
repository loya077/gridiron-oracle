PY ?= python3

.PHONY: refresh run test help

help:
	@echo "make refresh  - download latest data, rebuild ratings, save + grade picks"
	@echo "make run      - start the app at http://127.0.0.1:8642"
	@echo "make test     - run the test suite"

refresh:
	$(PY) -m oracle refresh

run:
	$(PY) -m oracle run

test:
	$(PY) -m oracle test
