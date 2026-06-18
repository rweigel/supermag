import utilrsw
logger = utilrsw.logger(
  color=True,
  console_format='%(name)s %(levelname)s: %(message)s')


def get(url, format='json', cafile=None, timeout=30):
  import os
  import urllib3
  import certifi

  logger.debug("Getting URL: %s", url)

  pool_kwargs = {}
  if cafile is not None:
    if os.path.isfile(cafile):
      pool_kwargs['ca_certs'] = cafile
    elif cafile.lower() == 'default':
      pool_kwargs['ca_certs'] = certifi.where()
    else:
      raise ValueError(f"Invalid cafile value: {cafile}. Must be 'default', 'none', or path to PEM file.")
    logger.debug(f"  Using CA certificates from: {pool_kwargs['ca_certs']}")

  try:
    http = urllib3.PoolManager(**pool_kwargs)
    response = http.request('GET', url, timeout=timeout)
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

  try:
    longstring = response.data.decode('utf-8')
    if debug_response:
      logger.debug(f"Raw response string (first 80 chars): {longstring[0:80]}")
    # JSON does not allow NaN
    longstring = re.sub(r'\b(?:NaN|nan|Infinity|inf|-Infinity|-inf)\b', 'null', longstring, flags=re.IGNORECASE)
  except Exception as error:
    return None, f"Error: '{error}' for response data: '{longstring}'"
  finally:
    response.release_conn()

  if longstring.startswith("ERROR"):
    error = Exception(longstring)
    return None, error

  if format is None or format == 'string':
    return longstring

  if len(longstring) == 0:
    return {}, None

  try:
    data_json = json.loads(longstring)
  except Exception as error:
    error = Exception(f"json.loads() error '{error}' for response (first 80 chars): '{longstring[0:80]}'")
    return None, error

  return data_json, None


def write_combined_files(inventory, output_dir, start, stop, station_id=None, partial_inventory=False):

  import json
  import gzip
  import pathlib
  import datetime as dt

  from .util import path_relative_to_cwd

  output_dir = pathlib.Path(output_dir)

  output_dir.mkdir(parents=True, exist_ok=True)
  timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
  if station_id is None:
    if partial_inventory:
      inventory_file = output_dir / 'partial' / f'inventory-{start}-{stop}.json'
      archive_file = None
    else:
      inventory_file = output_dir / 'inventory.json'
      archive_file = output_dir / 'archive' / f'inventory-{timestamp}.json.gz'
      archive_file.parent.mkdir(parents=True, exist_ok=True)
  else:
    inventory_file = output_dir / 'partial' / f'inventory-{station_id}.json'
    archive_file = None

  inventory_file.parent.mkdir(parents=True, exist_ok=True)

  logger.info(f'Writing {path_relative_to_cwd(inventory_file)} with {len(inventory)} stations')
  with inventory_file.open('w') as stream:
    json.dump(inventory, stream, indent=2)
    stream.write('\n')

  if archive_file is None:
    return

  logger.info(f'Writing {path_relative_to_cwd(archive_file)} with {len(inventory)} stations')
  with gzip.open(archive_file, 'wt') as stream:
    json.dump(inventory, stream, indent=2)
    stream.write('\n')


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
    raise ValueError("SuperMAG user id is required")

  if userid == 'USERID':
    raise ValueError("Provide a valid SuperMAG user id instead of the placeholder 'USERID'")
