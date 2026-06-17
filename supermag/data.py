from .util import logger

from .config import config
CONFIG = config()

# If true, show response data in debug logs.
debug_response = True


def indices(userid, start, extent,
            format='json',
            cache=True,
            ignore_cache=False,
            cache_dir=CONFIG['common']['output_dir'],
            cafile=None,
            timeout=30):

  return data(userid, 'indices', start, extent,
              format=format,
              cache=cache,
              ignore_cache=ignore_cache,
              cache_dir=cache_dir,
              cafile=cafile,
              timeout=timeout)


def data(userid, stationid, start, extent,
          baseline='none',
          delta='none',
          format='json',
          cadence='PT1M',
          cache=True,
          ignore_cache=False,
          cache_dir=CONFIG['common']['output_dir'],
          cafile=None,
          timeout=30):

  _locals = locals()
  logger.debug("data() called with arguments:")
  for arg in _locals:
    logger.debug(f"  {arg}: {_locals[arg]}")

  from .util import check_userid
  check_userid(userid)

  if format not in ['json', 'list', 'dataframe', 'csv']:
    raise ValueError(f"Invalid format: {format}. Must be one of: json, list, dataframe, csv.")

  if stationid == 'indices':
    baseline = None
    delta = None
  else:
    if baseline not in ['yearly', 'all', 'none']:
      raise ValueError(f"Invalid baseline value: {baseline}. Must be one of: yearly, default, none.")

    if delta not in ['start', 'none']:
      raise ValueError(f"Invalid delta value: {delta}. Must be one of: start, none.")

  if cadence != 'PT1M':
    raise ValueError(f"Invalid cadence value: {cadence}. Only 'PT1M' (1 minute) is supported.")

  """
  delta=median not supported. It is an option in the table at
  https://supermag.jhuapl.edu/line/?fidelity=low&start=2001-01-01T00%3A00%3A00.000Z&interval=00%3A05&tab=view&stations=ABK&baseline=none&delta=median
  but the following request gives the same as delta=none.
  https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=2001-01-01T00:00Z&extent=120&logon=superhapi&station=ABK&delta=median&baseline=none&mlt&decl&sza&glat&glon

  Also, if 'Subtract median value' is checked (shows only when 'Do Not Remove
  Any Baseline' is selected), 'Subtract start value' is ignored. To see this,
  search on 'median' at https://supermag.jhuapl.edu/mag/lib/js/mag.applet.js?l=a
  So if delta=median, is supported, will need to check that baseline is 'none'
  and raise an error if not.
  """

  if isinstance(extent, str):
    extent = _stop_to_extent(start, extent)

  # Preserve the originally requested extent for sub-setting
  requested_extent = extent

  # When caching, always fetch all extra parameters and a full day
  if cache:
    seconds_per_day = 60 * 60 * 24
    # round up to full day(s)
    extent = ((extent + seconds_per_day - 1) // seconds_per_day) * seconds_per_day

  # Try to load from cache
  if cache and not ignore_cache:
    result, error = _cache_get(cache_dir, stationid, format, start, extent, requested_extent, cadence, delta=delta, baseline=baseline)
    if result is not None or error is not None:
      return result, error


  common_params = f"start={start}&extent={extent}&logon={userid}"
  if stationid == 'indices':
    url = CONFIG['data']['base_url_indices']
    url += f"&{common_params}&indices=all&swi=all&imf=all"
  else:
    # Call the SuperMAG API to get the data
    options = []
    options.append(f"delta={delta}")
    options.append(f"baseline={baseline}")
    options = '&'.join(options)
    options += '&' + '&'.join(CONFIG['data']['extra_parameters'])

    url = CONFIG['data']['base_url_data']
    url += f"&{common_params}&station={stationid}&{options}"

  data_json, error = _get_and_parse(url, stationid, format='json', cafile=cafile, timeout=timeout)
  if error is not None:
    return None, error

   # Cache the full response before sub-setting, so we have the full data available in cache for future requests.
  if cache:
    _cache_write(data_json, cache_dir, stationid, cadence, delta=delta, baseline=baseline)
    data_json = _subset(data_json, start, requested_extent)

  if format == 'json':
    return data_json, None

  return _reformat(data_json, format=format), None


def _get_and_parse(url, stationid, format='json', cafile=None, timeout=30):
  from .util import get
  try:
    data_json, error = get(url, cafile=cafile, format='json', timeout=timeout)
    if error is not None:
      logger.debug(error)
      return None, {'url': url, 'error': error}

    if debug_response:
      logger.debug(f"Raw response keys: {list(data_json[0].keys()) if data_json else 'no data'}")

    try:
      data_json = _reformat(data_json)
    except Exception as error:
      emsg = f"Failed to reformat data for {stationid}"
      logger.debug(emsg)
      error = Exception(f"{emsg}: {error}")
      return None, {'url': url, 'error': error}

  except Exception as error:
    emsg = f"data() failed for {stationid}"
    logger.debug(emsg)
    error = Exception(f"{emsg}: {error}")
    return None, {'url': url, 'error': error}

  return data_json, None


def _stop_to_extent(start, extent):
  if isinstance(extent, str):
    start_ts = _parse_timestamp(start)
    stop_ts = _parse_timestamp(extent)
    if stop_ts <= start_ts:
      raise ValueError(f"Stop time must be after start time. Got start={start} ({start_ts}), stop={extent} ({stop_ts})")
    extent = int(stop_ts - start_ts)
  return extent


def _parse_timestamp(timestamp):
  """Parse an common ISO6801 string to a Unix timestamp."""
  from datetime import datetime, timezone
  timestamp_str = str(timestamp).rstrip('Z').replace(' ', 'T')
  fmts = ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%dT%H', '%Y-%m-%d')
  for fmt in fmts:
    try:
      return datetime.strptime(timestamp_str, fmt).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
      pass
    try:
      return datetime.strptime(timestamp_str, fmt + "Z").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
      continue
  raise ValueError(f"Cannot parse timestamp: '{timestamp_str}'. Allowed: {fmts} with optional 'Z' suffix.")


def _reformat(data_json, format='json'):
  """Convert json response data to the requested format.

  `data_json` is the response from _parse_response().
  For list input, nested dicts are flattened (e.g. N.nez -> N_nez).
  """
  import pandas
  from datetime import datetime, timezone

  if format not in ['json', 'list', 'dataframe', 'csv']:
    raise ValueError("Invalid format. Must be one of: 'json', 'list', 'dataframe', 'csv'.")

  if format == 'json':
    result = []
    for row in data_json:
      iso = datetime.fromtimestamp(row['tval'], tz=timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
      result.append({'tval_iso': iso, **row})
    return result

  header = []
  for key in data_json[0]:
    if isinstance(data_json[0][key], dict):
      for subkey in data_json[0][key]:
        header.append(f"{key}_{subkey}")
    else:
      header.append(key)

  data_rows = []
  for entry in data_json:
    row = []
    for key in entry:
      if isinstance(entry[key], dict):
        for subkey in entry[key]:
          row.append(entry[key][subkey])
      else:
        row.append(entry[key])
    data_rows.append(row)

  if format == 'list':
    return [header] + data_rows

  df = pandas.DataFrame(data_rows, columns=header)
  if format == 'csv':
    for col in df.columns:
      # Reprocess columns and convert columns with list values to comma-separated strings.
      # E.g., ...,"[66.365166, 66.365166, ...]", "['ABK', 'ABC', ...]", ...
      # =>        "66.365166, 66.365166, ...", "'ABK', 'ABC', ...", ...
      if df[col].apply(lambda x: isinstance(x, list)).any():
        df[col] = df[col].apply(lambda x: ','.join(str(v) for v in x) if isinstance(x, list) else x)
    return df.to_csv(index=False).rstrip()

  # dataframe: always prepend tval_datetime
  if format == 'dataframe':
    df = df.copy()
    df.insert(0, 'tval_datetime', pandas.to_datetime(df['tval'], unit='s', utc=True))
    return df


def _subset(data, start, extent):
  """Subset data to [start, start+extent).

  Accepts either a list of dicts (JSON records) or a pandas DataFrame.
  """


  try:
    import pandas
    is_df = isinstance(data, pandas.DataFrame)
  except ImportError:
    is_df = False

  start_ts = _parse_timestamp(start)
  stop_ts = start_ts + extent if extent is not None else None

  if is_df:
    if not data.empty and stop_ts is not None:
      data = data[(data['tval'] >= start_ts) & (data['tval'] < stop_ts)]
    return data

  # list-of-dicts path
  if not data or stop_ts is None:
    return data

  return [row for row in data if start_ts <= row['tval'] < stop_ts]


def _cache_get(cache_dir, stationid, format, start, extent, requested_extent, cadence, delta=None, baseline=None):

  if False:
    _locals = locals()
    logger.debug("data._cache_get() called with arguments:")
    for arg in _locals:
      logger.debug(f"  {arg}: {_locals[arg]}")

  if format not in ['json', 'dataframe', 'csv', 'list']:
    raise ValueError("Invalid format. Must be one of: 'json', 'dataframe', 'csv', 'list'.")

  # csv/list are generated from JSON records.
  file_ext = 'dataframe' if format == 'dataframe' else 'json'
  cached = _cache_read(cache_dir, stationid, start, extent, format=file_ext, cadence=cadence, delta=delta, baseline=baseline)
  if cached is None:
    return None, None

  data = _subset(cached, start, requested_extent)

  if format == 'dataframe':
    return data, None

  return _reformat(data, format=format), None


def _cache_path(cache_dir, stationid, cadence, delta=None, baseline=None):

  if False:
    _locals = locals()
    logger.debug("data._cache_path() called with arguments:")
    for arg in _locals:
      logger.debug(f"  {arg}: {_locals[arg]}")


  import pathlib
  if cache_dir is None:
    cache_dir = pathlib.Path(__file__).resolve().parent.parent / CONFIG['common']['output_dir']
  else:
    cache_dir = pathlib.Path(cache_dir)

  if stationid == 'indices':
    sub_dir = pathlib.Path(f'indices/{cadence}')
  else:
    sub_dir = pathlib.Path(f"mag/{cadence}/{stationid}")

  delta_str = str(delta) if delta is not None else 'none'
  baseline_str = str(baseline) if baseline is not None else 'none'
  cache_path = cache_dir / sub_dir / f"baseline-{baseline_str}" / f"delta-{delta_str}"
  return cache_path


def _cache_read(cache_dir, stationid, start, extent, format='json', cadence='PT1M', delta=None, baseline=None):
  """Return cached data for all day-chunk files spanning [start, start+extent). Returns None if any chunk is missing."""

  if False:
    _locals = locals()
    logger.debug("data._cache_read() called with arguments:")
    for arg in _locals:
      logger.debug(f"  {arg}: {_locals[arg]}")


  import pickle
  from datetime import datetime, timezone, timedelta

  if format not in ['json', 'dataframe']:
    raise ValueError("Invalid format. Must be 'json' or 'dataframe'.")

  cache_dir = _cache_path(cache_dir, stationid, cadence, delta=delta, baseline=baseline)

  # Determine which UTC dates are needed
  start_str = str(start).rstrip('Z').replace(' ', 'T')
  for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
    try:
      start_dt = datetime.strptime(start_str, fmt).replace(tzinfo=timezone.utc)
      break
    except ValueError:
      continue
  else:
    return None

  seconds_per_day = 60 * 60 * 24
  n_days = max(1, (extent + seconds_per_day - 1) // seconds_per_day) if extent else 1
  dates = [start_dt.date() + timedelta(days=i) for i in range(n_days)]

  chunks = []
  for date in dates:
    cache_file = cache_dir / f'{date}.{format}.pkl'
    if not cache_file.exists():
      logger.debug(f"Cache miss: {cache_file}")
      return None
    logger.debug(f"Cache hit: {cache_file}")
    with cache_file.open('rb') as f:
      chunks.append(pickle.load(f))

  if format == 'dataframe':
    import pandas
    return pandas.concat(chunks, ignore_index=True)

  # json: list of dicts
  result = []
  for chunk in chunks:
    result.extend(chunk)
  return result


def _cache_write(data_json, cache_dir, stationid, cadence, delta=None, baseline=None):
  """Write list of dicts and a dataframe to the cache in one-day chunks. No-op if data_json is falsy."""
  import pickle
  from datetime import datetime, timezone

  if not data_json:
    return

  # Group records by date (UTC) derived from tval
  days = {}
  for row in data_json:
    date_str = datetime.fromtimestamp(row['tval'], tz=timezone.utc).strftime('%Y-%m-%d')
    days.setdefault(date_str, []).append(row)

  cache_dir = _cache_path(cache_dir, stationid, cadence, delta=delta, baseline=baseline)
  cache_dir.mkdir(parents=True, exist_ok=True)

  for date_str, rows in days.items():
    # Write JSON chunk
    rows = _reformat(rows, format='json')
    cache_json_file = cache_dir / f'{date_str}.json.pkl'
    with cache_json_file.open('wb') as f:
      pickle.dump(rows, f)
    logger.debug(f"Wrote: {cache_json_file}")

    # Write dataframe chunk
    try:
      df = _reformat(rows, format='dataframe')
      cache_df_file = cache_dir / f'{date_str}.dataframe.pkl'
      with cache_df_file.open('wb') as f:
        pickle.dump(df, f)
      logger.debug(f"Wrote: {cache_df_file}")
    except Exception as error:
      logger.debug(f"Failed to write dataframe cache for {date_str}: {error}")


if __name__ == '__main__':
  from .cli import main_data
  main_data()
