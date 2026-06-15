
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

# Note: mlt => response includes mlt, and mcolat. All others are single.
EXTRA_PARAMETERS = ['mlt', 'decl', 'sza', 'glat', 'glon']


def data(userid, stationid, start, extent,
          baseline='yearly',
          delta='default',
          extra_parameters=EXTRA_PARAMETERS,
          format='json',
          add_timestamp=False,
          cache=True,
          ignore_cache=False,
          cache_dir=None):

  _locals = locals()
  logger.debug("data() called with arguments:")
  for arg in _locals:
    logger.debug(f"  {arg}: {_locals[arg]}")

  import pathlib

  if not userid:
    raise ValueError("SuperMAG user id is required")

  if userid == 'USERID':
    raise ValueError("Provide a valid SuperMAG user id instead of the placeholder 'USERID'")

  if cache_dir is None:
    cache_dir = pathlib.Path(__file__).resolve().parent.parent / 'data'
  else:
    cache_dir = pathlib.Path(cache_dir)

  if isinstance(extent, str):
    # compute extent using start and this stop time
    start_ts = _parse_timestamp(start)
    stop_ts = _parse_timestamp(extent)
    if stop_ts <= start_ts:
      raise ValueError(f"Stop time must be after start time. Got start={start} ({start_ts}), stop={extent} ({stop_ts})")
    extent = stop_ts - start_ts

  # Preserve the originally requested extent for sub-setting
  requested_extent = extent
  requested_extra_parameters = extra_parameters.copy() if extra_parameters else None

  # When caching, always fetch all extra parameters and a full day
  if cache:
    extra_parameters = EXTRA_PARAMETERS
    seconds_per_day = 60 * 60 * 24
    extent = ((extent + seconds_per_day - 1) // seconds_per_day) * seconds_per_day  # round up to full day(s)

  # Try to load from cache
  if cache and not ignore_cache:
    result, error = _cache_get(stationid, delta, start, extent, cache_dir,
                               format, add_timestamp, requested_extent, requested_extra_parameters)
    if result is not None or error is not None:
      return result, error


  # Call the SuperMAG API to get the data
  flag_list = []
  if delta is not None:
    if delta not in ['start', 'default', None]:
      raise ValueError("Invalid delta value. Must be one of: 'start', 'default', None")
    flag_list.append(f"delta={delta}")

  baseline = 'default'
  if baseline is not None:
    if baseline not in ['yearly', 'default', 'none', None]:
      raise ValueError("Invalid baseline value. Must be one of: 'yearly', 'none', 'default'")
    flag_list.append(f"baseline={baseline}")

  flagstring = '&'.join(flag_list)

  if extra_parameters is not None and not isinstance(extra_parameters, (list, tuple)):
    raise ValueError(f"extra_parameters must be a list, tuple, or None. Got: {extra_parameters}")

  if extra_parameters is not None:
    for parameter in extra_parameters:
      if parameter not in EXTRA_PARAMETERS:
        raise ValueError(f"Invalid extra parameter: '{parameter}'. Allowed parameters are: {EXTRA_PARAMETERS}")
    flagstring += '&' + '&'.join(extra_parameters)

  url = "https://supermag.jhuapl.edu/services/data-api.php?python&nohead&"
  url += f"start={start}&extent={extent}&logon={userid}&station={stationid.upper()}&{flagstring}"

  try:
    response = _get(url)
    data_json, error = _parse_response(response, format='json')
    if error is not None:
      logger.debug(f"Failed to parse response for station {stationid}: {error}")
      return None, {'url': url, 'error': str(error)}
  except Exception as error:
    logger.debug("data() failed for station %s: %s", stationid, error)
    return None, {'url': url, 'error': str(error)}

  if cache:
    _cache_write(stationid, delta, start, data_json, cache_dir)
    data_json = _subset(data_json, start, requested_extent, requested_extra_parameters)

  try:
    result = _reformat(data_json, format=format, add_timestamp=add_timestamp)
  except Exception as error:
    emsg = f"Failed to _reformat data for station {stationid}: {error}"
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

  if format is None:
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


def _reformat(data, format='dataframe', add_timestamp=False):
  """Convert data to the requested format.

  `data` may be either a list of dicts (raw JSON records) or a pandas DataFrame.
  For list input, nested dicts are flattened (e.g. N.nez -> N_nez).
  """
  import pandas
  from datetime import datetime, timezone

  if format == 'json' and isinstance(data, list):
    if add_timestamp:
      result = []
      for row in data:
        iso = datetime.fromtimestamp(row['tval'], tz=timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
        result.append({'tval_iso': iso, **row})
    return data

  if format not in ['list', 'dataframe', 'csv']:
    raise ValueError("Invalid format. Must be 'list', 'dataframe', or 'csv'.")

  # --- Build a flat DataFrame if input is list-of-dicts ---
  if not isinstance(data, pandas.DataFrame):
    data_json = data
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
  else:
    df = data

  # --- DataFrame / CSV output ---
  if add_timestamp and 'tval_iso' not in df.columns:
    df = df.copy()
    tval_pos = df.columns.get_loc('tval') if 'tval' in df.columns else 0
    df.insert(tval_pos, 'tval_iso',
      df['tval'].apply(lambda x: datetime.fromtimestamp(x, tz=timezone.utc).strftime('%Y-%m-%dT%H:%MZ')))

  if format == 'csv':
    return df.to_csv(index=False).rstrip()

  # dataframe: always prepend tval_datetime
  if 'tval_datetime' not in df.columns:
    df = df.copy()
    df.insert(0, 'tval_datetime', pandas.to_datetime(df['tval'], unit='s', utc=True))

  return df


def _subset(data, start, extent, extra_parameters):
  """Subset data to [start, start+extent) and keep only requested extra_parameters.

  Accepts either a list of dicts (JSON records) or a pandas DataFrame.
  """


  try:
    import pandas
    is_df = isinstance(data, pandas.DataFrame)
  except ImportError:
    is_df = False

  start_ts = _parse_timestamp(start)
  stop_ts = start_ts + extent if extent is not None else None

  extra_keys = set(EXTRA_PARAMETERS + ['mcolat'])

  if extra_parameters is None or set(extra_parameters) == set(EXTRA_PARAMETERS):
    requested = None  # keep all
  else:
    requested = set(extra_parameters)
    if 'mlt' in requested:
      requested.add('mcolat')

  if is_df:
    if not data.empty and stop_ts is not None:
      data = data[(data['tval'] >= start_ts) & (data['tval'] < stop_ts)]
    if requested is not None:
      non_extra = [c for c in data.columns if c not in extra_keys]
      keep_cols = non_extra + [c for c in data.columns if c in requested]
      data = data[keep_cols]
    return data

  # list-of-dicts path
  if not data or stop_ts is None:
    return data

  if requested is None:
    return [row for row in data if start_ts <= row['tval'] < stop_ts]

  result = []
  for row in data:
    if row['tval'] < start_ts:
      continue
    if row['tval'] >= stop_ts:
      break
    non_extra = set(row.keys()) - extra_keys
    keys_to_keep = non_extra | requested
    result.append({k: v for k, v in row.items() if k in keys_to_keep})
  return result


def _cache_get(stationid, delta, start, extent, cache_dir, format,
               add_timestamp, requested_extent, requested_extra_parameters):

  file_ext = 'json' if format == 'json' else 'dataframe'
  cached = _cache_read(stationid, delta, start, extent, cache_dir, format=file_ext)
  if cached is None:
    return None, None

  data = _subset(cached, start, requested_extent, requested_extra_parameters)

  try:
    return _reformat(data, format=format, add_timestamp=add_timestamp), None
  except Exception as error:
    return None, {'url': None, 'error': str(error)}


def _cache_read(stationid, delta, start, extent, cache_dir, format='json'):
  """Return cached data for all day-chunk files spanning [start, start+extent). Returns None if any chunk is missing."""
  import pickle
  from datetime import datetime, timezone, timedelta

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
  """Write data_json (and a dataframe) to the cache in one-day chunks. No-op if data_json is falsy."""
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
    cache_json_file = base_dir / f'{date_str}.json.pkl'
    with cache_json_file.open('wb') as f:
      pickle.dump(rows, f)
    logger.debug(f"Wrote: {cache_json_file}")

    # Write dataframe chunk (no extra timestamp columns — plain tval)
    try:
      df = _reformat(rows, format='dataframe', add_timestamp=False)
      # Drop tval_datetime so cached df is plain; it will be added on read
      if 'tval_datetime' in df.columns:
        df = df.drop(columns=['tval_datetime'])
      cache_df_file = base_dir / f'{date_str}.dataframe.pkl'
      with cache_df_file.open('wb') as f:
        pickle.dump(df, f)
      logger.debug(f"Wrote: {cache_df_file}")
    except Exception as error:
      logger.debug(f"Failed to write dataframe cache for {date_str}: {error}")


def _parse_args():
  import pathlib
  import argparse

  default_cache_dir = '.'

  # If these defaults changed, will need to update tests.
  default_station = 'ABK'
  default_start = '2001-01-01T00:00Z'
  default_stop  = '2001-01-01T00:01Z'

  parser = argparse.ArgumentParser(
    description='Fetch SuperMAG station data via data().',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=(
      'Examples:\n'
      '  supermag-data --userid USERID\n'
      '  supermag-data --userid USERID --station ABK\n'
      '  supermag-data --userid USERID --station ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z\n'
    ),
  )
  parser.add_argument(
    '--station',
    default=default_station,
    help=f'SuperMAG station ID. Default: {default_station}.',
  )
  parser.add_argument(
    '--userid',
    required=True,
    help='SuperMAG user ID (required).',
  )
  parser.add_argument(
    '--start',
    default=default_start,
    help=f'Start time (YYYY-MM-DDTHH:MMZ or full ISO). Default: {default_start}.',
  )
  parser.add_argument(
    '--stop',
    default=default_stop,
    help=f'Stop time (YYYY-MM-DDTHH:MMZ or full ISO). Default: {default_stop}.',
  )
  parser.add_argument(
    '--delta',
    default='default',
    choices=['start', 'default', 'none'],
    help='Delta parameter for the SuperMAG API. Default: default.',
  )
  parser.add_argument(
    '--baseline',
    default='yearly',
    choices=['yearly', 'default', 'none'],
    help='Baseline parameter for the SuperMAG API. Default: yearly.',
  )
  parser.add_argument(
    '--format',
    default='json',
    choices=['json', 'csv', 'list', 'dataframe'],
    help='Output format. Default: json.',
  )
  parser.add_argument(
    '--no-cache',
    action='store_true',
    help='Disable caching entirely.'
  )
  parser.add_argument(
    '--ignore-cache',
    action='store_true',
    help='Re-fetch even if a cache file exists.'
  )
  parser.add_argument(
    '--cache-dir',
    default=default_cache_dir,
    type=pathlib.Path,
    help=f'Base directory for cache storage. Default: {default_cache_dir}.'
  )
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.'
  )
  parser.add_argument(
    '--add-timestamp',
    action='store_true',
    help='Add tval_iso (ISO 8601) as the first column in dataframe and csv output.'
  )
  parser.add_argument(
    '--output-dir',
    default=".",
    help='Path to write output file. Ignored if --output-file is given. Default: current directory.'
  )
  parser.add_argument(
    '--output-file',
    default=None,
    type=pathlib.Path,
    help='Path to write output. If not given, writes to supermag-{station}-{start}-{stop}-{baseline}-{delta}.{format}'
  )
  parser.add_argument(
    '--extra-parameters',
    default=EXTRA_PARAMETERS,
    help=f'Comma-separated list of extra parameters to include in output. Default: {",".join(EXTRA_PARAMETERS)}.'
  )

  args = parser.parse_args()

  if args.extra_parameters:
    if args.extra_parameters == 'none':
      args.extra_parameters = []
    else:
      args.extra_parameters = [param.strip() for param in args.extra_parameters]

  # Normalise times to HH:MMZ
  args.start = args.start[:16] + 'Z'
  args.stop  = args.stop[:16]  + 'Z'

  # Compute extent in seconds from start/stop
  from datetime import datetime, timezone
  fmt = '%Y-%m-%dT%H:%MZ'
  start_dt = datetime.strptime(args.start, fmt).replace(tzinfo=timezone.utc)
  stop_dt  = datetime.strptime(args.stop,  fmt).replace(tzinfo=timezone.utc)
  if stop_dt <= start_dt:
    raise ValueError('--stop must be after --start')
  args.extent = int((stop_dt - start_dt).total_seconds())

  args.cache = not args.no_cache

  return args


def main():
  # Called when running `python -m supermag.data` or supermag-data from the command line.
  # Parses command-line arguments, calls data(), and writes output to a file.
  import pathlib
  from .util import set_logging_level

  args = _parse_args()

  if args.debug:
    set_logging_level(logging.DEBUG, [__name__])

  logger.debug("Parsed command-line arguments:")
  for arg in vars(args):
    logger.debug(f"  {arg}: {getattr(args, arg)}")

  kwargs = {
    'baseline': args.baseline,
    'delta': args.delta,
    'format': args.format,
    'add_timestamp': args.add_timestamp,
    'cache': args.cache,
    'ignore_cache': args.ignore_cache,
    'cache_dir': args.cache_dir,
    'extra_parameters': args.extra_parameters
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
      fname = f"supermag-{args.station}-{args.start}-{args.stop}-{args.baseline}-{args.delta}.{ext}{ext2}"
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
