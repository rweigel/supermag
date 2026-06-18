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
              station_id=None,
              timeout=CONFIG['inventory']['timeout'],
              delay=CONFIG['inventory']['delay']):

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
    'update': update_inventory,
    'timeout': timeout,
    'delay': delay
  }
  inventories = get_inventories(start, stop, **kwargs)

  station_availability = {}
  logger.info(f'Parsing {len(inventories)} inventories')
  for inventory_date, station_ids in inventories.items():
    s = '' if len(station_ids) == 1 else 's'
    logger.debug(f'  Found {len(station_ids)} station{s} on {inventory_date}')
    for sid in station_ids:
      if sid not in station_availability:
        station_availability[sid] = []
      station_availability[sid].append(inventory_date)


  s = '' if len(station_availability) == 1 else 's'
  logger.info(f'Creating combined inventory with {len(station_availability)} station{s}')
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

  if station_id is not None:
    inventory = [entry for entry in inventory if entry['id'] == station_id]
    if not inventory:
      logger.info(f"{station_id} not found in inventory from {start} through {stop}")
      return []
      #raise ValueError(f"Station ID not found in combined inventory: {station_id}")
    logger.info(f'Filtered inventory to station {station_id}')


  logger.info("Getting geographic locations for each station")
  from .locations import locations
  geo_locations = locations(userid,
                            output_dir=output_dir,
                            update=update_locations,
                            station_id=station_id,
                            inventory=inventory)

  logger.info("Adding geographic locations to inventory entries")

  logger.info("Inventory summary")
  for entry in inventory:
    if entry['id'] in geo_locations:
      entry['location'] = geo_locations[entry['id']]
    logger.info(f"{entry['id']}: ")
    logger.info(f"  startDate: {entry['startDate']}")
    logger.info(f"  stopDate:  {entry['stopDate']}")
    logger.info(f"  Unavailable: {len(entry.get('unavailable', []))}/{n_days} ({100-entry['available_percent']:.1f}%)")

    geo_location_changed = entry.get('location', {}).get('geo_location_changed', None)
    if entry.get('location', None) is None:
      logger.warning("  Warning: location information is missing")
    elif geo_location_changed is False:
      logger.warning("  Warning: geographic location changed")
    elif geo_location_changed is None:
      logger.warning("  Warning: could not determine if geographic location changed")
    logger.info(f"  Start location: {entry['location']['start']}")
    logger.info(f"  Stop location:  {entry['location']['stop']}")


  kwargs = {
    'start': start,
    'stop': stop,
    'station_id': station_id,
    'partial_inventory': partial_inventory
  }

  _write_files(inventory, output_dir, **kwargs)

  return inventory


def get_inventories(start, stop, output_dir=CONFIG['common']['output_dir'], update=False, timeout=CONFIG['inventory']['timeout'], delay=CONFIG['inventory']['delay']):

  import time
  import pathlib

  from .util import path_relative_to_cwd

  output_dir = pathlib.Path(output_dir)

  def parse_date(value):
    import datetime as dt
    return dt.datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)

  def inventory_file_path(output_dir, start):
    return output_dir / "inventory" / "daily" / f"{start:%Y-%m-%d}.json"

  def write_inventory_file(output_dir, start, payload):
    import json
    output_file = inventory_file_path(output_dir, start)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2) + '\n')
    return output_file

  start = parse_date(start)
  stop = parse_date(stop)
  if stop < start:
    raise ValueError('stop must be on or after start')

  inventory_data = {}
  requested = 0
  data_range = _date_range(start, stop)
  s = '' if len(data_range) == 1 else 's'
  logger.info(f"Getting inventory on {len(data_range)} day{s} from {start:%Y-%m-%d} to {stop:%Y-%m-%d}")
  for current in data_range:

    file_date = current.strftime('%Y-%m-%d')
    logger.debug(f"Getting inventory for {file_date}")

    output_file = inventory_file_path(output_dir, current)

    if output_file.exists():
      if not update:
        logger.debug(f'  Found cache: {path_relative_to_cwd(output_file)}')
        with output_file.open() as stream:
          import json
          payload = json.load(stream)
        inventory_data[file_date] = payload['stations'] if isinstance(payload, dict) else []
        continue
      else:
        logger.debug(f'  Updating existing: {path_relative_to_cwd(output_file)}')

    if requested > 0 and delay > 0:
      time.sleep(delay)

    payload = _get_inventory(current, timeout=timeout)
    requested += 1
    stations = payload.get('stations', []) if isinstance(payload, dict) else []
    output_file = write_inventory_file(output_dir, current, payload)
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
