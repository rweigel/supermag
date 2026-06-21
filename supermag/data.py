from .util import logger

from .config import config
CONFIG = config()

# If true, show response data in debug logs.
DEBUG_RESPONSE = True

CACHE_RAW_JSON = True

def indices(userid,
            start,
            extent,
            parameters=None,
            format='json',
            cache=True,
            use_cache=True,
            cache_dir=CONFIG['common']['output_dir'],
            cafile=None):

  return data(userid,
              'indices',
              start,
              extent,
              parameters=parameters,
              format=format,
              cache=cache,
              use_cache=use_cache,
              cache_dir=cache_dir,
              cafile=cafile)


def data(userid,
          stationid,
          start,
          extent,
          baseline='none',
          delta='none',
          format='json',
          parameters=None,
          cadence='PT1M',
          cache=True,      # If True, cache data
          use_cache=True,  # If False, request data and cache if cache=True.
          cache_dir=CONFIG['common']['output_dir'],
          cafile=None):

  _locals = locals()
  logger.debug("data() called with arguments:")
  for arg in _locals:
    logger.debug(f"  {arg}: {_locals[arg]}")

  # Check inputs
  from .util import check_userid
  check_userid(userid)

  formats = CONFIG['data']['formats']
  if format not in formats:
    raise ValueError(f"Invalid format: {format}. Must be one of: {', '.join(formats)}.")

  cadences = CONFIG['data']['cadences']
  if cadence not in cadences:
    raise ValueError(f"Invalid cadence value: {cadence}. Must be one of: {', '.join(cadences)}.")

  if stationid == 'indices':
    if baseline != 'none':
      raise ValueError(f"Invalid baseline value for indices: {baseline}. Must be 'none'.")
    if delta  != 'none':
      raise ValueError(f"Invalid delta value for indices: {delta}. Must be 'none'.")
  else:
    baselines = CONFIG['data']['mag']['baselines']
    if baseline not in baselines:
      raise ValueError(f"Invalid baseline value: {baseline}. Must be one of: {", ".join(baselines)}.")

    deltas = CONFIG['data']['mag']['deltas']
    if delta not in deltas:
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
      raise ValueError(f"Invalid delta value: {delta}. Must be one of: {", ".join(deltas)}.")

  _check_parameters(stationid, parameters, format)

  if isinstance(extent, str):
    extent = _stop_to_extent(start, extent)

  # Preserve the originally requested extent for sub-setting
  extent_requested = extent

  if use_cache:
    # Try to load from cache
    result, error = _cache_get(cache_dir,
                              stationid,
                              format,
                              start,
                              extent,
                              extent_requested,
                              cadence,
                              parameters=parameters,
                              delta=delta,
                              baseline=baseline)
    if result is not None or error is not None:
      return result, error


  if cache:
    # When caching, always fetch from the start of the day and request an
    #  integer number of days.
    start_original = start
    extent_originial = extent
    start = start[0:10] + "T00:00Z"
    seconds_per_day = 60 * 60 * 24
    extent = ((extent + seconds_per_day - 1) // seconds_per_day) * seconds_per_day
    logger.debug("cache=True =>")
    logger.debug(f"  Adjusting start from {start_original} to {start}")
    logger.debug(f"  Adjusting extent from {extent_originial} to {extent}")


  common_request_params = f"start={start}&extent={extent}&logon={userid}"
  # Always request all parameters; will subset as needed.
  if stationid == 'indices':
    url = CONFIG['data']['base_url']['indices']
    url += f"&{common_request_params}&indices=all&swi=all&imf=all"
  else:
    options = []
    options.append(f"delta={delta}")
    options.append(f"baseline={baseline}")
    options = '&'.join(options)
    request_parameters = CONFIG['data']['mag']['extra_request_parameters']
    if len(request_parameters) > 0:
      options += '&' + '&'.join(request_parameters)

    url = CONFIG['data']['base_url']['data']
    url += f"&{common_request_params}&station={stationid}&{options}"


  data_json, error = _get_and_parse(url, stationid, format='json', cafile=cafile)
  if error is not None:
    return None, error


  if cache:
    write_error = False
    try:
      _cache_write(data_json,
                   cache_dir,
                   stationid,
                   cadence,
                   delta=delta,
                   baseline=baseline)
    except Exception as e:
      write_error = True
      logger.error(f"Failed to write cache for {stationid}: {e}")
    if not write_error:
      logger.debug(f"Cache write successful for {stationid}")

    data_json = _subset_time(data_json, start, extent_requested)

  data_json = _subset_parameters(data_json, parameters, format)

  if format == 'json':
    return data_json, None

  return _reformat(data_json, format=format), None


def _get_and_parse(url, stationid, format='json', cafile=None):
  from .util import get
  try:
    data_json, error = get(url,
                           cafile=cafile,
                           format='json',
                           retry=CONFIG['data']['retry'],
                           timeout=CONFIG['data']['timeout'])
    if error is not None:
      logger.debug(error)
      return None, {'url': url, 'error': error}

    if DEBUG_RESPONSE:
      logger.debug("Raw response keys in first row:")
      logger.debug(f"  {list(data_json[0].keys()) if data_json else 'no data'}")

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
  from .util import parse_timestamp
  if isinstance(extent, str):
    start_ts = parse_timestamp(start)
    stop_ts = parse_timestamp(extent)
    if stop_ts <= start_ts:
      raise ValueError(f"Stop time must be after start time. Got start={start} ({start_ts}), stop={extent} ({stop_ts})")
    extent = int(stop_ts - start_ts)
  return extent


def _check_parameters(dataset, parameters, format):

  import json
  import pathlib

  if parameters is None:
    return None

  if not isinstance(parameters, (list, tuple, set)):
    raise ValueError(f"Invalid parameters value: {parameters}. Must be a None, list, tuple, or set.")

  if format == 'json':
    if dataset == 'indices':
      pass
    else:
      known_parameters = CONFIG['data']['mag']['known_response_parameters']
      if not all(param in known_parameters for param in parameters):
        unknown = [param for param in parameters if param not in known_parameters]
        raise ValueError(f"Unknown parameter(s) requested: {unknown}. Allowed: {known_parameters}")
    return

  if dataset == 'indices':
    file = 'catalog.indices.json'
  else:
    file = 'catalog.mag.json'

  _catalog_file = pathlib.Path(__file__).parent / file
  logger.debug(f"Reading catalog file: {_catalog_file}")
  with open(_catalog_file) as f:
    dataset = json.load(f)


def _reformat(data_json, format='json'):
  """Convert json response data to the requested format.

  `data_json` is the response from _parse_response().
  For list input, nested dicts are flattened (e.g. N.nez -> N_nez).
  """
  from datetime import datetime, timezone

  if format not in ['json', 'list', 'dataframe', 'csv', 'csv-hapi', 'csv-hapi-noheader']:
    raise ValueError("Invalid format. Must be one of: 'json', 'list', 'dataframe', 'csv', 'csv-hapi', 'csv-hapi-noheader'.")

  if format == 'json':
    result = []
    for row in data_json:
      iso = datetime.fromtimestamp(row['tval'], tz=timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
      result.append({'tval_iso': iso, **row})
    return result

  if format == 'hapi-binary':
    pass

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

  import pandas
  df = pandas.DataFrame(data_rows, columns=header)
  if format in ['csv', 'csv-hapi', 'csv-hapi-noheader']:
    if format in ['csv-hapi', 'csv-hapi-noheader'] and 'tval' in df.columns:
      df = df.drop(columns=['tval'])
    if format in ['csv-hapi', 'csv-hapi-noheader'] and 'tval_iso' in df.columns:
      df = df.rename(columns={'tval_iso': 'Time'})

    for col in df.columns:
      # Reprocess columns and convert columns with list values to comma-separated strings.
      # E.g., ...,"[66.365166, 66.365166, ...]", "['ABK', 'ABC', ...]", ...
      # =>        "66.365166, 66.365166, ...", "'ABK', 'ABC', ...", ...
      if df[col].apply(lambda x: isinstance(x, list)).any():
        df[col] = df[col].apply(lambda x: ','.join(str(v) for v in x) if isinstance(x, list) else x)
    include_header = format in ['csv', 'csv-hapi']
    return df.to_csv(index=False, header=include_header).rstrip()

  # dataframe: always prepend tval_datetime
  if format == 'dataframe':
    df = df.copy()
    df.insert(0, 'tval_datetime', pandas.to_datetime(df['tval'], unit='s', utc=True))
    return df


def _subset_time(data, start, extent):
  """Subset data to [start, start+extent).

  Accepts either a list of dicts (JSON records) or a pandas DataFrame.
  """
  from .util import parse_timestamp

  try:
    import pandas
    is_df = isinstance(data, pandas.DataFrame)
  except ImportError:
    is_df = False

  if is_df:
    if data.empty:
      logger.debug("  No data to subset because dataframe is empty.")
      return data
  else:
    if not data:
      logger.debug("  No data to subset because data = [].")
      return data

  start_ts = parse_timestamp(start)
  stop_ts = start_ts + extent if extent is not None else None

  if is_df:
    orig_first = data['tval_iso'].iloc[0]
    orig_last = data['tval_iso'].iloc[-1]
    if not data.empty and stop_ts is not None:
      data = data[(data['tval'] >= start_ts) & (data['tval'] < stop_ts)]
    logger.debug(f"  Original first:  {orig_first}")
    logger.debug(f"  Subsetted first: {data['tval_iso'].iloc[0]}")
    logger.debug(f"  Original last:   {orig_last}")
    logger.debug(f"  Subsetted last:  {data['tval_iso'].iloc[-1]}")
    return data

  logger.debug(f"Subsetting data to start={start}, extent={extent}")
  logger.debug(f"  Original start: {data[0]['tval_iso']}")
  logger.debug(f"  Original end:   {data[-1]['tval_iso']}")

  data_subsetted = [row for row in data if start_ts <= row['tval'] < stop_ts]
  logger.debug(f"  Subsetted start {data_subsetted[0]['tval_iso']}")
  logger.debug(f"  Subsetted end   {data_subsetted[-1]['tval_iso']}")

  return data_subsetted


def _subset_parameters(data_json, parameters, format):
  if parameters is None:
    return data_json

  filtered = []
  parameters = ['tval', 'tval_iso'] + parameters
  for row in data_json:
    row_filtered = {}
    for key, value in row.items():
      if key in parameters:
        row_filtered[key] = value
    filtered.append(row_filtered)

  return filtered


def _cache_get(cache_dir, stationid, format, start, extent, extent_requested, cadence, parameters=None, delta=None, baseline=None):

  if False:
    _locals = locals()
    logger.debug("data._cache_get() called with arguments:")
    for arg in _locals:
      logger.debug(f"  {arg}: {_locals[arg]}")

  if format not in ['json', 'dataframe', 'csv', 'csv-hapi', 'csv-hapi-noheader', 'list']:
    raise ValueError("Invalid format. Must be one of: 'json', 'dataframe', 'csv', 'csv-hapi', 'csv-hapi-noheader', 'list'.")

  # csv/list and parameter-subset dataframe are generated from JSON records.
  file_ext = 'dataframe' if format == 'dataframe' and parameters is None else 'json'
  cached = _cache_read(cache_dir,
                       stationid,
                       start,
                       extent,
                       format=file_ext,
                       cadence=cadence,
                       delta=delta,
                       baseline=baseline)
  if cached is None:
    return None, None

  data = _subset_time(cached, start, extent_requested)

  if file_ext == 'json':
    data = _subset_parameters(data, parameters, format)

  if format == 'dataframe' and file_ext == 'dataframe':
    return data, None

  if format == 'dataframe':
    return _reformat(data, format='dataframe'), None

  return _reformat(data, format=format), None


def _cache_path(cache_dir, stationid, cadence, parameters=None, delta=None, baseline=None):

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

  cache_dir = cache_dir / 'cache'

  if stationid == 'indices':
    sub_dir = pathlib.Path(f'indices/{cadence}')
    return cache_dir / sub_dir
  else:
    sub_dir = pathlib.Path(f"mag/{cadence}/{stationid}")

  delta_str = str(delta) if delta is not None else 'none'
  baseline_str = str(baseline) if baseline is not None else 'none'
  cache_path = cache_dir / sub_dir / f"baseline-{baseline_str}" / f"delta-{delta_str}"
  return cache_path


def _cache_read(cache_dir, stationid, start, extent, format='json', cadence='PT1M', parameters=None, delta=None, baseline=None):
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

  cache_dir = _cache_path(cache_dir, stationid, cadence, parameters=parameters, delta=delta, baseline=baseline)

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


def _cache_write(data_json, cache_dir, stationid, cadence, parameters=None, delta=None, baseline=None):
  """Write list of dicts and a dataframe to the cache in one-day chunks. No-op if data_json is falsy."""
  import os
  import pickle
  from datetime import datetime, timezone

  def _atomic_pickle_write(path, obj):
    # TODO: Write gzip-compressed pickle files (reduces file size by factor of 3)
    import secrets

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_ext = f".{secrets.token_hex(3)}.tmp"
    tmp_path = path.with_suffix(path.suffix + tmp_ext)
    try:
      with tmp_path.open('wb') as f:
        pickle.dump(obj, f)
      os.replace(tmp_path, path)
    except Exception:
      try:
        tmp_path.unlink()
      except OSError:
        pass
      raise

  if not data_json:
    return

  # Group records by date (UTC) derived from tval
  days = {}
  for row in data_json:
    date_str = datetime.fromtimestamp(row['tval'], tz=timezone.utc).strftime('%Y-%m-%d')
    days.setdefault(date_str, []).append(row)

  cache_dir = _cache_path(cache_dir,
                          stationid,
                          cadence,
                          parameters=parameters,
                          delta=delta,
                          baseline=baseline)

  cache_dir.mkdir(parents=True, exist_ok=True)

  for date_str, rows in days.items():

    logger.debug("Writing cache for data with ")
    logger.debug(f"  first timestamp: {rows[0]['tval_iso']}")
    logger.debug(f"  last timestamp:  {rows[-1]['tval_iso']}")
    logger.debug(f"  number of records: {len(rows)}")

    # Write JSON chunk
    # TODO: Don't write redundant JSON. Write only dataframe and then convert 
    # to raw JSON format if needed.
    rows = _reformat(rows, format='json')
    cache_json_file = cache_dir / f'{date_str}.json.pkl'
    _atomic_pickle_write(cache_json_file, rows)
    logger.debug(f"Wrote: {cache_json_file}")

    # Write dataframe chunk
    try:
      df = _reformat(rows, format='dataframe')
      cache_df_file = cache_dir / f'{date_str}.dataframe.pkl'
      _atomic_pickle_write(cache_df_file, df)
      logger.debug(f"Wrote: {cache_df_file}")
    except Exception as error:
      logger.debug(f"Failed to write dataframe cache for {date_str}: {error}")


if __name__ == '__main__':
  from .cli import main_data
  main_data()
