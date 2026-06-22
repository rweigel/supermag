from .util import logger

from .config import config
CONFIG = config()


def get(cache_dir,
              stationid,
              dataset_type,
              format,
              start,
              extent,
              extent_requested,
              cadence,
              parameters=None,
              delta=None,
              baseline=None):

  if False:
    _locals = locals()
    logger.debug("data.get() called with arguments:")
    for arg in _locals:
      logger.debug(f"  {arg}: {_locals[arg]}")

  from .data import _subset_time, _subset_parameters, _reformat_json

  if format not in ['json', 'dataframe', 'csv', 'csv-hapi', 'csv-hapi-noheader']:
    raise ValueError("Invalid format. Must be one of: 'json', 'dataframe', 'csv', 'csv-hapi', 'csv-hapi-noheader'.")

  # csv and parameter-subset dataframe are generated from JSON records.
  file_ext = 'dataframe' if format == 'dataframe' and parameters is None else 'json'
  cached = _read(cache_dir,
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
    return _reformat_json(data, dataset_type, format='dataframe'), None

  return _reformat_json(data, dataset_type, format=format), None


def write(data_json,
          cache_dir,
          stationid,
          dataset_type,
          cadence,
          parameters=None,
          delta=None,
          baseline=None):
  """Write list of dicts and a dataframe to the cache in one-day chunks. No-op if data_json is falsy."""

  from .util import t_val2iso
  from .data import _reformat_json

  if not data_json:
    return

  # Group rows in data_json by date (UTC)
  days = {} # Keys of date
  for row in data_json:
    date = t_val2iso(row['tval'])[0:10]
    days.setdefault(date, []).append(row)

  cache_dir = _path(cache_dir,
                          stationid,
                          cadence,
                          parameters=parameters,
                          delta=delta,
                          baseline=baseline)

  cache_dir.mkdir(parents=True, exist_ok=True)

  for date, data_json in days.items():

    logger.debug("Writing cache for data with ")
    logger.debug(f"  first timestamp: {t_val2iso(data_json[0]['tval'])}")
    logger.debug(f"  last timestamp:  {t_val2iso(data_json[-1]['tval'])}")
    logger.debug(f"  number of records: {len(data_json)}")

    for format in ('json', 'dataframe'):
      # Write day chunk
      try:
        cache_file = cache_dir / f'{date}.{format}.pkl'
        if format == 'json':
          _write_atomic_pkl(cache_file, data_json)
        else:
          data = _reformat_json(data_json, dataset_type, format='dataframe')
          _write_atomic_pkl(cache_file, data)
        logger.debug(f"Wrote: {cache_file}")
      except Exception as e:
        logger.debug(f"Failed to write cache file {cache_file}: {e}")
        raise e


def _path(cache_dir,
               stationid,
               cadence,
               parameters=None,
               delta=None,
               baseline=None):

  if False:
    _locals = locals()
    logger.debug("data._path() called with arguments:")
    for arg in _locals:
      logger.debug(f"  {arg}: {_locals[arg]}")


  import pathlib
  if cache_dir is None:
    pkg_dir = pathlib.Path(__file__).resolve().parent.parent
    cache_dir = pkg_dir / CONFIG['common']['output_dir']
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


def _read(cache_dir,
               stationid,
               start,
               extent,
               format='json',
               cadence='PT1M',
               parameters=None,
               delta=None,
               baseline=None):
  """Return cached data for full-day files from [start, start+extent). Returns None if any chunk is missing."""

  if False:
    _locals = locals()
    logger.debug("data_cache._read() called with arguments:")
    for arg in _locals:
      logger.debug(f"  {arg}: {_locals[arg]}")


  import pickle
  import pandas
  import datetime

  if format not in ['json', 'dataframe']:
    raise ValueError("Invalid format. Must be 'json' or 'dataframe'.")

  cache_dir = _path(cache_dir,
                          stationid,
                          cadence,
                          parameters=parameters,
                          delta=delta,
                          baseline=baseline)

  # Determine which UTC dates are needed
  start_str = str(start).rstrip('Z').replace(' ', 'T')
  for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
    try:
      tzinfo = datetime.timezone.utc
      start_dt = datetime.datetime.strptime(start_str, fmt).replace(tzinfo=tzinfo)
      break
    except ValueError:
      continue
  else:
    return None

  secs_per_day = 60 * 60 * 24
  n_days = max(1, (extent + secs_per_day - 1) // secs_per_day) if extent else 1
  dates = [start_dt.date() + datetime.timedelta(days=i) for i in range(n_days)]

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
    return pandas.concat(chunks, ignore_index=True)

  # json: list of dicts
  result = []
  for chunk in chunks:
    result.extend(chunk)
  return result


def _write_atomic_pkl(path, obj):

  # TODO: Write gzip-compressed pickle files (reduces file size by factor of 3)
  import os
  import pickle
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
