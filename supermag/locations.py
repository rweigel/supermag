"""
Usage:
  supermag-locations --help
  supermag-locations
"""

from .util import path_relative_to_cwd, configure_logging
from .config import config

logger = configure_logging()
CONFIG = config()


def locations(userid,
              output_dir=CONFIG['common']['output_dir'],
              update=False,
              station_id=None):

  locations_file = output_dir / 'inventory' / 'locations.json'

  # Read existing locations from file if it exists
  locations = _read_locations(locations_file)

  inventory = _read_inventory(output_dir, station_id=station_id)

  locations_new = _fetch_locations(userid, inventory, output_dir, locations, update)

  # Merge new locations with existing locations
  if station_id is None:
    logger.debug("Merging existing locations with possibly updated locations.")
  else:
    logger.debug(f"Replacing existing location for {station_id} with possibly updated location.")
  locations.update(locations_new)

  # Print missing locations to console
  missing_locations = [
    station_id for station_id, loc in locations.items()
    if not _has_location(loc.get('start', {})) and not _has_location(loc.get('stop', {}))
  ]
  if missing_locations:
    logger.error(f'Missing locations for {len(missing_locations)} stations:')
    for station_id in missing_locations:
      logger.error(f'  Station ID: {station_id}')

  # Write updated locations to file
  _write_locations(locations, locations_file)

  if station_id is None:
    return locations
  else:
    return locations.get(station_id, None)

def _fetch_locations(userid,
                    inventory,
                    output_dir=CONFIG['common']['output_dir'],
                    existing_locations=None,
                    update=False):

  import copy

  existing_locations = existing_locations or {}
  existing_locations = copy.deepcopy(existing_locations)

  locations = {}
  for entry in inventory:
    station_id = entry['id']

    existing_location = existing_locations.get(station_id)

    start_isodate = f"{entry['startDate']}"
    stop_isodate = f"{entry['stopDate']}"

    if not update and existing_location:
      location_start = existing_location.get('start', {})
      location_stop = existing_location.get('stop', {})
      if _has_location(location_start) or _has_location(location_stop):
        logger.debug(f"{station_id} already has location, skipping fetch because update=False.")
        _print_location_info(station_id, location_start, location_stop, start_isodate, stop_isodate)
        locations[station_id] = existing_location
        continue

    location_start, error_start = _fetch_location(userid, station_id, start_isodate, "first", update=update)
    location_stop, error_stop = _fetch_location(userid, station_id, stop_isodate, "last", update=update)

    _print_location_info(station_id, location_start, location_stop, start_isodate, stop_isodate)

    location_start = _location_record(stop_isodate, location_start, error_start)
    location_stop = _location_record(stop_isodate, location_stop, error_stop)

    if _has_location(location_start) or _has_location(location_stop):
      locations[station_id] = {
        'geo_location_changed': _locations_match(location_start, location_stop),
        'start': location_start,
        'stop': location_stop,
      }
    else:
      emsg = f"Failed to fetch location for station {station_id}"
      if existing_location:
        logger.debug(f"{emsg}, but existing location found. Keeping existing location.")
        locations[station_id] = existing_location
      else:
        logger.debug(f"{station_id}, and no existing location found. Adding empty location.")
        locations[station_id] = {
          'geo_location_changed': None,
          'start': _location_record('', None, error_start),
          'stop': _location_record('', None, error_stop)
        }

  return locations


def _fetch_location(userid,
                    station_id,
                    isodate,
                    value='first',
                    update=False):
  from .data import data as data

  logger.debug(f"Fetching location for station {station_id} on {isodate}")
  extent = 60*60*24  # 1 day
  data, error = data(userid, station_id, isodate, extent)

  if error is not None:
    emsg = f"Failed to fetch data for station {station_id} on {isodate}: {error}"
    logger.debug(emsg)
    return None, emsg

  if not isinstance(data, list) or len(data) == 0:
    emsg = f"No data returned for station {station_id} on {isodate}"
    logger.debug(emsg)
    return None, emsg

  if value == "first":
    first_row = data[0]
  elif value == "last":
    first_row = data[-1]
  else:
    raise ValueError(f"Invalid value parameter: {value}. Must be 'first' or 'last'.")

  if 'glat' not in first_row or 'glon' not in first_row:
    return None, f"Missing 'glat' or 'glon' in data for station {station_id} at time {isodate}"

  return (first_row['glat'], first_row['glon']), None


def _has_location(location_record):
  if location_record is None:
    return False
  a = location_record.get('glat', None) is not None
  b = location_record.get('glon', None) is not None
  return a and b


def _location_record(isotime, location, error):
  if error is not None:
    return {
      'datetime': isotime if isotime is not None else '',
      'glat': None,
      'glon': None,
      'error': error
    }

  return {
    'datetime': isotime,
    'glat': location[0],
    'glon': location[1]
  }


def _locations_match(start_location, stop_location):
  if not _has_location(start_location) or not _has_location(stop_location):
    return None

  return (
    start_location.get('glat') == stop_location.get('glat')
    and start_location.get('glon') == stop_location.get('glon')
  )


def _print_location_info(station_id, location_start, location_stop, start_isodate, stop_isodate):

  start_msg = f"  Start location on {start_isodate}: {location_start}"
  stop_msg =  f"  Stop location on {stop_isodate}:  {location_stop}"
  if not _locations_match(location_start, location_stop):
    logger.warning(f"  Warning: {station_id} has different locations at start and stop times.")
    logger.warning(f"  {start_msg}")
    logger.warning(f"  {stop_msg}")
  else:
    logger.debug(start_msg)
    logger.debug(stop_msg)


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

  if not isinstance(inventory, list):
    raise ValueError(f"Inventory file {inventory_file} does not contain a list of stations")

  logger.debug(f"  Read {len(inventory)} stations from inventory file {inventory_file}")

  if station_id is not None:
    inventory = [entry for entry in inventory if entry.get('id') == station_id]
    if not inventory:
      raise ValueError(f"Station ID not found in inventory: {station_id}")
    logger.debug(f"  Filtered inventory to station {station_id}")

  return inventory


def _read_locations(output_file):
  import json

  locations = {}
  if not output_file.exists():
    logger.debug(f"No existing locations file found at {output_file}, starting with empty locations.")
    return locations
  else:
    logger.debug(f"Using existing locations from {output_file}")

  logger.debug(f"Reading {output_file}")
  with output_file.open() as stream:
    locations = json.load(stream)

  logger.debug(f"  Read {len(locations)} station locations from {output_file}")

  return locations


def _write_locations(locations, output_file):
  import json

  output_file.parent.mkdir(parents=True, exist_ok=True)
  with output_file.open('w') as stream:
    json.dump(locations, stream, indent=2)
    stream.write('\n')

  logger.debug(f'Wrote {path_relative_to_cwd(output_file)} with {len(locations)} station locations')


if __name__ == '__main__':
  from .cli import main_locations
  main_locations()
