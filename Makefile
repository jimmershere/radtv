# B@Dtv build orchestrator.
#
#   make help     - list targets
#   make repo     - rebuild dist/*.zip + addons.xml + md5
#   make assets   - rasterize SVG branding -> PNG/JPG, copy into addon dirs
#   make iptv     - fetch + merge IPTV sources -> iptv/dist/badtv.{m3u,xml}
#   make install  - run install.sh against the local Kodi userdata
#   make clean    - drop dist/ and iptv/dist/ contents
#   make all      - assets + repo + iptv
#
# All targets are safe to re-run.

SHELL := /bin/bash

WIZARD_ID    := script.badtv.wizard
WIZARD_VER   := 2.0.0
REPO_ID      := repository.badtv
REPO_VER     := 2.0.0

DIST         := dist
WIZARD_DIR   := build/wizard
REPO_DIR     := build/repository

WIZARD_ZIP   := $(DIST)/$(WIZARD_ID)-$(WIZARD_VER).zip
REPO_ZIP     := $(DIST)/$(REPO_ID)-$(REPO_VER).zip

.PHONY: help all repo assets iptv install clean check catalog stage-bundle

help:
	@awk -F':.*##' '/^[a-zA-Z_-]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

all: assets iptv catalog repo  ## Build everything

assets:  ## Rasterize SVG branding into PNG/JPG
	bash tools/render-assets.sh

iptv:  ## Build merged IPTV playlist + EPG
	python3 iptv/build-playlist.py

catalog:  ## Probe third-party scraper repos + refresh addons/scraper-catalog.json
	python3 tools/refresh-scrapers.py --print-summary

stage-bundle:  ## Copy catalog (and other runtime bundles) into the wizard tree
	mkdir -p $(WIZARD_DIR)/resources/data
	cp addons/scraper-catalog.json $(WIZARD_DIR)/resources/data/scraper-catalog.json

repo: stage-bundle $(WIZARD_ZIP) $(REPO_ZIP) $(REPO_DIR)/addons.xml.md5  ## Rebuild dist/*.zip + addons.xml + md5

$(DIST):
	mkdir -p $(DIST)

$(WIZARD_ZIP): $(DIST) stage-bundle
	@echo "Packing $(WIZARD_ID) v$(WIZARD_VER)..."
	rm -f "$@"
	cd build && zip -qr "../$@" wizard \
	  --exclude 'wizard/__pycache__/*' \
	  --exclude 'wizard/**/__pycache__/*' \
	  --exclude 'wizard/*.pyc'
	@# rename top-level dir inside the zip from `wizard` to the addon id
	@command -v zipnote >/dev/null && python3 tools/build-repo.py rename-zip-root "$@" wizard "$(WIZARD_ID)" || true

$(REPO_ZIP): $(DIST)
	@echo "Packing $(REPO_ID) v$(REPO_VER)..."
	rm -f "$@"
	cd build && zip -qr "../$@" repository \
	  --exclude 'repository/addons.xml.md5'
	@command -v zipnote >/dev/null && python3 tools/build-repo.py rename-zip-root "$@" repository "$(REPO_ID)" || true

$(REPO_DIR)/addons.xml.md5: $(REPO_DIR)/addons.xml
	md5sum $< | awk '{print $$1}' > $@

install:  ## Apply B@Dtv to the local Kodi userdata
	bash install.sh

check:  ## Lint XML + run wizard smoke tests
	python3 -c "import xml.etree.ElementTree as ET; \
	  [ET.parse(p) for p in ['$(WIZARD_DIR)/addon.xml','$(REPO_DIR)/addon.xml','$(REPO_DIR)/addons.xml']]; \
	  print('xml ok')"
	python3 -c "import json; json.load(open('addons/scraper-catalog.json')); print('catalog json ok')"
	cd $(WIZARD_DIR) && PYTHONPATH=resources python3 -c "from lib import badtv_wizard, actions, sources_xml, pvr_iptv, catalog, network; print('wizard imports ok')"
	python3 iptv/build-playlist.py --dry-run --only-id pluto-us || true
	python3 tools/refresh-scrapers.py --dry-run --only-id umbrella || true

clean:  ## Delete built artifacts
	rm -rf $(DIST)/*.zip iptv/dist/*.m3u iptv/dist/*.xml assets/branding/*.png assets/branding/*.jpg
	rm -rf $(WIZARD_DIR)/resources/data
	@echo "cleaned."
