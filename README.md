<p align="center"><img src="https://github.com/wazo-platform/wazo-platform.org/raw/master/static/images/logo.png" height="200"></p>

# wazo-provd

[![Build Status](https://jenkins.wazo.community/buildStatus/icon?job=wazo-provd)](https://jenkins.wazo.community/job/wazo-provd)

wazo-provd is the phone provisioning server of Wazo Platform. It handles multiple brands of phones
via plugins provided by Wazo and the community.

## Installation

The provisioning server is already provided as a part of [Wazo Platform](https://wazo-platform.org/uc-doc/).
Please refer to [the documentation](https://wazo-platform.org/uc-doc/installation/install-system) for
further details on installing one.

## Usage

On a Wazo Platform environment, wazo-provd is launched automatically at system boot via a systemd service.

## Configuration

wazo-provd is different from our other services when it comes to configuration. Being an older
project, it has a few oddities such as a JSON file that defines the provisioning plugin source.
It is in the file `/var/lib/wazo-provd/app.json`.

## Development

wazo-provd is written in Python 3 ported from Python 2 using the Twisted networking framework. The REST API is located in the file `provd/rest/server/server.py`.

## Testing

### Running unit tests

```bash
apt-get install python3-dev libffi-dev libssl-dev
pip install tox
tox --recreate -e py311
```

### Running integration tests

You need Docker installed.

```sh
cd integration_tests
pip install -U -r test-requirements.txt
make test-setup
make test
```

## Contributing

You can learn more on how to contribute in the [Wazo Platform documentation](https://wazo-platform.org/contribute/code).

## How to get help

If you ever need help from the Wazo Platform community, the following resources are available:

* [Discourse](https://wazo-platform.discourse.group/)
* [Mattermost](https://mm.wazo.community)

## License

wazo-provd is released under the GPL 3.0 license. You can get the full license in the [LICENSE](LICENSE) file.
