SHELL:=/usr/bin/env bash
export TOP:=$(shell dirname "$(abspath $(lastword $(MAKEFILE_LIST)))")
name:=$(shell basename "$(TOP)")
export PIP_FIND_LINKS:=$(abspath $(TOP)/whl_local/)
export PYTHONPATH:=$(TOP)/src


.PHONY: help
help:
	@echo
	@echo "▍Help"
	@echo "▀▀▀▀▀▀"
	@echo
	@echo "Available targets:"
	@echo "    check:              run checks"
	@echo "    test:               run all tests"
	@echo "    coverage:           run all tests and collect code coverage"
	@echo "    lint:               run linters"
	@echo
	@echo "    format:             auto-format code with ruff"
	@echo
	@echo "    build:              build the source and whl package, look for */dist/*.whl"
	@echo
	@echo "    release:            tag a new release (required: V=X.Y.Z), e.g. make V=1.0.0 release"
	@echo
	@echo "    rpm:                build RPM and SRPM (optional: RPM_VER=X.Y.Z RPM_REV=N)"
	@echo "    srpm:               build SRPM only  (optional: RPM_VER=X.Y.Z RPM_REV=N)"
	@echo
	@echo "    run:                sync dev environment and run the app (development mode)"
	@echo
	@echo "    clean:              clean the build tree"
	@echo
	@printf "Makefile debug: name=%q, PYTHONPATH=%q, PIP_FIND_LINKS=%q\n\n" "$(name)" "$(PYTHONPATH)" "$(PIP_FIND_LINKS)"


.PHONY: check
check: lint


.PHONY: test
test:
	pytest -v


.PHONY: coverage
coverage:
	pytest -v --cov . --cov-report=term-missing


.PHONY: lint
lint:
	ruff check "src/$(name)"


.PHONY: format
format:
	ruff format "src/$(name)"
	ruff check --fix "src/$(name)"


.PHONY: build
build:
	python3 -m build
	mkdir -p "$(PIP_FIND_LINKS)/"
	cp dist/*.whl "$(PIP_FIND_LINKS)/"


.PHONY: userinstall
userinstall: build
	python3 -m pip install $(PIP_USER) ./dist/*.whl


.PHONY: uninstall
uninstall:
	python3 -m pip uninstall -y "$(name)"


.PHONY: useruninstall
useruninstall: uninstall


RPM_VER ?= $(shell git tag --sort=-version:refname | grep -E '^v?[0-9]' | head -1 | sed 's/^v//')
RPM_REV ?= 0

.PHONY: rpmprep
rpmprep:
	@[ -n "$(RPM_VER)" ] || { echo "Error: RPM_VER could not be determined (no release tags found)."; exit 1; }
	cp "rpm/$(name).spec.in" "$(name).spec"
	sed -i 's|^Version:.*|Version:        $(RPM_VER)|g' "$(name).spec"
	sed -i 's|^Release:.*|Release:        $(RPM_REV)%{?dist}|g' "$(name).spec"
	rm -rf ~/rpmbuild/RPMS/noarch/"$(name)"*.rpm ~/rpmbuild/SRPMS/"$(name)"*.src.rpm
	python3 -m build --sdist
	mkdir -p ~/rpmbuild/SOURCES
	cp dist/$(name)-$(RPM_VER).tar.gz rpm/$(name).desktop rpm/$(name).svg ~/rpmbuild/SOURCES/


.PHONY: rpm
rpm: rpmprep
	rpmbuild -ba "$(name).spec"
	rm "$(name).spec"


.PHONY: srpm
srpm: rpmprep
	rpmbuild -bs "$(name).spec"
	rm "$(name).spec"


.PHONY: run
run:
	uv sync --group dev
	uv run bluelock


.PHONY: release
release:
	@[ -n "$(V)" ] || { echo "Error: V is not set.  Usage: make V=X.Y.Z release"; exit 1; }
	"$(TOP)/release.py" "$(V)"


.PHONY: clean
clean:
	-python3 -m coverage erase
	find "$(TOP)" -depth \( -name '__pycache__' -o -name '*.pyc' -o -name '*.pyo' -o -name '*.pyd' -o -name '*.egg-info' -o -name '*.py,cover' \) \
		-not -path '*/.git/*' -exec rm -rf {} +
	rm -rf "$(TOP)/build/" "$(TOP)/dist/" "$(TOP)/.tox/" \
		"$(TOP)/.pytest_cache/" "$(TOP)/.coverage"


.PHONY: test_upload
test_upload:
	twine upload --repository testpypi dist/bluelock-*.whl dist/bluelock-*.tar.gz


.PHONY: upload
upload:
	twine upload dist/bluelock-*.whl dist/bluelock-*.tar.gz