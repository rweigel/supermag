"""
Usage:
  supermag-samples --help
"""

from os import stat

from .util import path_relative_to_cwd, logger
from .config import config

CONFIG = config()

def samples(userid,
            output_dir=CONFIG['common']['output_dir'],
            update=False,
            station_id=None,
            inventory=None,
            cafile=None):
  """Reads inventory file and fetches station data samples.

  Fetches data on each station's first and last available day to get geographic
  latitude and longitude, writes results to samples.json, and updates inventory
  start/stop dates if no data is returned at those endpoints by searching forward
  from start and backward from stop.
  """

  import pathlib
  output_dir = pathlib.Path(output_dir)

  partial = station_id is not None
  if partial:
    from .util import _partial_output_stem
    stem = _partial_output_stem(file_type='samples', station_id=station_id, partial=True)
    samples_file = output_dir / 'inventory' / 'partial' / f'{stem}.json'
  else:
    samples_file = output_dir / 'inventory' / 'samples.json'

  if inventory is None:
    inventory = _read_inventory(output_dir, station_id=station_id)

  samples_data = _fetch_samples(userid, inventory, update, cafile=cafile)

  _write_samples(samples_data, samples_file)

  if station_id is None:
    return samples_data
  else:
    return {station_id: samples_data.get(station_id, None)}


def _fetch_samples(userid, inventory, update=False, cafile=None):

  from .util import tval2iso

  samples = {}
  for entry in inventory:
    station_id = entry['id']

    start_isodate = f"{entry['startDate']}"
    stop_isodate = f"{entry['stopDate']}"

    args = [userid, station_id, start_isodate, entry, "first", update, cafile]
    first_record, first_url, first_error = _fetch_sample(*args)

    first_timestamp = tval2iso(first_record.get('tval', None))
    first_location = _location_info(first_record)

    args = [userid, station_id, stop_isodate, entry, "last", update, cafile]
    last_record, last_url, last_error = _fetch_sample(*args)

    last_timestamp = tval2iso(last_record.get('tval', None))
    last_location = _location_info(last_record)

    sample_info = {
        'description': 'First and last records for all parameters from data request on start and stop days.',
        'startDate': {'reported': start_isodate},
        'stopDate': {'reported': stop_isodate},
        'firstRecord': {
          'timestamp': first_timestamp,
          'url': first_url,
          'location': first_location,
          'data': first_record,
        },
        'lastRecord': {
          'timestamp': last_timestamp,
          'url': last_url,
          'location': last_location,
          'data': last_record
        }
      }

    if first_error is not None:
      sample_info['firstRecord']['error'] = first_error
    if last_error is not None:
      sample_info['lastRecord']['error'] = last_error

    for day, record_key in [('startDate', 'firstRecord'), ('stopDate',  'lastRecord')]:
      timestamp = sample_info[record_key]['timestamp']
      if timestamp is None:
        sample_info[day]['found'] = None
        sample_info[day][''] = True
      else:
        sample_info[day]['found'] = timestamp[0:10]
        if timestamp[0:10] != sample_info[day]['reported']:
          sample_info[day]['error'] = True

    samples[station_id] = sample_info

    _print_summary(station_id, sample_info)

  return samples


def _fetch_sample(userid,
                  station_id,
                  isodate,
                  entry,
                  value='first',
                  update=False,
                  cafile=None,
                  allow_retry=True):

  from .data import data, data_url

  logger.debug("")
  logger.debug(f"Fetching location for station {station_id} on {isodate}")
  extent = 60*60*24  # 1 day

  # update=True means refresh from source, so do not read from cache.
  args = [userid, station_id, isodate, extent]
  kwargs = {
    "delta": "none",
    "baseline": "none"
  }
  url = data_url(*args, **kwargs)
  data, error = data(*args, **kwargs, use_cache=not update, cafile=cafile)

  if allow_retry and (error is not None or len(data) == 0):
    msg = "No data returned for {station_id} on {which} date obtained from inventory requests."
    logger.error(msg.format(station_id=station_id, which=value))
    return _fetch_sample_retry(userid, station_id, isodate, entry, value, update, cafile)

  if error is not None:
    emsg = f"Failed to fetch data for station {station_id} on {isodate}: {error}"
    logger.error(emsg)
    return {}, url, emsg

  if not isinstance(data, list) or len(data) == 0:
    emsg = f"No data returned for station {station_id} on {isodate}"
    logger.error(emsg)
    return {}, url, emsg

  if value == "first":
    record = data[0]
  elif value == "last":
    record = data[-1]
  else:
    raise ValueError(f"Invalid value parameter: {value}. Must be 'first' or 'last'.")

  return record, url, None


def _fetch_sample_retry(userid, station_id, isodate, entry, value, update, cafile):
  """Try alternative days when the primary date returns no data."""
  from datetime import datetime, timedelta

  # Could do binary search to reduce number of attempts, but for now try and
  # will report issue to SuperMAG.
  n_try = 7
  if value == 'first':
    day_offsets = range(1, n_try + 1)
  else:
    day_offsets = range(-1, -n_try - 1, -1)

  error = None
  isodate_new = isodate
  for day_offset in day_offsets:

    date_new = datetime.strptime(isodate, "%Y-%m-%d")
    date_new = date_new + timedelta(days=day_offset)
    isodate_new = date_new.strftime("%Y-%m-%d")

    logger.debug(f"Trying {isodate_new}")

    args = [userid, station_id, isodate_new, entry, value, update, cafile]
    sample, url, error = _fetch_sample(*args, allow_retry=False)

    if error is None and sample is not None:
      logger.debug(f"    Found data on {isodate_new}")
      break

  if error is not None or sample is None:
    logger.error(f"  Failed find data after trying {n_try} days.")
    if value == 'first':
      msg = "after reported start day"
    else:
      msg = "before reported stop day"
    error = f"Failed find data after trying {n_try} days {msg}"

  return sample, url, error


def _location_info(sample):
  if len(sample) == 0:
    return {
      'glon': None,
      'glat': None
    }

  return {
    'glon': sample.get('glon', None),
    'glat': sample.get('glat', None)
  }


def _print_summary(station_id, sample):
  logger.info(f"{station_id} summary:")
  for prefix in ['first', 'last']:
    logger.info(f"  {prefix} record")
    logger.info(f"     timestamp: {sample[f"{prefix}Record"]['timestamp']}")
    logger.info(f"     location:  {sample[f"{prefix}Record"]['location']}")
    logger.info(f"     data:      {sample[f"{prefix}Record"]['data']}")


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
