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
              update_locations=False, # Whether to update location details
              include_locations=True, # Whether to include location details
              station_id=None,
              cafile=None):
  """
  Fetch daily SuperMAG inventories and build station-level inventory records.

  Additional information includes the station name, start and stop dates,
  geographic latitude and longitude, station operator, percentage of days with
  data, and lists of days when data are available.

  Note that the returned inventory differs in structure from the inventory API,
  which returns a only list of station ids given a start and stop date.
  ----

  Returns a dict with a key 'stations' containing a list where each item contains
  a station id, start/stop dates, and additional information.

  If `include_locations` is `True`, location details beyond geographic location
  are added to each station's information. The details include the stations
  reported location on the start and stop dates, which are determined from the
  glat and glong parameters from a request for data on these dates. This is
  useful for determining of the station location changed significantly.

  Also, `include_locations=True` will result in the start and stop dates being
  updated if no data are returned or the request fails.
  """

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


  from .util import path_relative_to_cwd
  logger.info(f"Output directory: {path_relative_to_cwd(output_dir)}")


  kwargs = {
    'output_dir': output_dir,
    'update': update_inventory
  }
  inventory_by_day = get_inventories(start, stop, **kwargs)

  inventory_by_station = {}
  logger.info(f'Converting {len(inventory_by_day)} by-day inventory to by-id inventories')
  for inventory_date, station_ids in inventory_by_day.items():
    for sid in station_ids:
      if sid not in inventory_by_station:
        inventory_by_station[sid] = []
      inventory_by_station[sid].append(inventory_date)

  logger.info(f"  {len(inventory_by_station)} stations in requested date range")

  logger.info("Restructuring inventory information")
  inventory_by_station = _restructure_inventory(inventory_by_station)

  _add_station_info(inventory_by_station, cafile=cafile)

  # Filter inventory by station id if specified
  if station_id is not None:
    inventory_by_station = [entry for entry in inventory_by_station if entry['id'] == station_id]
    if not inventory_by_station:
      logger.info(f"{station_id} not found in inventory from {start} through {stop}")
      return []
    logger.info(f'Filtered inventory to station {station_id}')

  if include_locations:
    kwargs = {
      'station_id': station_id,
      'output_dir': output_dir,
      'update_locations': update_locations,
      'cafile': cafile
    }
    _add_sample_details(userid, inventory_by_station, **kwargs)

  _print_summary(inventory_by_station)

  kwargs = {
    'start': start,
    'stop': stop,
    'station_id': station_id,
    'partial_inventory': partial_inventory
  }
  from .util import write_files
  write_files(inventory_by_station, output_dir, **kwargs)

  return inventory_by_station


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
    return output_dir / "inventory" / "cache" / f"{start:%Y-%m-%d}.json"

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
  logger.info(f"Preparing inventory on {len(data_range)} day{s} from {start:%Y-%m-%d} to {stop:%Y-%m-%d}")
  if update:
    logger.info("  Updating inventory files, ignoring cached data")
  else:
    logger.info("  Using cached inventory files if available")

  for date in data_range:

    # Print info when year changes
    if date.month == 1 and date.day == 1:
      logger.info(f"Preparing inventory for days in year {date.year}")

    date_str = date.strftime('%Y-%m-%d')
    logger.debug(f"Preparing inventory for {date_str}")

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

  response, error = get(url,
                        retry=CONFIG['inventory']['retry'],
                        timeout=CONFIG['inventory']['timeout'])

  if error is not None:
    logger.error(f"  Error fetching inventory for {start}: {error}")
    raise error

  return response


def _restructure_inventory(inventory):
  """Restructure inventory_by_station"""

  station_days = 0
  s = '' if len(inventory) == 1 else 's'
  logger.info(f'  Adding {{start,stop}}Date and availability info to {len(inventory)} station{s}')
  inventory_r = []
  for station_id, available_dates in inventory.items():
    available_dates = sorted(available_dates)
    entry = {
        'id': station_id,
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
      station_days += len(available_dates)
    else:
      station_days += len(available_dates)

    inventory_r.append(entry)

  logger.info(f"Total station-days: {station_days} ({station_days} x 200KB/day = {station_days * 100_000/1e9} GB)")

  return inventory_r


def _add_station_info(inventory, cafile=None):
  logger.info("Getting all station info")
  station_info, station_info_error = _get_station_info(cafile=cafile)
  if station_info_error is not None:
    logger.warning(f"  Failed to fetch station info: {station_info_error}")
    station_info = {}
    return

  logger.info(f"  Station info has {len(station_info)} stations")
  logger.info("Adding station info to inventory entries")
  for entry in inventory:
    if entry['id'] in station_info:
      entry['station'] = station_info[entry['id']]


def _get_station_info(cafile=None):

  from .util import get
  from .config import config

  station_info_url = config('inventory')['station_info_url']
  kwargs = {
     'format': 'json',
     'cafile': cafile,
      'retry': CONFIG['inventory']['retry'],
     'timeout': CONFIG['inventory']['timeout']
  }
  station_info, error = get(station_info_url, **kwargs)
  if error is not None:
    return {}, error

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

  return station_info, None


def _add_sample_details(userid, inventory,
                        station_id=None,
                        output_dir=None,
                        update_locations=False,
                        cafile=None):

  from .samples import samples

  msgo = "geographic locations for each station on start and stop dates"
  if update_locations:
    logger.info(f"Getting {msgo} (refetching cached data)")
  else:
    logger.info(f"Getting {msgo} (using cached data, if available)")

  kwargs = {
    'output_dir': output_dir,
    'update': update_locations,
    'station_id': station_id,
    'inventory': inventory,
    'cafile': cafile
  }

  location_details = samples(userid, **kwargs)

  logger.info(f"Adding {msgo} to inventory entries")
  for entry in inventory:
    if entry['id'] in location_details:
      sample_details = location_details[entry['id']]
      entry['location'] = sample_details['location']
      entry['sample'] = sample_details['sample']


def _print_summary(inventory):

  def _sample_record_get(location_record, which):
    if not isinstance(location_record, dict):
      return {}

    if which == 'first':
      return location_record.get('firstRecord', {})

    if which == 'last':
      return location_record.get('lastRecord', {})

    raise ValueError(f"Invalid which value: {which}. Must be 'first' or 'last'.")

  def _locations_differ(location_record, threshold=None):

    from .util import has_location

    start_location = _sample_record_get(location_record, 'first')
    stop_location = _sample_record_get(location_record, 'last')

    if not has_location(start_location) or not has_location(stop_location):
      return None

    if threshold is None:
      return (
        start_location.get('glat') != stop_location.get('glat')
        or
        start_location.get('glon') != stop_location.get('glon')
      )
    else:
      # If locations match within threshold degrees, count as match
      lat_adiff = abs(start_location.get('glat') - stop_location.get('glat'))
      lon_adiff = abs(start_location.get('glon') - stop_location.get('glon'))
      return lat_adiff > threshold or lon_adiff > threshold


  logger.info("Inventory summary:")
  for entry in inventory:

    logger.info(f"{entry['id']}: ")
    logger.info("  From inventory requests (and start/stop date updates from location requests):")
    for key in ['start', 'stop']:
      msgo = f"    {key}Date: {entry[f'{key}Date']}"
      if f'{key}DateExpected' in entry:
        logger.info(f"{msgo} (updated); Expected: {entry[f'{key}DateExpected']}")
      else:
        logger.info(msgo)


    availability = entry.get('availability', {})
    n_days = len(_date_range(entry['startDate'], entry['stopDate']))
    available = f"{len(availability.get('available', []))}/{n_days}"
    available += f" ({availability['available_percent']:.1f}%)"
    logger.info(f"    Percentage of days available: {available}")


    logger.info("  From station information request:")
    if 'station' not in entry:
      logger.warning("    Warning: station information is missing")
      continue
    for key in entry['station']:
      logger.info(f"    {key}: {entry['station'][key]}")


    if 'sample' in entry or 'location' in entry:
      threshold = 0.0001 # degrees
      logger.info("  From data requests:")
      sample_entry = entry.get('location', entry.get('sample', {}))
      for key in sample_entry:
        logger.info(f"    {key}: {sample_entry[key]}")
      if _locations_differ(sample_entry, threshold=threshold):
        logger.warning(f"    Location has changed by more than {threshold}° (~10 meters) between start and stop dates")


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
