
import pathlib
import logging

from .util import configure_logging

logger = configure_logging(__name__, level=logging.INFO)

debug_response = False # If true, show response data in debug logs.


def data(userid, stationid, start, extent,
            baseline='yearly',
            delta='default',
            extra_parameters=None,
            format='json',
            cache=True,
            ignore_cache=False,
            output_dir=None):

  logger.debug(f"data() called with stationid={stationid}, start={start}, extent={extent}, "
               f"baseline={baseline}, delta={delta}, extra_parameters={extra_parameters}, "
               f"format={format}, cache={cache}, ignore_cache={ignore_cache}, output_dir={output_dir}")

  if output_dir is None:
    output_dir = pathlib.Path(__file__).resolve().parent.parent / 'data'
  else:
    output_dir = pathlib.Path(output_dir)

  # Preserve the originally requested extent for sub-setting
  requested_extent = extent

  # When caching, always fetch all extra parameters and a full day
  if cache:
    extra_parameters = ['mlt', 'mag', 'geo', 'decl', 'sza', 'glat', 'glon']
    extent = 60 * 60 * 24  # 1 full day

  # Try to load from cache
  if cache and not ignore_cache:
    data_json = _cache_read(stationid, delta, start, output_dir, format='json')
    if data_json is not None:
      data_json = _subset_json(data_json, start, requested_extent)
      if format == 'json':
        return data_json, None
      try:
        return _reformat(data_json, format=format), None
      except Exception as error:
        return None, {'url': None, 'error': str(error)}
  elif cache and ignore_cache:
    _, cache_json_file, _ = _cache_paths(stationid, delta, start, output_dir)
    if cache_json_file.exists():
      logger.debug(f"Ignoring cache hit: {cache_json_file}")


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

  if extra_parameters:
    extra_parameters_allowed = ['mlt', 'mag', 'geo', 'decl', 'sza', 'glat', 'glon']
    for parameter in extra_parameters:
      if parameter not in extra_parameters_allowed:
        raise ValueError(f"Invalid extra parameter: {parameter}. Allowed parameters are: {extra_parameters_allowed}")
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
    _cache_write(stationid, delta, start, data_json, output_dir)
    data_json = _subset_json(data_json, start, requested_extent)

  if format == 'json':
    return data_json, None

  if format == 'list' or format == 'dataframe':
    try:
      result = _reformat(data_json, format=format)
    except Exception as error:
      logger.debug(f"Failed to _reformat data for station {stationid}: {error}")
      return None, {'url': url, 'error': str(error)}
    return result, None


def _get(url):
  import urllib3
  import importlib

  certspec = importlib.util.find_spec("certifi")
  cafile = None
  if certspec is not None:
    import certifi

  logger.debug("Fetching URL: %s", url)
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

  logger.debug("  Fetched URL: %s", url)

  return response


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


def _reformat(data_json, format='list'):
  """
  data_json is a list of dicts, each dict has the form
  {
    'tval': 1573814400.0,
    'ext': 60.0,
    'iaga': 'HBK',
    'glon': 27.709999,
    'glat': -25.879997,
    'mlt': 12.647217,
    'mcolat': 125.510384,
    'decl': -18.616241,
    'sza': 13.026016,
    'N': {'nez': 6.80695, 'geo': 9.677255},
    'E': {'nez': 10.103335, 'geo': 7.400181},
    'Z': {'nez': 2.049171, 'geo': 2.049171}
  }
  """

  if format not in ['list', 'dataframe', 'csv']:
    raise ValueError("Invalid format. Must be 'list', 'dataframe', or 'csv'.")

  header = []
  for key in data_json[0]:
    if isinstance(data_json[0][key], dict):
      for subkey in data_json[0][key]:
        header.append(f"{key}_{subkey}")
    else:
      header.append(key)

  if debug_response:
    logger.debug(f"Header: {header}")
  # Flatten json_data
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

  if format == 'dataframe' or format == 'csv':
    import pandas
    from datetime import datetime, timezone

    df = pandas.DataFrame(data_rows, columns=header)

    # Add a Time column in ISO format
    df['tval_iso'] = df['tval'].apply(
      lambda x: datetime.fromtimestamp(x, tz=timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    )

    # Add a datetime column
    df['tval_datetime'] = pandas.to_datetime(df.index)

    # Put datetime and Time columns first
    df = df.loc[:, ['tval_datetime', 'tval_iso'] + header]

    if format == 'csv':
      return df.to_csv(index=False).rstrip()

    return df

  return [header] + data_rows


def _subset_json(data_json, start, extent):
  """Return only records within [start, start+extent) based on tval (Unix seconds)."""
  from datetime import datetime, timezone

  if not data_json or extent is None:
    return data_json

  # Parse start to a Unix timestamp
  start_str = str(start).rstrip('Z').replace(' ', 'T')
  for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
    try:
      start_dt = datetime.strptime(start_str, fmt).replace(tzinfo=timezone.utc)
      break
    except ValueError:
      continue
  else:
    logger.debug(f"Could not parse start time for subsetting: {start}")
    return data_json

  start_ts = start_dt.timestamp()
  stop_ts = start_ts + extent
  return [row for row in data_json if start_ts <= row['tval'] < stop_ts]


def _cache_paths(stationid, delta, start, output_dir):
  date_str = str(start)[:10]
  delta_str = str(delta) if delta is not None else 'none'
  cache_dir = output_dir / 'cache' / stationid.upper() / delta_str
  return cache_dir, cache_dir / f'{date_str}.json.pkl', cache_dir / f'{date_str}.dataframe.pkl'


def _cache_read(stationid, delta, start, output_dir, format='json'):
  """Return cached data_json (or _reformatted) if available, else return None."""
  import pickle

  _, cache_json_file, _ = _cache_paths(stationid, delta, start, output_dir)
  if not cache_json_file.exists():
    return None
  logger.debug(f"Cache hit: {cache_json_file}")
  with cache_json_file.open('rb') as f:
    data_json = pickle.load(f)
  if format == 'json':
    return data_json
  try:
    return _reformat(data_json, format=format)
  except Exception as error:
    logger.debug(f"Failed to _reformat cached data for station {stationid}: {error}")
    return None


def _cache_write(stationid, delta, start, data_json, output_dir):
  """Write data_json and its dataframe form to the cache. No-op if data_json is falsy."""
  import pickle

  if not data_json:
    return

  cache_dir, cache_json_file, cache_df_file = _cache_paths(stationid, delta, start, output_dir)
  cache_dir.mkdir(parents=True, exist_ok=True)

  with cache_json_file.open('wb') as f:
    pickle.dump(data_json, f)
  if debug_response:
    logger.debug(f"Cached JSON: {cache_json_file}")

  try:
    df = _reformat(data_json, format='dataframe')
    with cache_df_file.open('wb') as f:
      pickle.dump(df, f)
    if debug_response:
      logger.debug(f"Cached dataframe: {cache_df_file}")
  except Exception as error:
    logger.debug(f"Failed to cache dataframe for station {stationid}: {error}")


def parse_args():
  import argparse

  default_start = '2001-01-01T00:00:00.000000Z'
  default_stop  = '2001-01-01T00:01:00.000000Z'
  default_output_dir = pathlib.Path(__file__).resolve().parent.parent / 'data'

  parser = argparse.ArgumentParser(
    description='Fetch SuperMAG station data via data().',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=(
      'Examples:\n'
      '  supermag-data --userid USER --station ABK\n'
      '  supermag-data --userid USER --station ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z\n'
      '  supermag-data --userid USER --station ABK --no-cache\n'
      '  supermag-data --userid USER --station ABK --ignore-cache --debug\n'
    ),
  )
  parser.add_argument(
    '--station',
    default='ABK',
    help='SuperMAG station ID. Default: ABK.',
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
    choices=['json', 'csv'],
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
    '--output-dir',
    default=default_output_dir,
    type=pathlib.Path,
    help=f'Base directory for cache storage. Default: {default_output_dir}.'
  )
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.'
  )

  args = parser.parse_args()

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
  from .util import set_logging_level

  args = parse_args()

  if args.debug:
    set_logging_level(logging.DEBUG, [__name__])

  for arg in vars(args):
    logger.debug(f"{arg}: {getattr(args, arg)}")

  result, error = data(
    args.userid,
    args.station,
    args.start,
    args.extent,
    baseline=args.baseline,
    delta=args.delta,
    format=args.format,
    cache=args.cache,
    ignore_cache=args.ignore_cache,
    output_dir=args.output_dir,
  )

  if error is not None:
    logger.error(f"Error: {error}")
  else:
    if args.format == 'json':
      import json
      print(json.dumps(result, indent=2))
    elif args.format == 'csv':
      print(result)


if __name__ == '__main__':
  main()
