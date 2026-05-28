SPHINXOPTS  ?=
SPHINXBUILD ?= sphinx-build
SOURCEDIR   = source
BUILDDIR    = _build

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

html:
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo ""
	@echo "Build finished.  Open $(BUILDDIR)/html/index.html"

clean:
	@rm -rf "$(BUILDDIR)" "$(SOURCEDIR)/generated"
	@echo "Build directory cleaned."

.PHONY: help html clean
