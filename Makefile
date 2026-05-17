COLLECTION = jdevera.truenas
DOCS_DIR = docs
RM = rm -rf

# Lint / typecheck / validate / docs checks live in
# .pre-commit-config.yaml. Run them via `pre-commit run --all-files`,
# or invoke any tool directly via `uv run --with X tool ...`.
#
# The docs site is built and deployed to GitHub Pages by
# .github/workflows/docs.yml on push to main. To preview locally:
#
#   scripts/prepare-collection-layout.sh
#   uv run \
#     --with 'ansible-core>=2.13.0' --with antsibull-docs \
#     --with antsibull-changelog --with sphinx \
#     --with sphinx_ansible_theme \
#     bash docs/build.sh
#   open docs/build/html/index.html

all::

# Build a tarball that can be uploaded as an Ansible collection.
tarball:
	uv run --with ansible-core ansible-galaxy collection build --force

clean::
	${RM} -r plugins/*/__pycache__
	${RM} $(subst .,-,${COLLECTION})-*.tar.gz
	${RM} -r ${DOCS_DIR}/build/ ${DOCS_DIR}/temp-rst/ ${DOCS_DIR}/rst/
	${RM} ansible_collections
