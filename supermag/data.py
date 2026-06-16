
import logging

try:
  from .util import configure_logging
  logger = configure_logging(__name__, level=logging.INFO)
except:
  # If util cannot be imported (if this script copied locally), set up a 
  # basic logger to avoid NameError.
  logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')
  logger = logging.getLogger(__name__)

# If true, show response data in debug logs.
debug_response = False

# We always request all extra parameters.
# Note: mlt => response includes mlt, and mcolat. All others are single.
EXTRA_PARAMETERS = ['mlt', 'decl', 'sza', 'glat', 'glon']


def indices(userid, start, extent, format='json', cache=True, ignore_cache=False, cache_dir=None):

  _check_userid(userid)

  if isinstance(extent, str):
    extent = _stop_to_extent(start, extent)

  url = "https://supermag.jhuapl.edu/services/indices.php?python&nohead"
  url += f"&start={start}&extent={extent}&logon={userid}"
  url += "&indices=all&swi=all&imf=all"

  data_json, error = _get_and_parse(url, 'indices', format='json')
  if error is not None:
    return None, {'url': url, 'error': str(error)}

  try:
    result = _reformat(data_json, format=format)
  except Exception as error:
    return None, {'url': url, 'error': str(error)}
  return result, None


def data(userid, stationid, start, extent,
          baseline='yearly',
          delta='default',
          format='json',
          cache=True,
          ignore_cache=False,
          cache_dir=None):

  _locals = locals()
  logger.debug("data() called with arguments:")
  for arg in _locals:
    logger.debug(f"  {arg}: {_locals[arg]}")

  import pathlib

  if format not in ['json', 'list', 'dataframe', 'csv']:
    raise ValueError("Invalid format. Must be one of: 'json', 'list', 'dataframe', 'csv'.")

  if baseline not in ['yearly', 'all', 'none']:
    raise ValueError("Invalid baseline value. Must be one of: 'yearly', 'default', 'none'.")

  if delta not in ['start', 'none']:
    raise ValueError("Invalid delta value. Must be one of: 'start', 'none'.")

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

  if cache_dir is None:
    cache_dir = pathlib.Path(__file__).resolve().parent.parent / 'data'
  else:
    cache_dir = pathlib.Path(cache_dir)

  if isinstance(extent, str):
    extent = _stop_to_extent(start, extent)

  # Preserve the originally requested extent for sub-setting
  requested_extent = extent

  # When caching, always fetch all extra parameters and a full day
  if cache:
    seconds_per_day = 60 * 60 * 24
    extent = ((extent + seconds_per_day - 1) // seconds_per_day) * seconds_per_day  # round up to full day(s)

  # Try to load from cache
  if cache and not ignore_cache:
    result, error = _cache_get(stationid, delta, start, extent, cache_dir, format, requested_extent)
    if result is not None or error is not None:
      return result, error


  # Call the SuperMAG API to get the data
  options = []
  options.append(f"delta={delta}")
  options.append(f"baseline={baseline}")
  options = '&'.join(options)
  options += '&' + '&'.join(EXTRA_PARAMETERS)

  url = "https://supermag.jhuapl.edu/services/data-api.php?python&nohead&"
  url += f"start={start}&extent={extent}&logon={userid}&station={stationid.upper()}&{options}"

  data_json, error = _get_and_parse(url, stationid, format='json')
  if error is not None:
    return None, {'url': url, 'error': str(error)}

   # Cache the full response before sub-setting, so we have the full data available in cache for future requests.
  if cache:
    _cache_write(stationid, delta, start, data_json, cache_dir)
    data_json = _subset(data_json, start, requested_extent)

  if format == 'json':
    return data_json, None

  try:
    result = _reformat(data_json, format=format)
  except Exception as error:
    emsg = f"Failed to reformat data for station {stationid}: {error}"
    logger.debug(emsg)
    return None, {'url': url, 'error': emsg}
  return result, None


def _get(url):
  import urllib3
  import importlib

  certspec = importlib.util.find_spec("certifi")
  cafile = None
  if certspec is not None:
    import certifi

  logger.debug("Getting URL: %s", url)
  try:
    logger.debug("  Trying certifi.where().")
    cafile = certifi.where()
  except Exception:
    logger.debug("  certifi.where() raised an exception.")
    cafile = None

  pool_kwargs = {}
  if cafile is not None:
    logger.debug(f"  Using CA certificates from certifi: {cafile}")
    pool_kwargs['ca_certs'] = cafile

  try:
    logger.debug("  Getting response using urllib3.PoolManager().request('GET', url)")
    http = urllib3.PoolManager(**pool_kwargs)
    response = http.request('GET', url)
  except Exception as error:
    logger.debug(f"  Failed: {error}")
    raise

  if response.status >= 400:
    response.release_conn()
    raise urllib3.exceptions.HTTPError(f"HTTP {response.status} for {url}")

  logger.debug("Got URL: %s", url)

  return response


def _get_and_parse(url, stationid, format='json'):
  try:
    response = _get(url)
    data_json, error = _parse_response(response, format='json')
    if error is not None:
      logger.debug(f"Failed to parse response for {stationid}: {error}")
      return None, {'url': url, 'error': str(error)}
    try:
      data_json = _reformat(data_json)
    except Exception as error:
      logger.debug(f"Failed to reformat data for {stationid}: {error}")
      return None, {'url': url, 'error': str(error)}
  except Exception as error:
    logger.debug("data() failed for %s: %s", stationid, error)
    return None, {'url': url, 'error': str(error)}

  return data_json, None


def _check_userid(userid):
  if not userid:
    raise ValueError("SuperMAG user id is required")

  if userid == 'USERID':
    raise ValueError("Provide a valid SuperMAG user id instead of the placeholder 'USERID'")


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


def _parse_response(response, format=None):
  import re
  import json

  if format not in [None, 'string', 'json']:
    raise ValueError("Invalid format. Must be one of: None, 'string', 'json'.")

  try:
    longstring = response.data.decode('utf-8')
    if debug_response:
      logger.debug(f"Raw response string: {longstring}")
    # JSON does not allow NaN
    longstring = re.sub(r'\b(?:NaN|nan|Infinity|inf|-Infinity|-inf)\b', 'null', longstring, flags=re.IGNORECASE)
    if debug_response:
      logger.debug(f"Raw response string after re.sub(): {longstring}")
  except Exception as error:
    return None, f"Error: '{error}' for response data: '{longstring}'"
  finally:
    response.release_conn()

  if format is None or format == 'string':
    return longstring

  if len(longstring) == 0:
    return {}, None

  try:
    data_json = json.loads(longstring)
    if debug_response:
      logger.debug(f"Parsed JSON data: {data_json}")
  except Exception as error:
    return None, f"Error: '{error}' for response data: '{longstring}'"

  return data_json, None


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
  if debug_response:
    logger.debug(f"Header: {header}")

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
  if debug_response:
    logger.debug(f"Data: {data_rows}")

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


def _cache_get(stationid, delta, start, extent, cache_dir, format, requested_extent):

  if format not in ['json', 'dataframe']:
    raise ValueError("Invalid format. Must be 'json' or 'dataframe'.")

  file_ext = 'json' if format == 'json' else 'dataframe'
  cached = _cache_read(stationid, delta, start, extent, cache_dir, format=file_ext)
  if cached is None:
    return None, None

  data = _subset(cached, start, requested_extent)

  try:
    return _reformat(data, format=format), None
  except Exception as error:
    return None, {'url': None, 'error': str(error)}


def _cache_read(stationid, delta, start, extent, cache_dir, format='json'):
  """Return cached data for all day-chunk files spanning [start, start+extent). Returns None if any chunk is missing."""
  import pickle
  from datetime import datetime, timezone, timedelta

  if format not in ['json', 'dataframe']:
    raise ValueError("Invalid format. Must be 'json' or 'dataframe'.")

  delta_str = str(delta) if delta is not None else 'none'
  base_dir = cache_dir / stationid.upper() / delta_str

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
    cache_file = base_dir / f'{date}.{format}.pkl'
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


def _cache_write(stationid, delta, start, data_json, cache_dir):
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

  delta_str = str(delta) if delta is not None else 'none'
  base_dir = cache_dir / stationid.upper() / delta_str
  base_dir.mkdir(parents=True, exist_ok=True)

  for date_str, rows in days.items():
    # Write JSON chunk
    rows = _reformat(rows, format='json')
    cache_json_file = base_dir / f'{date_str}.json.pkl'
    with cache_json_file.open('wb') as f:
      pickle.dump(rows, f)
    logger.debug(f"Wrote: {cache_json_file}")

    # Write dataframe chunk (no extra timestamp columns — plain tval)
    try:
      df = _reformat(rows, format='dataframe')
      cache_df_file = base_dir / f'{date_str}.dataframe.pkl'
      with cache_df_file.open('wb') as f:
        pickle.dump(df, f)
      logger.debug(f"Wrote: {cache_df_file}")
    except Exception as error:
      logger.debug(f"Failed to write dataframe cache for {date_str}: {error}")


def main():
  # Called when running `python -m supermag.data` or supermag-data from the command line.
  # Parses command-line arguments, calls data(), and writes output to a file.
  import pathlib
  from .util import set_logging_level
  from .cli import parse_args

  args = parse_args()

  if args.debug:
    set_logging_level(logging.DEBUG, [__name__])

  logger.debug("Parsed command-line arguments:")
  for arg in vars(args):
    logger.debug(f"  {arg}: {getattr(args, arg)}")

  kwargs = {
    'baseline': args.baseline,
    'delta': args.delta,
    'format': args.format,
    'cache': args.cache,
    'ignore_cache': args.ignore_cache,
    'cache_dir': args.cache_dir,
  }
  result, error = data(args.userid, args.station, args.start, args.extent, **kwargs)

  if error is not None:
    logger.error(f"Error: {error}")
  else:
    ext = args.format
    ext2 = ""
    if args.format == 'dataframe' or args.format == 'list':
      ext2 = '.pkl'
    if args.output_file is not None:
      output_file = args.output_file
    else:
      baseline_str = args.baseline if args.baseline is not None else 'none'
      delta_str = args.delta if args.delta is not None else 'none'
      fname = f"supermag-{args.station}-{args.start}-{args.stop}-baseline_{baseline_str}-delta_{delta_str}.{ext}{ext2}"
      output_file = pathlib.Path(args.output_dir) / fname

    output_file.parent.mkdir(parents=True, exist_ok=True)

    if args.format == 'json':
      import json
      output_file.write_text(json.dumps(result, indent=2) + '\n')
    elif args.format == 'csv':
      output_file.write_text(result + '\n')
    elif args.format == 'dataframe':
      result.to_pickle(output_file)
    elif args.format == 'list':
      import pickle
      with output_file.open('wb') as f:
        pickle.dump(result, f)

    logger.info(f"Wrote {output_file}")


if __name__ == '__main__':
  main()
