# Usage:
#   pytest test_mag.py --userid USERID
#   python test_mag.py --userid USERID
from datetime import datetime

import supermag
from util import userid, check_output, check_equivalent

# Change to False after this script is complete.
use_cache = False

def test_default(userid=userid):

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 60, use_cache=use_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, dataset_type='mag', n_records=1, output_target="response for default test")


def test_start(userid=userid):
  starts = ['2001-01-01', '2001-01-01T00Z', '2001-01-01T00:00Z', '2001-01-01T00:00:00.000Z']
  for start in starts:
    data, error = supermag.data(userid, 'ABK', start, 60, use_cache=use_cache)
    assert error is None, f"Expected no error in response for start {start}, found: {error}"
    check_output(data, dataset_type='mag', n_records=1, output_target=f"response with start {start}")


def test_extent_is_stop(userid=userid):
  stop = '2001-01-01T00:01Z'
  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', stop, use_cache=use_cache)
  assert error is None, f"Expected no error in response for stop {stop}, found: {error}"
  check_output(data, dataset_type='mag', n_records=1, output_target=f"response with stop {stop}")

  stop = '2001-01-01T00:10Z'
  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', stop, use_cache=use_cache)
  assert error is None, f"Expected no error in response for stop {stop}, found: {error}"
  check_output(data, dataset_type='mag', n_records=10, output_target=f"response with stop {stop}")


def test_format(userid=userid):
  all_formats = {}
  CONFIG = supermag.config('data')
  for format in CONFIG['formats']:
    data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 60, format=format, use_cache=use_cache)
    assert error is None, f"Expected no error in response, found: {error}"
    check_output(data, dataset_type='mag', n_records=1, format=format)
    all_formats[format] = data

  check_equivalent(all_formats)


def _run(station, start, extent, userid=userid):
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


def test_data(userid=userid):
  _run('DRV', '1970-01-01T00:00Z', 86400, userid=userid)
  _run('ABK', '2001-01-01T00:00Z', 86400, userid=userid)
  _run('ABK', '1979-01-01T00:00Z', 86400, userid=userid)

def test_options(userid=userid):
  # Replace LOGON in urls with your actual SuperMAG user ID.
  # Table: https://supermag.jhuapl.edu/line/?fidelity=low&start=2001-01-01T00%3A00%3A00.000Z&interval=2%3A00%3A00&stations=ABK&tab=view
  tests = [
    {
      'comment': "On table page, 'Subtract Baseline' selected and 'Subtract start value' unchecked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=60&logon=LOGON&station=ABK&delta=none&baseline=all&mlt&geo&decl&sza',
      'options': {'extent': 60, 'baseline': 'all', 'delta': 'none'},
      'expected': [{"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": -0.798087, "geo": -0.622084}, "E": {"nez": -1.956784, "geo": -2.019643}, "Z": {"nez": 3.239859, "geo": 3.239859}}]
    },
    {
      'comment': "On table page, 'Subtract Baseline' selected and 'Subtract start value' checked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=120&logon=LOGON&station=ABK&delta=start&baseline=all&mlt&geo&decl&sza',
      'options': {'extent': 120, 'baseline': 'all', 'delta': 'start'},
      'expected':
        [
          {"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": 0.000000, "geo": 0.000000}, "E": {"nez": 0.000000, "geo": 0.000000}, "Z": {"nez": 0.000000, "geo": 0.000000}},
          {"tval":978307260.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.634668, "mcolat": 24.785370, "decl": 5.068690, "sza": 133.307465, "N": {"nez": 0.034186, "geo": 0.032512}, "E": {"nez": 0.017443, "geo": 0.020395}, "Z": {"nez": 0.021014, "geo": 0.021014}}
        ]
    },

    {
      'comment': "On table page, 'Do Not Remove Daily Baseline' selected and 'Subtract start value' unchecked",
      'url': "https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=60&logon=LOGON&station=ABK&delta=none&baseline=yearly&mlt&geo&decl&sza",
      'options': {'extent': 60, 'baseline': 'yearly', 'delta': 'none'},
      'expected': [{"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": -2.192383, "geo": -2.187099}, "E": {"nez": 0.037229, "geo": -0.156614}, "Z": {"nez": -1.468750, "geo": -1.468750}}]
    },
    {
      'comment': "On table page, 'Do Not Remove Daily Baseline' selected and 'Subtract start value' checked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=120&logon=LOGON&station=ABK&delta=start&baseline=yearly&mlt&geo&decl&sza',
      'options': {'extent': 120, 'baseline': 'yearly', 'delta': 'start'},
      'expected':
        [
          {"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": 0.000000, "geo": 0.000000}, "E": {"nez": 0.000000, "geo": 0.000000}, "Z": {"nez": 0.000000, "geo": 0.000000}},
          {"tval":978307260.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.634668, "mcolat": 24.785370, "decl": 5.068690, "sza": 133.307465, "N": {"nez": 0.000000, "geo": 0.000011}, "E": {"nez": -0.000121, "geo": -0.000120}, "Z": {"nez": 0.000000, "geo": 0.000000}}
        ]
    },

    {
      'comment': "On table page, 'Do Not Remove Any Baseline' selected and 'Subtract start value' unchecked and 'Subtract median value' unchecked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=60&logon=LOGON&station=ABK&delta=none&baseline=none&mlt&decl&sza&glat&glon',
      'options': {'extent': 60, 'baseline': 'none', 'delta': 'none'},
      'expected': [{"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": 11490.268555, "geo": 11445.125093}, "E": {"nez": 2.384387, "geo": 1017.540544}, "Z": {"nez": 51368.906250, "geo": 51368.906250}}]
    },
    {
      'comment': "On table page, 'Do Not Remove Any Baseline' selected and 'Subtract start value' checked and 'Subtract median value' unchecked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=120&logon=LOGON&station=ABK&delta=start&baseline=none&mlt&decl&sza&glat&glon',
      'options': {'extent': 120, 'baseline': 'none', 'delta': 'start'},
      'expected':
          [
            {"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": 0.000000, "geo": 0.000000}, "E": {"nez": 0.000000, "geo": 0.000000}, "Z": {"nez": 0.000000, "geo": 0.000000}},
            {"tval":978307260.000000, "ext": 60.000000, "iaga": "ABK", 'glon': 18.82, 'glat': 68.349998, "mlt": 1.634668, "mcolat": 24.785370, "decl": 5.068690, "sza": 133.307465, "N": {"nez": 0.000000, "geo": 0.000012}, "E": {"nez": -0.000140, "geo": -0.000139}, "Z": {"nez": 0.000000, "geo": 0.000000}}
        ]
    }
  ]

  for test in tests:
    delta = test['options']['delta']
    baseline = test['options']['baseline']
    extent = test['options']['extent']
    expected = test['expected']

    data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', extent, delta=delta, baseline=baseline, use_cache=use_cache)
    if error is not None:
      assert False, f"Expected no error in response, found: {error}"
    for idx in range(len(expected)):
      assert data[idx] == expected[idx], f"Expected response\n  {expected[idx]}\ngot\n  {data[idx]}"


def test_full_day_request(userid=userid):

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 86400, use_cache=use_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, dataset_type='mag', n_records=1440, output_target="response for multi-day request")
  t_val_last = 978393540.0 # 2001-01-01T23:59:00Z
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


def test_half_day_request(userid=userid):
  n_records = 720
  extent = n_records * 60
  stop = '2001-01-01T11:59:00+00:00'
  t_val_last = datetime.fromisoformat(stop).timestamp()

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', extent, use_cache=use_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, n_records=720, output_target="response for multi-day request")
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


def test_one_and_half_day_request(userid=userid):
  n_records = 1440 + 720
  extent = n_records * 60
  stop = '2001-01-02T11:59:00+00:00'
  t_val_last = datetime.fromisoformat(stop).timestamp()

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', extent, use_cache=use_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, n_records=n_records, output_target="response for multi-day request")
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


if __name__ == "__main__":
  from util import parse_args
  args = parse_args()

  test_default(userid=args.userid)
  test_format(userid=args.userid)
  test_data(userid=args.userid)
  test_options(userid=args.userid)
  test_full_day_request(userid=args.userid)
  test_half_day_request(userid=args.userid)
  test_one_and_half_day_request(userid=args.userid)
