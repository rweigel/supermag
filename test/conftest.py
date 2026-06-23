import pytest

# Allow pytest to accept a --userid command-line option.

def pytest_addoption(parser):
  parser.addoption(
    '--userid',
    action='store',
    default=None,
    help='SuperMAG user ID for integration tests.',
  )


def pytest_configure(config):
  # Sets util.userid, which is accessed in test scripts.
  import os
  import util # util.py in dir of this script.
  # TODO: Implement SUPERMAG_USERID environment variable.
  userid = config.getoption('--userid') or os.environ.get('SUPERMAG_USERID')
  if not userid:
    raise pytest.UsageError(
      'Missing SuperMAG user ID. Pass --userid USERID.'
    )
  util.userid = userid