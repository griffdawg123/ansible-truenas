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

# Generate list of modules from plugins/modules/*.py:
# List the files, strip the directory name and .py suffix, then
# add the collection name in front, so
# plugins/modules/foo.py -> arensb.truenas.foo
MODULES = $(addprefix ${COLLECTION}., \
	$(basename \
	$(notdir \
	$(wildcard plugins/modules/*.py))))

check-docs:	ansible_collections/$(subst .,/,${COLLECTION})
	ANSIBLE_COLLECTIONS_PATH=. \
	uv run --with ansible-core ansible-doc \
		-M .\
		--json \
		--type module \
		${MODULES} >/dev/null

# This is a crude hack: make a symlink to fool 'ansible-doc': it looks
# for module foo.bar.baz in
# $ANSIBLE_COLLECTIONS_PATH/ansible_collections/foo/bar/baz.py
compatibility-link:	ansible_collections/$(subst .,/,${COLLECTION})

ansible_collections/$(subst .,/,${COLLECTION}):
	install -d -m 775 `dirname "$@"`
	ln -s ../.. $@

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

# Individual checks. The unified entry point is `pre-commit run
# --all-files`, which runs all of these and reports each one's status
# in one pass. The targets below are kept so pre-commit can call them
# and so each check is still reachable on its own.

lint::
	$(PYTHON) -m py_compile plugins/*/*.py
	uv run --with ruff ruff check plugins/

# Run the official Ansible validation suite against this collection
# (ansible-test's 'sanity' subcommand: pep8, validate-modules,
# ansible-doc, import, etc.). The underlying subcommand name comes
# from ansible-core; we expose it locally as 'validate'.
#
# ansible-test sanity insists that the current working directory be
# inside an ansible_collections/<ns>/<name>/ tree, and it resolves
# symlinks before checking that, so the compatibility-link approach
# doesn't satisfy it. Instead, rsync the source into a temp tree and
# run from there.
validate:
	@tmp=$$(mktemp -d) && \
	dest="$$tmp/ansible_collections/$(subst .,/,${COLLECTION})" && \
	mkdir -p "$$dest" && \
	rsync -aq --exclude=.git --exclude=ansible_collections --exclude=__pycache__ \
	    --exclude=venv-docs --exclude=tests/output --exclude=.venv \
	    --exclude=.local ./ "$$dest/" && \
	UV_PROJECT_ENVIRONMENT="$$tmp/.uvenv" \
	(cd "$$dest" && \
	 UV_PROJECT_ENVIRONMENT="$$tmp/.uvenv" \
	 uv run --with ansible-core ansible-test sanity --venv --color); \
	rc=$$?; rm -rf "$$tmp"; exit $$rc

# Type-check with mypy. Has to be invoked through the
# ansible_collections/$(subst .,/,${COLLECTION}) path so that the
# 'from ..module_utils import setup' relative imports inside plugins/
# resolve to the same namespace package that Ansible uses at runtime.
# Config lives in pyproject.toml ([tool.mypy]).
typecheck:	compatibility-link
	uv run --with mypy --with ansible-core mypy \
	    ansible_collections/$(subst .,/,${COLLECTION})/plugins/
