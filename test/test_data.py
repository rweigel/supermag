from datetime import datetime

import supermag
from util import userid, check_output, check_equivalent

# Change to True after this script is complete.
ignore_cache = True

def test_default():

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 60, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, n_records=1, output_file="response for default test")


def test_start():
  starts = ['2001-01-01', '2001-01-01T00Z', '2001-01-01T00:00Z', '2001-01-01T00:00:00.000Z']
  for start in starts:
    data, error = supermag.data(userid, 'ABK', start, 60, ignore_cache=ignore_cache)
    assert error is None, f"Expected no error in response for start {start}, found: {error}"
    check_output(data, n_records=1, output_file=f"response with start {start}")


def test_extent_is_stop():
  stop = '2001-01-01T00:01Z'
  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', stop, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response for stop {stop}, found: {error}"
  check_output(data, n_records=1, output_file=f"response with stop {stop}")

  stop = '2001-01-01T00:10Z'
  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', stop, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response for stop {stop}, found: {error}"
  check_output(data, n_records=10, output_file=f"response with stop {stop}")


def test_format():
  all_formats = {}
  for format in ['json', 'csv', 'dataframe', 'list']:
    data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 60, format=format, ignore_cache=ignore_cache)
    assert error is None, f"Expected no error in response, found: {error}"
    check_output(data, n_records=1, format=format)
    all_formats[format] = data

  check_equivalent(all_formats)

def test_options():

  tests = [
    {
      'comment': "On table page, 'Subtract Baseline' selected and 'Subtract start value' unchecked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=60&logon=superhapi&station=ABK&delta=none&baseline=all&mlt&decl&sza&glat&glon',
      'options': {'extent': 60, 'baseline': 'all', 'delta': 'none'},
      'expected': [{"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": -0.798087, "geo": -0.622084}, "E": {"nez": -1.956784, "geo": -2.019643}, "Z": {"nez": 3.239859, "geo": 3.239859}}]
    },
    {
      'comment': "On table page, 'Subtract Baseline' selected and 'Subtract start value' checked",
      'table': '',
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=120&logon=superhapi&station=ABK&delta=start&baseline=all&mlt&decl&sza&glat&glon',
      'options': {'extent': 120, 'baseline': 'all', 'delta': 'start'},
      'expected':
        [
          {"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": 0.000000, "geo": 0.000000}, "E": {"nez": 0.000000, "geo": 0.000000}, "Z": {"nez": 0.000000, "geo": 0.000000}},
          {"tval":978307260.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.634668, "mcolat": 24.785370, "decl": 5.068690, "sza": 133.307465, "N": {"nez": 0.034186, "geo": 0.032512}, "E": {"nez": 0.017443, "geo": 0.020395}, "Z": {"nez": 0.021014, "geo": 0.021014}}
        ]
    },

    {
      'comment': "On table page, 'Do Not Remove Daily Baseline' selected and 'Subtract start value' unchecked",
      'url': "https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=60&logon=superhapi&station=ABK&delta=none&baseline=yearly&mlt&decl&sza&glat&glon",
      'options': {'extent': 60, 'baseline': 'yearly', 'delta': 'none'},
      'expected': [{"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": -2.192383, "geo": -2.187099}, "E": {"nez": 0.037229, "geo": -0.156614}, "Z": {"nez": -1.468750, "geo": -1.468750}}]
    },
    {
      'comment': "On table page, 'Do Not Remove Daily Baseline' selected and 'Subtract start value' checked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=120&logon=superhapi&station=ABK&delta=start&baseline=yearly&mlt&decl&sza&glat&glon',
      'options': {'extent': 120, 'baseline': 'yearly', 'delta': 'start'},
      'expected':
        [
          {"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": 0.000000, "geo": 0.000000}, "E": {"nez": 0.000000, "geo": 0.000000}, "Z": {"nez": 0.000000, "geo": 0.000000}},
          {"tval":978307260.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.634668, "mcolat": 24.785370, "decl": 5.068690, "sza": 133.307465, "N": {"nez": 0.000000, "geo": 0.000011}, "E": {"nez": -0.000121, "geo": -0.000120}, "Z": {"nez": 0.000000, "geo": 0.000000}}
        ]
    },

    {
      'comment': "On table page, 'Do Not Remove Any Baseline' selected and 'Subtract start value' unchecked and 'Subtract median value' unchecked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=60&logon=superhapi&station=ABK&delta=none&baseline=none&mlt&decl&sza&glat&glon',
      'options': {'extent': 60, 'baseline': 'none', 'delta': 'none'},
      'expected': [{"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": 11490.268555, "geo": 11445.125093}, "E": {"nez": 2.384387, "geo": 1017.540544}, "Z": {"nez": 51368.906250, "geo": 51368.906250}}]
    },
    {
      'comment': "On table page, 'Do Not Remove Any Baseline' selected and 'Subtract start value' checked and 'Subtract median value' unchecked",
      'url': 'https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=120&logon=superhapi&station=ABK&delta=start&baseline=none&mlt&decl&sza&glat&glon',
      'options': {'extent': 120, 'baseline': 'none', 'delta': 'start'},
      'expected':
          [
            {"tval":978307200.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.617976, "mcolat": 24.785370, "decl": 5.068689, "sza": 133.343750, "N": {"nez": 0.000000, "geo": 0.000000}, "E": {"nez": 0.000000, "geo": 0.000000}, "Z": {"nez": 0.000000, "geo": 0.000000}},
            {"tval":978307260.000000, "ext": 60.000000, "iaga": "ABK", "mlt": 1.634668, "mcolat": 24.785370, "decl": 5.068690, "sza": 133.307465, "N": {"nez": 0.000000, "geo": 0.000012}, "E": {"nez": -0.000140, "geo": -0.000139}, "Z": {"nez": 0.000000, "geo": 0.000000}}
        ]
    }
  ]

  for test in tests:
    delta = test['options']['delta']
    baseline = test['options']['baseline']
    extent = test['options']['extent']
    expected = test['expected']

    data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', extent, delta=delta, baseline=baseline, ignore_cache=ignore_cache)
    if error is not None:
      assert False, f"Expected no error in response, found: {error}"
    for r in range(len(expected)):
      del data[r]['tval_iso']
      assert data[r] == expected[r], f"Expected response\n  {expected[r]}\ngot\n  {data[r]}"


def test_full_day_request():

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 86400, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, n_records=1440, output_file="response for multi-day request")
  t_val_last = 978393540.0 # 2001-01-01T23:59:00Z
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


def test_half_day_request():
  n_records = 720
  extent = n_records * 60
  stop = '2001-01-01T11:59:00+00:00'
  t_val_last = datetime.fromisoformat(stop).timestamp()

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', extent, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, n_records=720, output_file="response for multi-day request")
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


def test_one_and_half_day_request():
  n_records = 1440 + 720
  extent = n_records * 60
  stop = '2001-01-02T11:59:00+00:00'
  t_val_last = datetime.fromisoformat(stop).timestamp()

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', extent, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, n_records=n_records, output_file="response for multi-day request")
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


if __name__ == '__main__':
  test_options()
  exit()
  test_default()
  test_start()
  test_extent_is_stop()
  test_format()
  test_full_day_request()
  test_half_day_request()
  test_one_and_half_day_request()