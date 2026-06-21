# Usage:
#   pytest test_cafile.py --userid USERID
#   python test_cafile.py --userid USERID

import supermag

from util import userid

import certifi
cafile_default = certifi.where()


def test_get(userid=userid):

  url = "https://hapi-server.org/servers/TestData2.0/hapi/catalog"
  response, error = supermag.util.get(url, cafile=cafile_default)
  assert error is None, f"Error occurred: {error}"
  assert response is not None, "No response received"


def test_data(userid=userid):
  args = ['ABK', '2000-01-01', 60]

  cafile = None
  data = supermag.data(userid, *args, cafile=cafile, use_cache=True)
  assert data is not None, "No data received"

  cafile = 'default'
  data = supermag.data(userid, *args, cafile=cafile, use_cache=True)
  assert data is not None, "No data received"

  data = supermag.data(userid, *args, cafile=cafile, use_cache=True)
  assert data is not None, "No data received"


def test_samples(userid=userid):

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
  samples = supermag.samples(userid, cafile=cafile, **kwargs)
  assert samples is not None, "No output"

  cafile = 'default'
  samples = supermag.samples(userid, cafile=cafile, **kwargs)
  assert samples is not None, "No output"

  cafile = cafile_default
  samples = supermag.samples(userid, cafile=cafile, **kwargs)
  assert samples is not None, "No output"


def test_inventory(userid=userid):
  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-03',
    'station_id': 'DRV',
    'update_inventory': True,
    'update_locations': True,
  }

  cafile = None
  inventory = supermag.inventory(userid, cafile=cafile, **kwargs)
  assert inventory is not None, "No output"

  cafile = 'default'
  inventory = supermag.inventory(userid, cafile=cafile, **kwargs)
  assert inventory is not None, "No output"

  cafile = cafile_default
  inventory = supermag.inventory(userid, cafile=cafile, **kwargs)
  assert inventory is not None, "No output"


def test_catalog(userid=userid):

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
  from util import parse_args
  args = parse_args()

  test_get(userid=args.userid)
  test_data(userid=args.userid)
  test_samples(userid=args.userid)
  test_inventory(userid=args.userid)
  test_catalog(userid=args.userid)
