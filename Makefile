COLLECTION = jdevera.truenas
# Directory where generated HTML docs will go
DOCS_DIR = docs

PYTHON = python3

# Root of the documentation web site repo.
#
# This can be either a relative or absolute path, and it may point to
# a subdirectory within a git repo: You might use /path/to/dir as the
# repo for an entire web site, and use /path/to/dir/truenas for that
# portion of the site that documents this collection. In this case you
# would use
# DOCS_SITE = /path/to/dir/truenas
DOCS_SITE = docs-site/truenas

RM = rm -rf

# See whether this is a dry run
ifneq (,$(findstring n,$(MAKEFLAGS)))
RSYNC_DRYRUN=-n
endif

all::

clean::
	${RM} -r plugins/*/__pycache__

# Build a tarball that can be uploaded as an Ansible collection.
tarball:	docs
	ansible-galaxy collection build --force

# Delete any stray arensb-truenas-*.tar.gz tarballs.
clean::
	${RM} $(subst .,-,${COLLECTION})-*.tar.gz

compatibility-link:
	@scripts/prepare-collection-layout.sh

documentation:	venv-docs compatibility-link plugins/modules/*.py
	(. venv-docs/bin/activate; \
	    cd ${DOCS_DIR}; \
	    pip install -r requirements.txt; \
	    ANSIBLE_COLLECTIONS_PATHS=.. ./build.sh; \
	)

venv-docs:	requirements.txt
	$(PYTHON) -m venv venv-docs
	venv-docs/bin/pip install -r requirements.txt

clean::
	${RM} -r ${DOCS_DIR}/build/
	${RM} -r ${DOCS_DIR}/temp-rst/
	${RM} -r ${DOCS_DIR}/rst/

distclean::	clean
	${RM} venv-docs

# Copy the generated docs to the docs website repository.
update-doc-site:	documentation
	+rsync ${RSYNC_DRYRUN} \
		 -avi \
		--delete \
		docs/build/html/ ${DOCS_SITE}/
	(cd ${DOCS_SITE}; \
	 git add . ; \
	 git commit -m "Automatic update."; \
	)
	echo "Don't forget to git push the docs site."

# All lint / typecheck / validate / docs checks are driven by
# 'pre-commit run --all-files'. See .pre-commit-config.yaml and the
# scripts/ directory for the wiring. There are no Makefile targets
# that wrap them — call pre-commit directly, or invoke the underlying
# tools via uv (e.g. `uv run --with ruff ruff check plugins/`).
