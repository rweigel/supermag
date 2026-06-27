from .util import logger

from .config import config
CONFIG = config()


def read(output_dir, stationid, start, extent, cadence, delta, baseline):

  import pickle

  try:
    cache_file = _path(output_dir, stationid, start, extent, cadence, delta, baseline)
  except Exception as e:
    logger.debug(f"Failed to construct cache file path: {e}")
    return None

  if not cache_file.exists():
    logger.debug(f"Cache file does not exist: {cache_file}")
    return None

  try:
    logger.debug(f"Reading cache file: {cache_file}")
    with cache_file.open('rb') as f:
      data = pickle.load(f)
    return data
  except Exception as e:
    logger.error(f"Failed to read cache file {cache_file}: {e}")
    return None


def write(data, output_dir, stationid, start, extent, cadence, delta, baseline):

  if not data:
    msg = "data = []. Not writing cache, becuase likely an error occurred in "
    msg += "the SuperMAG API (it has returned '' when previous requests "
    msg += "and the other endpoints are returning errors)."
    logger.debug(msg)
    return None
  try:
    cache_file = _path(output_dir, stationid, start, extent, cadence, delta=None, baseline=None)
  except Exception as e:
    logger.debug(f"Failed to construct cache file path: {e}")
    return None

  cache_file = _path(output_dir, stationid, start, extent, cadence, delta=delta, baseline=baseline)
  try:
    _write_atomic_pkl(cache_file, data)
  except Exception as e:
    logger.error(f"Failed to write cache file {cache_file}: {e}")


def _path(output_dir, stationid, start, extent, cadence, delta, baseline):

  import pathlib
  if output_dir is None:
    pkg_dir = pathlib.Path(__file__).resolve().parent.parent
    output_dir = pkg_dir / pathlib.Path(CONFIG['common']['output_dir'])
  else:
    output_dir = pathlib.Path(output_dir)

  cache_dir = output_dir / 'cache'

  if stationid == 'indices':
    sub_dir = pathlib.Path(f'indices/{cadence}')
  else:
    baseline_str = baseline if baseline is not None else 'none'
    delta_str = delta if delta is not None else 'none'
    sub_dir = pathlib.Path(f"mag/{cadence}/{stationid}/baseline-{baseline_str}/delta-{delta_str}")

  cache_file = pathlib.Path(f"{start}-{extent}.pkl")

  cache_path = cache_dir / sub_dir / cache_file

  return cache_path


def _write_atomic_pkl(path, data):

  # TODO: Write gzip-compressed pickle files (reduces file size by factor of 3)
  import os
  import pickle
  import secrets

  path.parent.mkdir(parents=True, exist_ok=True)
  tmp_ext = f".{secrets.token_hex(6)}.tmp"
  tmp_path = path.with_suffix(path.suffix + tmp_ext)
  try:
    with tmp_path.open('wb') as f:
      pickle.dump(data, f)
    os.replace(tmp_path, path)
  except Exception:
    try:
      tmp_path.unlink()
    except OSError:
      pass
    raise
