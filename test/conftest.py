import os

import pytest

import util


def pytest_addoption(parser):
  parser.addoption(
    '--userid',
    action='store',
    default=None,
    help='SuperMAG user ID for integration tests. Can also be set with SUPERMAG_USERID.',
  )


def pytest_configure(config):
  userid = config.getoption('--userid') or os.environ.get('SUPERMAG_USERID')
  if not userid:
    raise pytest.UsageError(
      'Missing SuperMAG user ID. Pass --userid USERID or set SUPERMAG_USERID.'
    )
  util.userid = userid