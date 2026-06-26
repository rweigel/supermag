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
              update_samples=False, # Whether to update sample information
              include_samples=True, # Whether to include sample information
              station_id=None,
              cafile=None):
  """
  Fetch daily SuperMAG inventories and build station-level inventory records.

  Additional information includes the station name, start and stop dates,
  geographic latitude and longitude, station operator, percentage of days with
  data, and lists of days when data are available. By default, start = 1970-01-01
  and stop is tomorrow's date UTC.

  start and stop are interpreted as inclusive (an inventory will be returned on
  both dates).

  Note that the returned inventory differs in structure from the inventory API,
  which returns a only list of station ids with data available in given a start
  and stop date range.
  ----

  Returns a dict with a key 'stations' containing a list where each item contains
  a station id, start/stop dates, and additional information. Both start and
  stop are inclusive.

  If `include_samples` is `True`, location details beyond geographic location
  are added to each station's information. The details include a sample of data
  and the station's reported location on the start and stop dates, which are
  determined from the glat and glon parameters from a request for data on these
  dates. This is useful for determining of the station location changed
  significantly.

  Also, `include_samples=True` will result in the start and stop dates being
  updated if no data are returned or the request fails.
  """

  from .util import write_files

  import pathlib
  output_dir = pathlib.Path(output_dir)

  from .util import data_range
  start_data, stop_data = data_range()
  if start is None:
    start = start_data
  if stop is None:
    stop = stop_data

  start = start[0:10]
  stop = stop[0:10]

  from .util import parse_timestamp
  start_dt = parse_timestamp(start)
  stop_dt = parse_timestamp(stop)
  if stop_dt <= start_dt:
    msg = f"Stop time must be after start time. Got start={start}, stop={stop}"
    raise ValueError(msg)

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
  msg = f'Converting {len(inventory_by_day)} by-day inventory to by-id inventories'
  logger.info(msg)
  for inventory_date, station_ids in inventory_by_day.items():
    for sid in station_ids:
      if sid not in inventory_by_station:
        inventory_by_station[sid] = []
      inventory_by_station[sid].append(inventory_date)

  logger.info(f"  {len(inventory_by_station)} stations in requested date range")

  logger.info("Restructuring inventory information")
  inventory_by_station = _restructure_inventory(inventory_by_station)

  if not partial_inventory and station_id is None:
    info, url, missing = _add_station_info(inventory_by_station, cafile=cafile)
    if len(missing) != 0:
      msg = f'{len(missing)} station(s) in station list not '
      msg += f'found in inventory: {missing}'
      logger.error(msg)
    kwargs = {
      'start': start,
      'stop': stop,
      'station_id': station_id,
      'partial_inventory': False,
      'file_type': 'stations',
      'url': url
    }
    write_files(info, output_dir, **kwargs)


  # Filter inventory by station id if specified
  if station_id is not None:
    inventory_by_station = [entry for entry in inventory_by_station if entry['id'] == station_id]
    if not inventory_by_station:
      logger.info(f"{station_id} not found in inventory from {start} through {stop}")
      return []
    logger.info(f'Filtered inventory to station {station_id}')


  if include_samples:
    kwargs = {
      'station_id': station_id,
      'output_dir': output_dir,
      'update_samples': update_samples,
      'cafile': cafile
    }
    _add_sample_details(userid, inventory_by_station, **kwargs)
    _add_location_issues(inventory_by_station)


  _print_summary(inventory_by_station)


  kwargs = {
    'start': start,
    'stop': stop,
    'station_id': station_id,
    'partial_inventory': partial_inventory,
    'file_type': 'inventory'
  }
  write_files(inventory_by_station, output_dir, **kwargs)

  return inventory_by_station


def get_inventories(start, stop, output_dir=CONFIG['common']['output_dir'], update=False):
  """Get inventories for a date range, using cached files if available if update is False."""

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
  """Get inventory from SuperMAG API on a specific start date."""

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
  """Restructure inventory by-station"""

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
        'availability': {
          'available_percent': 100.0
        }
      }

    all_dates = _date_range(available_dates[0], available_dates[-1], format='str')
    if len(all_dates) != len(available_dates):
      unavailable_dates = sorted(set(all_dates) - set(available_dates))
      available_percent = 100 * len(available_dates) / len(all_dates)

      entry['availability']['available_percent'] = round(available_percent, 2)
      entry['availability']['available_number'] = len(available_dates)
      #entry['availability']['available'] = available_dates

      entry['availability']['unavailable_number'] = len(unavailable_dates)
      #entry['availability']['unavailable'] = unavailable_dates

      station_days += len(available_dates)
    else:
      station_days += len(available_dates)

    inventory_r.append(entry)

  logger.info(f"Total station-days: {station_days} ({station_days} x 200KB/day = {station_days * 100_000/1e9} GB)")

  return inventory_r


def _add_station_info(inventory, cafile=None):
  """Add station info returned by _get_station_info to inventory entries."""

  from .config import config

  url = config('inventory')['station_info_url']

  logger.info("Getting all station info")
  info, info_error = _get_station_info(url, cafile=cafile)
  if info_error is not None:
    logger.warning(f"  Failed to fetch station info: {info_error}")
    info = {}
    return

  logger.info(f"  Station info has {len(info)} stations")
  logger.info("Adding station info to inventory entries")
  for entry in inventory:
    if entry['id'] in info:
      entry['station'] = info[entry['id']]
    else:
      entry['stationError'] = f"Station not found in {url}"

  missing_inventory = []
  inventory_ids = [entry['id'] for entry in inventory]
  for station_id in info:
    if station_id not in inventory_ids:
      missing_inventory.append(station_id)

  return info, url, missing_inventory


def _get_station_info(url, cafile=None):
  """Fetch station info from the SuperMAG API."""

  from .util import get

  kwargs = {
      'format': 'json',
      'cafile': cafile,
      'retry': CONFIG['inventory']['retry'],
      'timeout': CONFIG['inventory']['timeout']
  }
  station_info, error = get(url, **kwargs)
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


def _add_location_issues(inventory_by_station):

  def precision(number):
    # Strip trailing zeros
    num_str = str(number).rstrip('0')
    if '.' in num_str:
      return len(num_str.split('.')[1])
    return 0  # Whole number

  def add_issues(sample):

    locationInformation = {
      'firstRecordMatchesReported': True,
      'firstRecordMatchesLast': True,
    }

    if 'sample' not in entry:
      msg = "No sample information in inventory. Cannot check locations."
      logger.error(msg)
      raise ValueError(msg)

    station_info = entry.get("station", None)

    if station_info is not None:
      reported = [station_info.get('glat', None), station_info.get('glon', None)]
    else:
      reported = [None, None]
    locationInformation['reported'] = reported

    sample = entry["sample"]
    for where in ['firstRecord', 'lastRecord']:
      record_val = sample.get("firstRecord", None)
      if record_val is not None:
        record_loc = [record_val['data'].get('glat', None), record_val['data'].get('glon', None)]
      else:
        record_loc = [None, None]
      locationInformation[where] = record_loc

    if locationInformation['firstRecord'] != locationInformation['lastRecord']:
      locationInformation['firstRecordMatchesLast'] = False

    if locationInformation['firstRecord'] != locationInformation['reported']:
      locationInformation['firstRecordMatchesReported'] = False
      # glat
      if locationInformation['firstRecord'][0] is not None and locationInformation['reported'][0] is not None:
        reported_precision = precision(locationInformation['reported'][0])
        if round(locationInformation['firstRecord'][0], reported_precision) == locationInformation['reported'][0]:
          locationInformation['firstRecordMatchesReported'] = True
       # glon
      if locationInformation['firstRecord'][1] is not None and locationInformation['reported'][1] is not None:
        reported_precision = precision(locationInformation['reported'][0])
        if round(locationInformation['firstRecord'][1], reported_precision) == locationInformation['reported'][0]:
          locationInformation['firstRecordMatchesReported'] = True

    ok = (locationInformation['firstRecordMatchesReported'],
          locationInformation['firstRecordMatchesLast'])

    if not all(ok):
      locationInformation["comment"] = "First record compared to reported by rounding first record to precision of reported. First record compared to last using exact match."
      entry["locationError"] = locationInformation


  for entry in inventory_by_station:
    try:
      add_issues(entry)
    except Exception as e:
      entry['locationError'] = {'error': f"Error when attempting to check location: {e}"}


def _add_sample_details(userid,
                        inventory,
                        station_id=None,
                        output_dir=None,
                        update_samples=False,
                        cafile=None):
  """Add sample details to inventory entries."""

  from .samples import samples

  msgo = "sample data and geographic locations for each station on start and stop dates"
  if update_samples:
    logger.info(f"Getting {msgo} (refetching cached data)")
  else:
    logger.info(f"Getting {msgo} (using cached data, if available)")

  kwargs = {
    'output_dir': output_dir,
    'update': update_samples,
    'station_id': station_id,
    'inventory': inventory,
    'cafile': cafile
  }

  _samples = samples(userid, **kwargs)

  logger.info(f"Adding {msgo} to inventory entries")
  for entry in inventory:
    if entry['id'] in _samples:
      entry['sample'] = _samples[entry['id']]


def _print_summary(inventory):
  """Print a summary of the inventory entries."""

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
    available_percent = availability.get("available_percent", "N/A")
    logger.info(f"    Percentage of days available: {available_percent}")


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
  """Return a list of dates between start and stop dates, inclusive."""
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
