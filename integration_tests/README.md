# wazo-provd integration tests

This README attempts to document various bits of information pertaining to the integration tests for
this project.

## Running tests

```bash
# Create a new virtual environment
python3 -m venv provd_tests
# activate virtual environement
. ./provd_tests/bin/activate
# Install the requirements
pip install -r test-requirements.txt
make test-setup
# Run the tests
make test
# or
nosetests -x
```

## assets/provd/plugins/pkgs/test-plugin

The integration tests use a test plugin that does nothing but to provide the basic functionality of a normal phone plugin,
such as package management and synchronization. The source code of this plugin is available on the wazo-provd-plugin repo
and can be built using the traditional method, as described in the documentation. However, it should be noted that the
plugins.db file located in the assets folder should be updated as well, using the information found in the plugins.db file
from wazo-provd-plugin once the plugins have been rebuilt.
