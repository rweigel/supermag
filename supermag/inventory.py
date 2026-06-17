"""
For usage, see:
  supermag-inventory --help

Create combined inventory file using daily inventory from 1970-01-01 through tomorrow
  Re-fetch daily inventory files
    supermag-inventory --update-inventory
  Use cached inventory files when available
    supermag-inventory

Short tests:
  supermag-inventory --start 1970-01-01 --stop 1970-01-10
  supermag-inventory --start 1970-01-01 --stop 1970-01-10 --update-inventory
"""

from .util import configure_logging
logger = configure_logging(__name__)

from .config import config
CONFIG = config()


def inventory(start, stop,
              output_dir=CONFIG['common']['output_dir'],
              update_inventory=False,
              update_locations=False,
              station_id=None,
              partial_inventory=False,
              timeout=CONFIG['inventory']['timeout'],
              delay=CONFIG['inventory']['delay']):

  kwargs = {
    'output_dir': output_dir,
    'update': update_inventory,
    'timeout': timeout,
    'delay': delay
  }
  inventories = get_inventories(start, stop, **kwargs)

  requested_station_id = station_id # Save original for later

  station_availability = {}
  """
  station_availability = {
    station_id1: [available_date1, available_date2, ...],
    ...
  }
  """
  logger.info(f'Parsing {len(inventories)} inventories')
  for inventory_date, station_ids in inventories.items():
    s = '' if len(station_ids) == 1 else 's'
    logger.info(f'  Found {len(station_ids)} station{s} on {inventory_date}')
    for station_id in station_ids:
      if station_id not in station_availability:
        station_availability[station_id] = []
      station_availability[station_id].append(inventory_date)


  s = '' if len(station_availability) == 1 else 's'
  logger.info(f'Creating combined inventory with {len(station_availability)} stations')
  inventory = []
  for inventory_station_id, available_dates in station_availability.items():
    available_dates = sorted(available_dates)
    entry = {
        'id': inventory_station_id,
        'startDate': available_dates[0],
        'stopDate': available_dates[-1],
        'available_percent': 100.0
      }

    all_dates = _date_range(available_dates[0], available_dates[-1], format='str')
    n_days = len(all_dates)
    if len(all_dates) != len(available_dates):
      entry['available'] = available_dates
      entry['available_percent'] = 100 * len(available_dates) / len(all_dates)
      entry['unavailable'] = sorted(set(all_dates) - set(available_dates))

    inventory.append(entry)

  if requested_station_id is not None:
    inventory = [entry for entry in inventory if entry['id'] == requested_station_id]
    if not inventory:
      raise ValueError(f"Station ID not found in combined inventory: {requested_station_id}")
    logger.info(f'Filtered inventory to station {requested_station_id}')


  logger.info("Getting geographic locations for each station")
  kwargs = {
    'start': start,
    'stop': stop,
    'station_id': requested_station_id,
    'partial_inventory': partial_inventory,
    'update': update_locations
  }
  geo_locations = _get_locations(inventory, output_dir, **kwargs)


  logger.info("Adding geographic locations to inventory entries")
  for entry in inventory:
    if entry['id'] in geo_locations:
      location = geo_locations[entry['id']]
      entry['location'] = location


  logger.info("Inventory summary")
  for entry in inventory:
    logger.info(f"{entry['id']}: ")
    logger.info(f"  startDate: {entry['startDate']}")
    logger.info(f"  stopDate:  {entry['stopDate']}")
    logger.info(f"  Unavailable: {len(entry.get('unavailable', []))}/{n_days} ({100-entry['available_percent']:.1f}%)")
    logger.info(f"  Geographic location changed: {entry.get('location', {}).get('geo_location_changed', None)}")
    for date_key in ['start', 'stop']:
      if entry.get('location', {}).get(date_key, {}).get('error'):
        msg = f"{date_key}Date: {entry['location'][date_key]['error']}"
        logger.info(f"  Error fetching geographic location on {msg}")
      elif entry.get('location', {}).get(date_key):
        glat = entry['location'][date_key]['glat']
        glon = entry['location'][date_key]['glon']
        logger.info(f"  Geographic location on {date_key}Date (lat, lon): ({glat}°, {glon}°)")


  kwargs = {
    'start': start,
    'stop': stop,
    'station_id': requested_station_id,
    'partial_inventory': partial_inventory
  }
  _write_files(inventory, output_dir, **kwargs)

  return inventory


def get_inventories(start, stop, output_dir=CONFIG['common']['output_dir'], update=False, timeout=CONFIG['inventory']['timeout'], delay=CONFIG['inventory']['delay']):

  import time
  from .util import path_relative_to_cwd

  def parse_date(value):
    import datetime as dt
    return dt.datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)

  def inventory_file_path(output_dir, start):
    return output_dir / f"{start:%Y-%m-%d}.json"

  def write_inventory_file(output_dir, start, payload):
    import json
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = inventory_file_path(output_dir, start)
    output_file.write_text(json.dumps(payload, indent=2) + '\n')
    return output_file

  start = parse_date(start)
  stop = parse_date(stop)
  if stop < start:
    raise ValueError('stop must be on or after start')

  inventory_dir = output_dir / "daily"

  inventory_data = {}
  requested = 0
  for current in _date_range(start, stop):

    file_date = current.strftime('%Y-%m-%d')
    logger.info(f"Getting inventory for {file_date}")

    output_file = inventory_file_path(inventory_dir, current)
    if output_file.exists():
      if not update:
        logger.info(f'  Found cache: {path_relative_to_cwd(output_file)}')
        with output_file.open() as stream:
          import json
          payload = json.load(stream)
        inventory_data[file_date] = payload['stations'] if isinstance(payload, dict) else []
        continue
      else:
        logger.info(f'  Updating existing: {path_relative_to_cwd(output_file)}')

    if requested > 0 and delay > 0:
      time.sleep(delay)

    payload = _get_inventory(current, timeout=timeout)
    requested += 1
    stations = payload.get('stations', []) if isinstance(payload, dict) else []
    output_file = write_inventory_file(inventory_dir, current, payload)
    logger.info(f'  {path_relative_to_cwd(output_file)}: {len(stations)} stations')
    inventory_data[file_date] = payload['stations'] if isinstance(payload, dict) else []

  return inventory_data


def _get_inventory(start, timeout=CONFIG['inventory']['timeout']):

  from urllib.parse import urlencode
  from .util import get

  query = urlencode({
      'service': 'inventory',
      'start': start.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
      'interval': 1440,
      'fidelity': '60s',
    })
  url = f'{CONFIG['inventory']['base_url']}?{query}'

  logger.debug(f"  Fetching {url}")
  response, error = get(url, timeout=timeout)

  if error is not None:
    logger.error(f"  Error fetching inventory for {start}: {error}")
    raise error

  return response


def _write_files(inventory, output_dir, start, stop, station_id=None, partial_inventory=False):

  import json
  import gzip
  import datetime as dt

  from .util import path_relative_to_cwd

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


if __name__ == '__main__':
  from .cli import main_inventory
  main_inventory()
