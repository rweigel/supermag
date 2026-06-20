import utilrsw
logger = utilrsw.logger(
  color=True,
  console_format='%(name)s %(levelname)s: %(message)s')


def get(url, format='json', cafile=None, retry=1, timeout=30):
  import os
  import certifi

  import urllib3
  from urllib3.util.retry import Retry

  logger.debug("Getting URL: %s", url)

  pool_kwargs = {}
  if cafile is not None:
    if cafile != 'none':
      if os.path.isfile(cafile):
        pool_kwargs['ca_certs'] = cafile
      elif cafile.lower() == 'default':
        pool_kwargs['ca_certs'] = certifi.where()
      else:
        raise ValueError(f"Invalid cafile value: '{cafile}'. Must be 'default', 'none', or path to PEM file.")
      logger.debug(f"  Using CA certificates from: {pool_kwargs['ca_certs']}")

  try:
    retries = Retry.from_int(retry)
    http = urllib3.PoolManager(retries=retries, **pool_kwargs)
    headers = {'User-Agent': 'supermag-hapi-server'}
    response = http.request('GET', url, timeout=timeout, headers=headers)
  except Exception as error:
    logger.debug(f"  Failed: {error}")
    return None, f"Error fetching URL: {error}"

  if response.status >= 400:
    response.release_conn()
    return None, f"HTTP {response.status} for {url}"

  logger.debug("Got URL: %s", url)

  return _parse_response(response, format=format)


def _parse_response(response, format=None):
  import re
  import json

  debug_response = False

  if format not in [None, 'string', 'json']:
    raise ValueError("Invalid format. Must be one of: None, 'string', 'json'.")

  response_str = ''
  try:
    response_str = response.data.decode('utf-8')
    if debug_response:
      logger.debug(f"Raw response string (first 80 chars): {response_str[0:80]}")
  except Exception as error:
    return None, f"Error: response.data.decode('utf-8') gave error '{error}' response: {response}"
  finally:
    response.release_conn()

  try:
    # JSON does not allow NaN
    regex = r'\b(?:NaN|nan|Infinity|inf|-Infinity|-inf)\b'
    response_str = re.sub(regex, 'null', response_str, flags=re.IGNORECASE)
  except Exception as error:
    return None, f"Error {error} when replacing NaN/Inf in response string '{response_str}'"

  if response_str.startswith("ERROR"):
    error = Exception(response_str)
    return None, error

  if format is None or format == 'string':
    return response_str

  if len(response_str) == 0:
    return {}, None

  try:
    data_json = json.loads(response_str)
  except Exception as error:
    error = Exception(f"json.loads() error '{error}' for response (first 80 chars): '{response_str[0:80]}'")
    return None, error

  return data_json, None


def write_json_and_archive(data, file_path, archive_dir=None):
  import json
  import gzip
  import pathlib

  import datetime as dt

  timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

  from .util import path_relative_to_cwd

  file_path = pathlib.Path(file_path)
  if archive_dir is not None:
    archive_dir = pathlib.Path(archive_dir)

  file_path.parent.mkdir(parents=True, exist_ok=True)
  if archive_dir is not None:
    archive_dir.mkdir(parents=True, exist_ok=True)

  logger.info(f'Writing {path_relative_to_cwd(file_path)} with {len(data)} entries')
  with file_path.open('w') as stream:
    json.dump(data, stream, indent=2)
    stream.write('\n')

  if archive_dir is None:
    return

  archive_path = pathlib.Path(archive_dir) / f'{file_path.stem}-{timestamp}.json.gz'
  logger.info(f'Writing {path_relative_to_cwd(archive_path)}')
  with gzip.open(archive_path, 'wt') as stream:
    json.dump(data, stream, indent=2)
    stream.write('\n')


def write_files(data,
                output_dir,
                start,
                stop,
                station_id=None,
                partial_inventory=False,
                file_type='inventory'):
  """Write combined inventory/catalog JSON files and archive full writes.

  For full writes, writes to:
    - inventory: output_dir/inventory/inventory.json
    - catalog:   output_dir/catalog/catalog.json

  For partial writes, writes to output_dir/<type>/partial/...
  and does not archive.
  """
  import datetime as dt
  import pathlib

  output_dir = pathlib.Path(output_dir)
  output_dir.mkdir(parents=True, exist_ok=True)

  if file_type not in ('inventory', 'catalog'):
    raise ValueError(f"Invalid file_type: {file_type}")

  start_label = start if start is not None else 'none'
  stop_label = stop if stop is not None else 'none'

  if station_id is None:
    if partial_inventory:
      output_file = output_dir / file_type / 'partial' / f'{file_type}-{start_label}-{stop_label}.json'
      archive_path = None
      payload = data
    else:
      output_file = output_dir / file_type / f'{file_type}.json'
      archive_path = output_dir / file_type / 'archive'
      last_update = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
      payload = {
        'lastUpdate': last_update,
        file_type: data,
      }
  else:
    output_file = output_dir / file_type / 'partial' / f'{file_type}-{station_id}.json'
    archive_path = None
    payload = data

  write_json_and_archive(payload, output_file, archive_path)


def move_log_files(log_files, dst_dir, archive=False):
  import gzip
  import shutil
  import pathlib
  import datetime

  pathlib.Path(dst_dir).mkdir(parents=True, exist_ok=True)

  for log_file in log_files:
    src = pathlib.Path(log_file)
    if src.exists():
      # Move log file to the output directory
      dst = pathlib.Path(dst_dir) / log_file
      logger.info(f"Moving {src} to {dst}")
      shutil.move(str(src), str(dst))

      if not archive:
        continue

      # Copy dst to archive and rename to dst-{timestamp}.log
      timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H:%M:%SZ")
      archive_dst = pathlib.Path(dst_dir) / 'archive' / f"{pathlib.Path(log_file).stem}-{timestamp}.log"
      archive_dst.parent.mkdir(parents=True, exist_ok=True)
      logger.info(f"Copying {dst} to {archive_dst}")
      shutil.copy2(str(dst), str(archive_dst))

      with open(archive_dst, 'rb') as f_in:
        with gzip.open(f"{archive_dst}.gz", 'wb') as f_out:
          f_out.writelines(f_in)
      archive_dst.unlink()


def parse_timestamp(timestamp):
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


def data_range():
  start_data = '1970-01-01'
  import datetime as dt
  tomorrow = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)
  stop_data  = (tomorrow).isoformat()
  return start_data, stop_data


def path_relative_to_cwd(path):
  import os
  from pathlib import Path
  return f"./{Path(os.path.relpath(Path(path).resolve(), Path.cwd()))}"


def check_userid(userid):
  if not userid:
    raise ValueError(f"SuperMAG user id is required. Got: {userid}")

  if userid == 'USERID':
    raise ValueError("Provide a valid SuperMAG user id instead of the placeholder 'USERID'")
