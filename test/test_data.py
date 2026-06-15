from datetime import datetime

import supermag
from util import _check_output, userid

ignore_cache = False

def test_default():

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 60, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  _check_output(data, n_records=1, output_file="response for default test")


def test_start():
  starts = ['2001-01-01', '2001-01-01T00Z', '2001-01-01T00:00Z', '2001-01-01T00:00:00.000Z']
  for start in starts:
    data, error = supermag.data(userid, 'ABK', start, 60, ignore_cache=ignore_cache)
    assert error is None, f"Expected no error in response for start {start}, found: {error}"
    _check_output(data, n_records=1, output_file=f"response with start {start}")


def test_extent_is_stop():
  stop = '2001-01-01T00:01Z'
  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', stop, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response for stop {stop}, found: {error}"
  _check_output(data, n_records=1, output_file=f"response with stop {stop}")

  stop = '2001-01-01T00:10Z'
  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', stop, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response for stop {stop}, found: {error}"
  _check_output(data, n_records=10, output_file=f"response with stop {stop}")


def test_format():
  for format in ['json', 'csv', 'dataframe', 'list']:
    data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 60, format=format, ignore_cache=ignore_cache)
    assert error is None, f"Expected no error in response, found: {error}"
    _check_output(data, n_records=1, format=format)


def test_full_day_request():

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', 86400, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  _check_output(data, n_records=1440, output_file="response for multi-day request")
  t_val_last = 978393540.0 # 2001-01-01T23:59:00Z
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


def test_half_day_request():
  n_records = 720
  extent = n_records * 60
  stop = '2001-01-01T11:59:00+00:00'
  t_val_last = datetime.fromisoformat(stop).timestamp()

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', extent, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  _check_output(data, n_records=720, output_file="response for multi-day request")
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


def test_one_and_half_day_request():
  n_records = 1440 + 720
  extent = n_records * 60
  stop = '2001-01-02T11:59:00+00:00'
  t_val_last = datetime.fromisoformat(stop).timestamp()

  data, error = supermag.data(userid, 'ABK', '2001-01-01T00:00:00Z', extent, ignore_cache=ignore_cache)
  assert error is None, f"Expected no error in response, found: {error}"
  _check_output(data, n_records=n_records, output_file="response for multi-day request")
  assert data[-1]['tval'] == t_val_last, f"Expected tval {t_val_last} in last row of multi-day response, found {data[0]['tval']}"


if __name__ == '__main__':
  test_default()
  test_start()
  test_extent_is_stop()
  test_format()
  test_full_day_request()
  test_half_day_request()
  test_one_and_half_day_request()