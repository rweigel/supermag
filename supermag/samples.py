"""
Usage:
  supermag-samples --help
"""

from .util import path_relative_to_cwd, logger
from .config import config

CONFIG = config()

def samples(userid,
              output_dir=CONFIG['common']['output_dir'],
              update=False,
              station_id=None,
              inventory=None,
              cafile=None):
  """Reads inventory file and fetches station endpoint samples.

  Fetches data on each station's first and last available day to get geographic
  latitude and longitude, writes results to samples.json, and updates inventory
  start/stop dates if no data is returned at those endpoints by searching forward
  from start and backward from stop.
  """


  import pathlib
  output_dir = pathlib.Path(output_dir)

  samples_file = output_dir / 'inventory' / 'samples.json'

  if inventory is None:
    inventory = _read_inventory(output_dir, station_id=station_id)

  samples_data = _fetch_samples(userid, inventory, update, cafile=cafile)

  _write_samples(samples_data, samples_file)

  if station_id is None:
    return samples_data
  else:
    return {station_id: samples_data.get(station_id, None)}


def _fetch_samples(userid,
                    inventory,
                    update=False,
                    cafile=None):

  samples = {}
  for entry in inventory:
    station_id = entry['id']

    start_isodate = f"{entry['startDate']}"
    stop_isodate = f"{entry['stopDate']}"

    args = [userid, station_id, start_isodate, entry, "first", update, cafile]
    # Will update entry if no data found on start_isodate
    location_start_row, error_start = _fetch_location(*args)

    args = [userid, station_id, stop_isodate, entry, "last", update, cafile]
    # Will update entry if no data found on stop_isodate
    location_stop_row, error_stop = _fetch_location(*args)

    location_start = _location_record(start_isodate, location_start_row, error_start)
    location_stop = _location_record(stop_isodate, location_stop_row, error_stop)
    sample_start = _sample_record(start_isodate, location_start_row, error_start)
    sample_stop = _sample_record(stop_isodate, location_stop_row, error_stop)

    samples[station_id] = {
      'location': {
        'description': 'Data from the glat and glon parameters on the timestamps given by start and stop.',
        'firstRecord': location_start,
        'lastRecord': location_stop,
      },
      'sample': {
        'description': 'Full first and last records from data() on the timestamps given by start and stop.',
        'firstRecord': sample_start,
        'lastRecord': sample_stop,
      },
    }

    _location_record_print(station_id, samples[station_id])

  return samples


def _fetch_location(userid,
                    station_id,
                    isodate,
                    entry,
                    value='first',
                    update=False,
                    cafile=None,
                    allow_retry=True):
  from .data import data as data

  logger.debug("")
  logger.debug(f"Fetching location for station {station_id} on {isodate}")
  extent = 60*60*24  # 1 day
  # update=True means refresh from source, so do not read from cache.
  data, error = data(userid, station_id, isodate, extent, use_cache=not update, cafile=cafile)

  if allow_retry and (error is not None or len(data) == 0):
    msg = "No data returned for {station_id} on {which} date for obtained from inventory requests."
    logger.error(msg.format(station_id=station_id, which=value))

    return _fetch_location_retry(userid, station_id, isodate, entry, value, update, cafile)

  if error is not None:
    emsg = f"Failed to fetch data for station {station_id} on {isodate}: {error}"
    logger.error(emsg)
    return None, emsg

  if not isinstance(data, list) or len(data) == 0:
    emsg = f"No data returned for station {station_id} on {isodate}"
    logger.error(emsg)
    return None, emsg

  if value == "first":
    first_row = data[0]
  elif value == "last":
    first_row = data[-1]
  else:
    raise ValueError(f"Invalid value parameter: {value}. Must be 'first' or 'last'.")

  if 'glat' not in first_row or 'glon' not in first_row:
    emsg = f"Missing 'glat' or 'glon' in data for station {station_id} at time {isodate}"
    logger.error(emsg)
    return None, emsg

  return first_row, None


def _fetch_location_retry(userid, station_id, isodate, entry, value, update, cafile):
  """Try alternative days when the primary date returns no data."""
  from datetime import datetime, timedelta

  # Could do binary search to reduce number of attempts, but for now try and
  # will report issue to SuperMAG.
  n_try = 7
  if value == 'first':
    day_offsets = range(1, n_try + 1)
  else:
    day_offsets = range(-1, -n_try - 1, -1)

  location = None
  error = None
  isodate_new = isodate
  for day_offset in day_offsets:
    date_new = datetime.strptime(isodate, "%Y-%m-%d")
    new_date = date_new + timedelta(days=day_offset)
    isodate_new = new_date.strftime("%Y-%m-%d")
    logger.info(f"  Trying {isodate_new}")
    location, error = _fetch_location(userid, station_id, isodate_new, entry, value, update, cafile, allow_retry=False)
    if error is None and location is not None:
      if value == 'first':
        logger.info(f"  Updating start day of first available data from {entry['startDate']} to {isodate_new}")
        entry['startDate'] = isodate_new
        entry['startDateExpected'] = isodate
      else:
        logger.info(f"  Updating stop day of last available data from {entry['stopDate']} to {isodate_new}")
        entry['stopDate'] = isodate_new
        entry['stopDateExpected'] = isodate
      break

  if error is not None or location is None:
    if value == 'first':
      logger.error(f"  Failed to update start date after trying {n_try} days. Updating to last attempted date {isodate_new}")
      entry['startDateError'] = f"Failed to update start date after trying {n_try} days"
      entry['startDate'] = isodate_new
    else:
      logger.error(f"  Failed to update stop date after trying {n_try} days. Updating to last attempted date {isodate_new}")
      entry['stopDateError'] = f"Failed to update stop date after trying {n_try} days"
      entry['stopDate'] = isodate_new

  return location, error


def _has_location(location_record):
  if location_record is None or not isinstance(location_record, dict):
    return False
  a = location_record.get('glat', None) is not None
  b = location_record.get('glon', None) is not None
  return a and b


def _location_record(isotime, location, error):
  if error is not None:
    return {
      'date': isotime if isotime is not None else '',
      'glat': None,
      'glon': None,
      'error': error
    }

  if location is None or not isinstance(location, dict):
    return {
      'date': isotime,
      'glat': None,
      'glon': None,
      'error': 'No location data returned'
    }

  return {
    'date': isotime,
    'glat': location.get('glat'),
    'glon': location.get('glon'),
  }


def _sample_record(isotime, location, error):
  if error is not None:
    return {
      'date': isotime if isotime is not None else '',
      'error': error
    }

  if location is None or not isinstance(location, dict):
    return {
      'date': isotime,
      'error': 'No sample data returned'
    }

  return dict(location)


def _location_record_print(station_id, location_record, threshold=None):

  location_entry = location_record.get('location', {}) if isinstance(location_record, dict) else {}
  location_start = _sample_record_get(location_entry, 'first')
  location_stop = _sample_record_get(location_entry, 'last')
  start_isodate = (location_start or {}).get('tval_iso', (location_start or {}).get('date', ''))
  stop_isodate = (location_stop or {}).get('tval_iso', (location_stop or {}).get('date', ''))

  logger.debug(station_id)
  start_msg = f"  Start {start_isodate}: {location_start}"
  stop_msg =  f"  Stop  {stop_isodate}:  {location_stop}"
  logger.debug(start_msg)
  logger.debug(stop_msg)


def _sample_record_get(location_record, which):
  if not isinstance(location_record, dict):
    return {}

  if which == 'first':
    return location_record.get('firstRecord', {})

  if which == 'last':
    return location_record.get('lastRecord', {})

  raise ValueError(f"Invalid which value: {which}. Must be 'first' or 'last'.")


def _read_inventory(output_dir, station_id=None):
  # Always read full inventory file. Will subset below.
  inventory_file = output_dir / 'inventory' / 'inventory.json'

  if not inventory_file.exists():
    raise ValueError(f"Inventory file not found: {inventory_file}. Run supermag-inventory first.")

  try:
    import json
    logger.debug(f"Reading {inventory_file}")
    inventory = json.loads(inventory_file.read_text())
  except Exception as error:
    raise ValueError(f"Failed to read inventory file {inventory_file}: {error}")

  if isinstance(inventory, dict) and 'inventory' in inventory:
    inventory = inventory['inventory']

  if not isinstance(inventory, list):
    raise ValueError(f"Inventory file {inventory_file} does not contain a list of stations")

  logger.debug(f"  Read {len(inventory)} stations from inventory file {inventory_file}")

  if station_id is not None:
    inventory = [entry for entry in inventory if entry.get('id') == station_id]
    if not inventory:
      raise ValueError(f"Station ID not found in inventory: {station_id}")
    logger.debug(f"  Filtered inventory to station {station_id}")

  return inventory


def _write_samples(samples, output_file):
  import json

  output_file.parent.mkdir(parents=True, exist_ok=True)
  with output_file.open('w') as stream:
    json.dump(samples, stream, indent=2)
    stream.write('\n')

  logger.debug(f'Wrote {path_relative_to_cwd(output_file)} with {len(samples)} station samples')


if __name__ == '__main__':
  from .cli import main_samples
  main_samples()
