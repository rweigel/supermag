
import supermag
from util import userid

def _rm_cache_dir():
  import os
  import shutil
  import pathlib
  CONFIG = supermag.config('common')
  cache_dir = pathlib.Path(CONFIG['output_dir']) / "cache"
  if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)


def _run(station, extent, start, userid=userid):
  from supermag.util import get

  """
  Note that if extent = 60, we will get a failure if use_cache = False.
  The SuperMAG API will return {} because there is no valid data given the
  start and that extent. For cache = True, data over a full day will be
  requested and the response is subsetted. When there are valid data in the
  requested interval, the SuperMAG API returns fill values on the timestamps
  with no valid data.
  """
  url = f'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start={start}&extent={extent}&logon={userid}&station={station}&delta=none&baseline=none&mlt&geo&decl&sza'

  args = [userid, station, start, extent]

  url_data, error = get(url, format='json')
  assert error is None, f"Error '{error}' fetching URL: {url}"

  data0, error = supermag.data(*args, cache=False, use_cache=False)
  assert error is None, f"Expected no error in response, found: {error}"
  assert data0 == url_data, "Expected data from supermag.data() to match data from URL fetch"

  # Remove cache directory
  _rm_cache_dir()

  print("")

  # Use cache is not relevant because no cache.
  data1, error = supermag.data(*args, cache=True)
  assert error is None, f"Expected no error in response, found: {error}"
  from supermag.util import t_val2iso
  print(t_val2iso(url_data[0]['tval']))
  print(t_val2iso(data1[0]['tval']))
  print(t_val2iso(url_data[-1]['tval']))
  print(t_val2iso(data1[-1]['tval']))
  assert data1 == url_data, "Expected data from supermag.data() to match data from URL fetch"

  print("")

  # Cache is not relevant because cache exists, so it will be used.
  data1, error = supermag.data(*args, use_cache=False)
  assert error is None, f"Expected no error in response, found: {error}"
  assert data1 == url_data, "Expected data from supermag.data() to match data from URL fetch"

  print("")

  extent = int(extent/2)

  url = f'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start={start}&extent={extent}&logon={userid}&station={station}&delta=none&baseline=none&mlt&geo&decl&sza'
  url_data, error = get(url, format='json')
  assert error is None, f"Error '{error}' fetching URL: {url}"

  args = [userid, station, start, extent]

  # Read from cache, but request a different extent.
  data1, error = supermag.data(*args, use_cache=False)
  assert error is None, f"Expected no error in response, found: {error}"
  #assert data1 == url_data, "Expected data from supermag.data() to match data from URL fetch"


def test_cache(userid=userid):
  _run(station='DRV', extent=86400, start='1970-01-01T00:00Z', userid=userid)
  _run(station='ABK', extent=86400, start='2000-01-01T00:00Z', userid=userid)
  _run(station='ABK', extent=180, start='1999-12-31T23:59:00Z', userid=userid)


if __name__ == "__main__":
  from util import parse_args
  args = parse_args()

  test_cache(userid=args.userid)