from .util import logger

from .config import config
CONFIG = config()


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

  """Fetch data from the SuperMAG API.

  ----
  Args:
    userid (str): The user ID for SuperMAG.

    stationid (str): The three-letter IAGA station ID to fetch data for.
    start (str): The start time for the data request.

    extent (int) or start (str):
      extent: The extent of the data request in seconds (exclusive, e.g. if 
      extent=60, start=2001-01-01T00:00Z and extent=60, only data on 2001-01-01T00:00Z is returned for 1-minute cadence data.

      start: The start time for the data request in ISO 8601 format (e.g., 2001-01-01T00:00:00Z).

  Keyword Arguments:
    baseline (str): The baseline to use for the data request. Allowed values are 'all', 'none', or 'yearly'.

    delta (str): The delta to use for the data request. Allowed values are 'start' or 'none'.

    format (str): The format of the data request. Allowed values are 'json', 'csv', 'csv-hapi', 'csv-hapi-noheader', and 'dataframe'.

    parameters (list): The parameters to include in the output data.

    cadence (str): The cadence of the data request. Only allowed value is 'PT1M' (one-minute).

    cache (bool): Whether to cache the data.

    use_cache (bool): Whether to use cached data.

    cache_dir (str): The directory to use for caching data.

    cafile (str): The CA file to use for the data request.

  Returns:
    tuple: A tuple containing (data, error), where `data` is the fetched data and `error` is any error encountered.
  """
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

  if stationid == 'indices':
      dataset_type = 'indices'
  else:
      dataset_type = 'mag'

  _check_parameters(dataset_type, parameters, format)

  if isinstance(extent, str):
    extent = _stop_to_extent(start, extent)

  # Preserve the originally requested extent for sub-setting
  extent_requested = extent


  if use_cache:
    # Try to load from cache
    from supermag import data_cache
    args = (cache_dir,
            stationid,
            dataset_type,
            start,
            extent,
            extent_requested,
            cadence,
            parameters,
            delta,
            baseline)
    data = data_cache.get(*args)
    if data is not None:
      logger.debug(f"Subsetting JSON data to start={start}, extent={extent_requested}")
      data = _subset_time(data, start, extent_requested)
      return _reformat_json(data, dataset_type, parameters, format), None

  if cache:
    # When caching, always fetch from the start of the day and request an
    #  integer number of days.
    start_original = start
    extent_original = extent
    start = start[0:10] + "T00:00Z"
    seconds_per_day = 60 * 60 * 24
    extent = ((extent + seconds_per_day - 1) // seconds_per_day) * seconds_per_day
    logger.debug("cache=True =>")
    logger.debug(f"  Adjusting start from {start_original} to {start}")
    logger.debug(f"  Adjusting extent from {extent_original} to {extent}")


  request_params_common = f"logon={userid}&start={start}&extent={extent}"
  # Always request all parameters; will subset as needed.
  if stationid == 'indices':
    url = CONFIG['data']['indices']['base_url']
    request_parameters = CONFIG['data']['indices']['request_parameters']
  else:
    url = CONFIG['data']['mag']['base_url']
    request_parameters = CONFIG['data']['mag']['request_parameters']
    request_parameters_args = {
      'station': stationid,
      'start': start,
      'extent': extent,
      'delta': delta,
      'baseline': baseline,
    }
    request_parameters = request_parameters.format(**request_parameters_args)

  url += f"&{request_params_common}&{request_parameters}"

  data_json, error = _get_and_parse(url, stationid, dataset_type, format='json', cafile=cafile)
  if error is not None:
    return None, error


  if cache:
    write_error = False
    try:
      from supermag import data_cache
      args = (
        data_json,
        cache_dir,
        stationid,
        dataset_type,
        cadence,
        delta,
        baseline
      )
      data_cache.write(*args)
    except Exception as e:
      write_error = True
      logger.error(f"Failed to write cache for {stationid}: {e}")
    if not write_error:
      logger.debug(f"Cache write successful for {stationid}")

    # When cache=True, data request spans an integer number of full days.
    logger.debug(f"Subsetting JSON data to start={start}, extent={extent_requested}")
    data_json = _subset_time(data_json, start, extent_requested)

  if format == 'json' and parameters is None:
    return data_json, None

  data = _reformat_json(data_json, dataset_type, parameters, format)

  return data, None


def _get_and_parse(url, stationid, dataset_type, format='json', cafile=None):

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

    if not isinstance(data_json, list):
      return [], None

    if len(data_json) == 0:
      return [], None

    if not isinstance(data_json[0], dict):
      return {'url': url, 'error': "Malformed response from SuperMAG API. Expected an array of objects."}

    logger.debug("Keys in first row of JSON response:")
    logger.debug(f"  {list(data_json[0].keys())}")

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


def _check_parameters(dataset_type, parameters, format):

  import json
  import pathlib

  if parameters is None:
    return None

  if not isinstance(parameters, (list, tuple, set)):
    raise ValueError(f"Invalid parameters value: {parameters}. Must be a None, list, tuple, or set.")

  if format == 'json':
    known_parameters = CONFIG['data'][dataset_type]['response_parameters']
    if not all(param in known_parameters for param in parameters):
      unknown = [param for param in parameters if param not in known_parameters]
      raise ValueError(f"Unknown parameter(s) requested: {unknown}. Allowed: {known_parameters}")
    return

  if dataset_type == 'indices':
    file = 'catalog.indices.json'
  else:
    file = 'catalog.mag.json'

  _catalog_file = pathlib.Path(__file__).parent / file
  logger.debug(f"Reading catalog file: {_catalog_file}")
  with open(_catalog_file) as f:
    catalog = json.load(f)


def _reformat_json(data_json, dataset_type, parameters, format):
  """Convert json response data to the requested format.

  `data_json` is the response from _parse_response().
  For list input, nested dicts are flattened (e.g. N.nez -> N_nez).
  """
  import pandas
  from .config import config

  if format == 'json':
    if parameters is None:
      return data_json
    return _subset_json_parameters(data_json, parameters)

  logger.debug(f"Reformatting json data to format: {format}")

  formats = config('data')['formats']
  if format not in formats:
    raise ValueError(f"Invalid format. Must be one of: {formats}.")

  if len(data_json) == 0:
    # Return appropriate empty structure based on format.
    # For CSV, we can't return the header 
    if format.startswith('csv'):
      return ''
    if format == 'dataframe':
      # Return empty dataframe
      return pandas.DataFrame()


  keys = config('data')[dataset_type]['response_parameters']
  dicts = config('data')[dataset_type]['response_parameter_dicts']

  wmsg = "Ignoring unknown key in first object of JSON data array: "
  for key in data_json[0].keys():
    if key not in keys:
      logger.warning(f"{wmsg}'{key}'. Expected one of: {keys}")
    if isinstance(data_json[0][key], dict):
      for subkey in data_json[0][key].keys():
        if subkey not in dicts[key]:
          logger.warning(f"{wmsg}key '{subkey}' in '{key}' parameter object. Expected one of: {dicts.get(key, [])}")


  # Determine columns that are known.
  columns_known = []
  for key in keys:
    if key in dicts:
      for subkey in dicts[key]:
        columns_known.append(f"{key}_{subkey}")
    else:
      columns_known.append(key)

  # Determine if any requested parameters are not valid columns.
  for parameter in parameters:
    if parameter not in columns_known:
      raise ValueError(f"Requested parameter not known: {parameter}. Known parameters: {columns_known}")


  # Determine which columns to keep based on requested parameters and
  # maintain the order of columns as they appear in columns_known.
  columns_keep = []
  for parameter in columns_known:
    if parameter in parameters:
      columns_keep.append(parameter)

  if 'tval' not in columns_keep:
    # Always return tval
    columns_keep = ['tval'] + columns_keep

  # Flatten nested dicts in the JSON data. This converts nested dictionaries
  # into columns with names of the form "key_subkey".
  df = pandas.json_normalize(data_json, sep='_')

  # Keep only columns requested in order set by columns_known.
  df = df[columns_keep]

  if format == 'hapi-binary':
    #int64_cols = df.select_dtypes(include=['int64']).columns
    #if len(int64_cols) > 0:
    #  df[int64_cols] = df[int64_cols].astype('int32')
    pass

  if format in ['csv', 'csv-hapi', 'csv-hapi-noheader']:
    if format in ['csv-hapi', 'csv-hapi-noheader']:
      # Drop tval and replace with parameter named Time in ISO 8601 format
      tval_iso = pandas.to_datetime(df['tval'], unit='s', utc=True).dt.strftime('%Y-%m-%dT%H:%MZ')
      df = df.drop(columns=['tval'])
      df.insert(0, 'Time', tval_iso)

    for col in df.columns:
      # Reprocess columns and convert columns with list values to comma-separated strings.
      # E.g., ...,"[66.365166, 66.365166, ...]", "['ABK', 'ABC', ...]", ...
      # =>        "66.365166, 66.365166, ...", "'ABK', 'ABC', ...", ...
      if df[col].apply(lambda x: isinstance(x, list)).any():
        df[col] = df[col].apply(lambda x: ','.join(str(v) for v in x) if isinstance(x, list) else x)

    include_header = format in ['csv', 'csv-hapi']
    return df.to_csv(index=False, header=include_header).rstrip()


  # Always prepend tval_datetime in dataframe
  if format == 'dataframe':
    tval_datetime = pandas.to_datetime(df['tval'], unit='s', utc=True)
    tval_iso = tval_datetime.dt.strftime('%Y-%m-%dT%H:%MZ')
    df.insert(0, 'tval_iso', tval_iso)
    df.insert(0, 'tval_datetime', tval_datetime)
    return df


def _subset_json_parameters(data_json, parameters):
  if parameters is None:
    return data_json

  logger.debug(f"Subsetting JSON data to parameters: {parameters}")
  filtered = []
  parameters = ['tval'] + parameters
  for row in data_json:
    row_filtered = {}
    for key, value in row.items():
      if key in parameters:
        row_filtered[key] = value
    filtered.append(row_filtered)

  return filtered


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

  from .util import t_val2iso
  logger.debug(f"Subsetting data to start={start}, extent={extent}")
  logger.debug(f"  Original start: {t_val2iso(data[0]['tval'])}")
  logger.debug(f"  Original end:   {t_val2iso(data[-1]['tval'])}")

  data_subsetted = [row for row in data if start_ts <= row['tval'] < stop_ts]
  logger.debug(f"  Subsetted start {t_val2iso(data_subsetted[0]['tval'])}")
  logger.debug(f"  Subsetted end   {t_val2iso(data_subsetted[-1]['tval'])}")

  return data_subsetted


if __name__ == '__main__':
  from .cli import main_data
  main_data()
