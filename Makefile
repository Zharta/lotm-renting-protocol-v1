.PHONY: venv install install-dev test run clean interfaces docs

VENV?=./.venv
PYTHON=${VENV}/bin/python3
PIP=${VENV}/bin/pip

CONTRACTS := $(shell find contracts -depth 1 -name '*.vy')
NATSPEC := $(patsubst contracts/%, natspec/%, $(CONTRACTS:%.vy=%.json))
PATH := ${VENV}/bin:${PATH}

vpath %.vy ./contracts

$(VENV):
	python3 -m venv $(VENV)
	${PIP} install -U pip
	${PIP} install pip-tools wheel

install: $(VENV) requirements.txt
	${PIP} install -r requirements.txt
	${VENV}/bin/ape plugins install --upgrade .

install-dev: $(VENV) requirements-dev.txt
	${PIP} install -r requirements-dev.txt
	${VENV}/bin/ape plugins install --upgrade .
	$(VENV)/bin/pre-commit install

requirements.txt: pyproject.toml
	$(VENV)/bin/pip-compile -o requirements.txt pyproject.toml

requirements-dev.txt: pyproject.toml
	$(VENV)/bin/pip-compile -o requirements-dev.txt --extra dev pyproject.toml

unit-tests: ${VENV}
	${VENV}/bin/pytest tests/unit --durations=20 -n auto

integration-tests: ${VENV}
	${VENV}/bin/pytest -n auto tests/integration -m "not profile" --durations=20

fuzz-tests:
	${VENV}/bin/pytest tests/fuzz --durations=0 -n auto

coverage:
	${VENV}/bin/coverage run -m pytest tests/unit --durations=0
	${VENV}/bin/coverage report | tee coverage.txt

gas:
	${VENV}/bin/pytest tests/integration/renting/test_gas.py --durations=0 --gas-profile

compile:
	ape compile -f

interfaces:
	${VENV}/bin/python scripts/build_interfaces.py contracts/*.vy

docs: $(NATSPEC)

natspec/%.json: %.vy
	${VENV}/bin/vyper -f userdoc,devdoc $< > $@

clean:
	rm -rf ${VENV} .cache


%-local: export ENV=local
%-dev: export ENV=dev
%-int: export ENV=int
%-prod: export ENV=prod

add-account:
	${VENV}/bin/ape accounts import $(alias)

console-local:
	${VENV}/bin/ape console --network ethereum:local:ganache

deploy-local:
	${VENV}/bin/ape run -I deployment --network ethereum:local:ganache

console-dev:
	${VENV}/bin/ape console --network https://network.dev.zharta.io

deploy-dev:
	${VENV}/bin/ape run -I deployment --network https://network.dev.zharta.io

publish-dev:
	${VENV}/bin/ape run publish

console-int:
	${VENV}/bin/ape console --network ethereum:sepolia:alchemy

deploy-int:
	${VENV}/bin/ape run -I deployment --network ethereum:sepolia:alchemy

publish-int:
	${VENV}/bin/ape run publish

console-prod:
	${VENV}/bin/ape console --network ethereum:mainnet:alchemy

deploy-prod:
	${VENV}/bin/ape run -I deployment --network ethereum:mainnet:alchemy

publish-prod:
	${VENV}/bin/ape run publish
