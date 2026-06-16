import logging


def configure_logging(name, level=logging.INFO, format_string='%(name)s: %(message)s'):
  logging.basicConfig(level=level, format=format_string)
  logger = logging.getLogger(name)
  logger.setLevel(level)
  return logger


def set_logging_level(level, logger_names=None):
  logging.getLogger().setLevel(level)
  if logger_names is None:
    return

  for logger_name in logger_names:
    logging.getLogger(logger_name).setLevel(level)


def get(url, format='json', cafile=None, timeout=30):
  import os
  import urllib3
  import certifi

  logger = logging.getLogger(__name__)

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
    logger.debug("  Getting response using urllib3.PoolManager().request('GET', url)")
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

  logger = logging.getLogger(__name__)

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


def path_relative_to_cwd(path):
  import os
  from pathlib import Path
  return Path(os.path.relpath(Path(path).resolve(), Path.cwd()))


def check_userid(userid):
  if not userid:
    raise ValueError("SuperMAG user id is required")

  if userid == 'USERID':
    raise ValueError("Provide a valid SuperMAG user id instead of the placeholder 'USERID'")

