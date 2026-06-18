"""
For usage, see:
  supermag-inventory --help
"""

from .util import logger

from .config import config
CONFIG = config()


def inventory(userid,
              start=None,
              stop=None,
              output_dir=CONFIG['common']['output_dir'],
              update_inventory=False,
              update_locations=False,
              include_locations=True,
              station_id=None,
              cafile=None):

  import pathlib
  output_dir = pathlib.Path(output_dir)

  from .util import data_range
  start_data, stop_data = data_range()
  if start is None:
    start = start_data
  if stop is None:
    stop = stop_data

  from .util import parse_timestamp
  start_dt = parse_timestamp(start)
  stop_dt = parse_timestamp(stop)
  if stop_dt <= start_dt:
    raise ValueError(f"Stop time must be after start time. Got start={start}, stop={stop}")

  partial_inventory = False
  if start_dt > parse_timestamp(start_data):
    partial_inventory = True
  if stop_dt < parse_timestamp(stop_data):
    partial_inventory = True

  kwargs = {
    'output_dir': output_dir,
    'update': update_inventory
  }
  inventories = get_inventories(start, stop, **kwargs)

  station_availability = {}
  logger.info(f'Converting {len(inventories)} by day to inventories by station ID')
  for inventory_date, station_ids in inventories.items():
    s = '' if len(station_ids) == 1 else 's'
    for sid in station_ids:
      if sid not in station_availability:
        station_availability[sid] = []
      station_availability[sid].append(inventory_date)


  s = '' if len(station_availability) == 1 else 's'
  logger.info(f'Adding {{start,stop}}Date and availability info to inventories by station ID for {len(station_availability)} station{s}')
  inventory = []
  for inventory_station_id, available_dates in station_availability.items():
    available_dates = sorted(available_dates)
    entry = {
        'id': inventory_station_id,
        'startDate': available_dates[0],
        'stopDate': available_dates[-1],
        'availability': {'available_percent': 100.0}
      }

    all_dates = _date_range(available_dates[0], available_dates[-1], format='str')
    if len(all_dates) != len(available_dates):
      entry['availability']['available'] = available_dates
      available_percent = 100 * len(available_dates) / len(all_dates)
      entry['availability']['available_percent'] = round(available_percent, 2)
      entry['availability']['unavailable'] = sorted(set(all_dates) - set(available_dates))

    inventory.append(entry)

  if station_id is not None:
    inventory = [entry for entry in inventory if entry['id'] == station_id]
    if not inventory:
      logger.info(f"{station_id} not found in inventory from {start} through {stop}")
      return []
    logger.info(f'Filtered inventory to station {station_id}')

  if not include_locations:
    geo_locations = None
    logger.info("Not getting geographic locations for each station on start and stop dates")
  else:
    from .locations import locations

    if update_locations:
      logger.info("Getting geographic locations for each station on start and stop dates (using cached data, if available)")
    else:
      logger.info("Getting geographic locations for each station on start and stop dates")

    kwargs = {
      'output_dir': output_dir,
      'update': update_locations,
      'station_id': station_id,
      'inventory': inventory
    }
    geo_locations = locations(userid, **kwargs)

  station_info = _get_station_info(cafile=cafile)

  logger.info("Adding geographic locations to inventory entries")

  for entry in inventory:
    if geo_locations is not None:
      if entry['id'] in geo_locations:
        entry['location'] = geo_locations[entry['id']]
    if entry['id'] in station_info:
      entry['station'] = station_info[entry['id']]

  _print_summary(inventory)


  kwargs = {
    'start': start,
    'stop': stop,
    'station_id': station_id,
    'partial_inventory': partial_inventory
  }

  _write_combined_files(inventory, output_dir, **kwargs)

  return inventory


def get_inventories(start, stop,
                    output_dir=CONFIG['common']['output_dir'],
                    update=False):

  import time
  import pathlib

  from .util import path_relative_to_cwd

  def parse_date(value):
    import datetime as dt
    return dt.datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)

  def inventory_file_path(output_dir, start):
    return output_dir / "inventory" / "daily" / f"{start:%Y-%m-%d}.json"

  def write_inventory_file(output_dir, start, inventory_data):
    import json
    output_file = inventory_file_path(output_dir, start)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(inventory_data, indent=2) + '\n')
    return output_file

  def read_inventory_file(output_dir, start):
    import json
    input_file = inventory_file_path(output_dir, start)
    if not input_file.exists():
      return None
    with input_file.open() as f:
      return json.load(f)

  output_dir = pathlib.Path(output_dir)

  start = parse_date(start)
  stop = parse_date(stop)
  if stop < start:
    raise ValueError('stop must be on or after start')

  inventory_by_date = {}
  requested = 0
  data_range = _date_range(start, stop)
  s = '' if len(data_range) == 1 else 's'
  logger.info(f"Getting inventory on {len(data_range)} day{s} from {start:%Y-%m-%d} to {stop:%Y-%m-%d}")
  if update:
    logger.info("Updating inventory files, ignoring cached data")
  else:
    logger.info("Using cached inventory files if available")

  for date in data_range:

    # Print info when year changes
    if date.month == 1 and date.day == 1:
      logger.info(f"Getting inventory for all days in year {date.year}")

    date_str = date.strftime('%Y-%m-%d')
    logger.debug(f"Getting inventory for {date_str}")

    if not update:
      output_file = inventory_file_path(output_dir, date)
      inventory_data = read_inventory_file(output_dir, date)
      if inventory_data is not None:
        n_stations = len(inventory_data['stations']) if isinstance(inventory_data, dict) else 0
        logger.debug(f'  Cache hit: {path_relative_to_cwd(output_file)}: {n_stations} stations')
        if isinstance(inventory_data, dict):
          inventory_by_date[date_str] = inventory_data['stations']
        else:
          inventory_by_date[date_str] = []
        continue

    if requested > 0 and CONFIG['inventory']['delay'] > 0:
      time.sleep(CONFIG['inventory']['delay'])

    inventory_data = _get_inventory(date)
    requested += 1

    if isinstance(inventory_data, dict):
      inventory_by_date[date_str] = inventory_data.get('stations', [])
    else:
      inventory_by_date[date_str] = []

    output_file = write_inventory_file(output_dir, date, inventory_data)
    logger.debug(f'  {path_relative_to_cwd(output_file)}: {len(inventory_by_date[date_str])} stations')

  return inventory_by_date


def _get_inventory(start):

  from urllib.parse import urlencode
  from .util import get

  query = urlencode({
      'service': 'inventory',
      'start': start.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
      'interval': 1440,
      'fidelity': '60s',
    })
  url = f'{CONFIG['inventory']['base_url']}?{query}'

  response, error = get(url, timeout=CONFIG['inventory']['timeout'])

  if error is not None:
    logger.error(f"  Error fetching inventory for {start}: {error}")
    raise error

  return response


def _get_station_info(cafile=None):

  from .util import get
  from .config import config

  station_info_url = config('inventory')['station_info_url']
  station_info, error = get(station_info_url, format='json', cafile=cafile, timeout=CONFIG['inventory']['timeout'])

  # Convert list of station info to dictionary keyed by station ID
  station_info = {item['id']: item for item in station_info}
  for item in station_info.values():
    # Delete id key from station_info entries
    item.pop('id', None)
    # Rename geolat to glat to be consistent with what is used in data response columns.
    if 'geolat' in item:
      item['glat'] = item.pop('geolat')
    if 'geolon' in item:
      item['glon'] = item.pop('geolon')

  return station_info


def _print_summary(inventory):
  logger.info("Inventory summary")
  for entry in inventory:

    logger.info(f"{entry['id']}: ")
    logger.info(f"  startDate: {entry['startDate']}")
    logger.info(f"  stopDate:  {entry['stopDate']}")

    n_days = len(_date_range(entry['startDate'], entry['stopDate']))

    availability = entry.get('availability', {})
    unavailable = f"{len(availability.get('unavailable', []))}/{n_days}"
    unavailable += f" ({100-availability['available_percent']:.1f}%)"
    logger.info(f"  unavailable: {unavailable}")


    logger.info("  station:")
    if 'station' not in entry:
      logger.warning("  Warning: station information is missing")
      continue
    for key in entry['station']:
      logger.info(f"    {key}: {entry['station'][key]}")

    logger.info("  location:")
    if entry.get('location', None) is None:
      logger.warning("  Warning: location information is missing")
      continue
    geo_location_changed = entry.get('location', {}).get('geo_location_changed', None)
    if geo_location_changed is True:
      logger.warning("  Warning: geographic location changed")
    elif geo_location_changed is None:
      logger.warning("  Warning: could not determine if geographic location changed")

    for key in entry['location']:
      logger.info(f"    {key}: {entry['location'][key]}")


def _date_range(start, stop, format='datetime'):
  import datetime as dt

  if isinstance(start, str):
    start = dt.datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)
  if isinstance(stop, str):
    stop = dt.datetime.strptime(stop, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)

  dates = []
  current = start
  while current <= stop:
    if format == 'datetime':
      dates.append(current)
    if format == 'str':
      dates.append(current.strftime('%Y-%m-%d'))
    current += dt.timedelta(days=1)

  return dates


def _write_combined_files(inventory, output_dir, start, stop, station_id=None, partial_inventory=False):

  import pathlib
  from .util import write_json_and_archive

  output_dir = pathlib.Path(output_dir)

  output_dir.mkdir(parents=True, exist_ok=True)
  if station_id is None:
    if partial_inventory:
      inventory_file = output_dir / 'inventory' / 'partial' / f'inventory-{start}-{stop}.json'
      archive_path = None
    else:
      inventory_file = output_dir / 'inventory' / 'inventory.json'
      archive_path = output_dir / 'inventory' / 'archive'
  else:
    inventory_file = output_dir / 'inventory'/ 'partial' / f'inventory-{station_id}.json'
    archive_path = None

  write_json_and_archive(inventory, inventory_file, archive_path)


if __name__ == '__main__':
  from .cli import main_inventory
  main_inventory()
