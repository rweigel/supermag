import supermag

import certifi
cafile_default = certifi.where()

def test_get(userid=None):

  url = "https://hapi-server.org/servers/TestData2.0/hapi/catalog"
  response, error = supermag.util.get(url, cafile=cafile_default)
  assert error is None, f"Error occurred: {error}"
  assert response is not None, "No response received"


def test_data(userid=None):
  args = ['ABK', '2000-01-01', 60]

  cafile = None
  data = supermag.data(userid, *args, cafile=cafile, ignore_cache=True)
  assert data is not None, "No data received"

  cafile = 'default'
  data = supermag.data(userid, *args, cafile=cafile, ignore_cache=True)
  assert data is not None, "No data received"

  data = supermag.data(userid, *args, cafile=cafile, ignore_cache=True)
  assert data is not None, "No data received"


def test_locations(userid=None):

  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-03',
    'station_id': 'DRV'
  }
  inventory = supermag.inventory(userid, **kwargs)

  kwargs = {
    'update': True,
    'station_id': 'DRV',
    'inventory': inventory
  }

  cafile = None
  locations = supermag.locations(userid, cafile=cafile, **kwargs)
  assert locations is not None, "No output"

  cafile = 'default'
  locations = supermag.locations(userid, cafile=cafile, **kwargs)
  assert locations is not None, "No output"

  cafile = cafile_default
  locations = supermag.locations(userid, cafile=cafile, **kwargs)
  assert locations is not None, "No output"


def test_inventory(userid=None):
  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-03',
    'station_id': 'DRV',
    'update_inventory': True,
    'update_locations': True,
  }

  cafile = None
  inventory = supermag.inventory(None, cafile=cafile, **kwargs)
  assert inventory is not None, "No output"

  cafile = 'default'
  inventory = supermag.inventory(userid, cafile=cafile, **kwargs)
  assert inventory is not None, "No output"

  cafile = cafile_default
  inventory = supermag.inventory(userid, cafile=cafile, **kwargs)
  assert inventory is not None, "No output"


def test_catalog(userid=None):

  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-03',
    'update_inventory': True,
    'update_locations': True,
    'dataset': 'DRV/baseline_none/PT1M/XYZ'
  }

  cafile = None
  catalog = supermag.catalog(userid, cafile=cafile, **kwargs)
  assert catalog is not None, "No output"

  cafile = 'default'
  catalog = supermag.catalog(userid, cafile=cafile, **kwargs)
  assert catalog is not None, "No output"

  cafile = cafile_default
  catalog = supermag.catalog(userid, cafile=cafile, **kwargs)
  assert catalog is not None, "No output"


if __name__ == "__main__":
  import sys
  from supermag.util import logger
  logger.setLevel('DEBUG')

  args = sys.argv
  if len(args) == 2:
    userid = args[1]
  else:
    print("Usage: python test_cafile.py USERID")

  test_get(userid)
  test_data(userid)
  test_locations(userid)
  test_inventory(userid)
  test_catalog(userid)