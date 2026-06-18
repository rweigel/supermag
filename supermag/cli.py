from .util import logger, check_userid

from .config import config
CONFIG = config()


def parse_data_args():
  import pathlib
  import textwrap
  import argparse

  default_cache_dir = CONFIG['common']['output_dir']

  # If these defaults changed, will need to update tests.
  default_station = 'ABK'
  default_start = '2001-01-01T00:00Z'
  default_stop  = '2001-01-01T00:01Z'

  epilog = """
  Examples:
    supermag-data --userid USERID
    supermag-data --dataset indices --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z --userid USERID
    supermag-data --dataset ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z --userid USERID
    supermag-data --dataset ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z --userid USERID
  """
  # Remove leading spaces from epilog
  epilog = textwrap.dedent(epilog)

  parser = argparse.ArgumentParser(
    description='Fetch SuperMAG station data via data().',
    epilog=epilog,
    formatter_class=argparse.RawDescriptionHelpFormatter
  )
  parser.add_argument(
    '--dataset',
    default=default_station,
    help=f'"indices" or magnetometer IAGA ID (e.g., BOU). Default: {default_station}.',
  )
  _add_userid_arg(parser)
  _add_start_arg(parser, default_start)
  _add_stop_arg(parser, default_stop)
  parser.add_argument(
    '--delta',
    default='none',
    choices=['start', 'none'],
    help='Delta parameter for the SuperMAG API. Default: default.',
  )
  parser.add_argument(
    '--baseline',
    default='none',
    choices=['all', 'yearly', 'none'],
    help='Baseline parameter for the SuperMAG API. Default: yearly.',
  )
  parser.add_argument(
    '--format',
    default='json',
    choices=['json', 'csv', 'list', 'dataframe'],
    help='Output format. Default: json.',
  )
  parser.add_argument(
    '--no-cache',
    action='store_true',
    help='Do not write or read cache.'
  )
  parser.add_argument(
    '--ignore-cache',
    action='store_true',
    help='Re-fetch data even if a cache file exists.'
  )
  parser.add_argument(
    '--cache-dir',
    default=default_cache_dir,
    type=pathlib.Path,
    help=f'Base directory for cache storage. Default: {default_cache_dir}.'
  )
  _add_cafile_arg(parser)
  _add_debug_arg(parser)
  _add_output_dir_arg(parser, CONFIG['common']['output_dir'])
  parser.add_argument(
    '--output-file',
    default=None,
    type=pathlib.Path,
    help='Path to write output. If not given, writes to supermag-{station}-{start}-{stop}-{baseline}-{delta}.{format}'
  )

  args = parser.parse_args()

  check_userid(args.userid)

  # Normalize times to HH:MMZ
  args.start = args.start[:16] + 'Z'
  args.stop  = args.stop[:16]  + 'Z'

  # Compute extent in seconds from start/stop
  from datetime import datetime, timezone
  fmt = '%Y-%m-%dT%H:%MZ'
  start_dt = datetime.strptime(args.start, fmt).replace(tzinfo=timezone.utc)
  stop_dt  = datetime.strptime(args.stop,  fmt).replace(tzinfo=timezone.utc)
  if stop_dt <= start_dt:
    raise ValueError('--stop must be after --start')
  args.extent = int((stop_dt - start_dt).total_seconds())

  args.cache = not args.no_cache

  if isinstance(args.cafile, str):
    if args.cafile.lower() == 'none':
      args.cafile = None
    elif args.cafile.lower() == 'default':
      args.cafile = 'default'

  return args


def parse_inventory_args():
  import textwrap
  import argparse

  from .util import data_range
  default_start, default_stop = data_range()

  epilog = """
  Examples:
    Full run:
      supermag-inventory --userid USERID
    Short tests:
      supermag-inventory --start 1970-01-01 --stop 1970-01-10 --userid USERID
      supermag-inventory --start 1970-01-01 --stop 1970-01-10 --update-inventory --userid USERID
      supermag-inventory --start 1970-01-01 --stop 1970-01-10 --update-inventory --update-locations --userid USERID
  """
  epilog = textwrap.dedent(epilog)

  description = """
  Fetch daily SuperMAG inventories from 1970-01-01 through tomorrow (UTC) and create inventory.json file with list of available dates for each station.

  If --station-id, --start, or --stop is given, output is written to OUTPUT_DIR/partial
  """
  description = textwrap.dedent(description)

  parser = argparse.ArgumentParser(
    description=description,
    epilog=epilog,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )

  _add_userid_arg(parser)
  _add_start_arg(parser, default_start)
  _add_stop_arg(parser, default_stop)
  _add_output_dir_arg(parser, CONFIG['common']['output_dir'])
  _add_station_id_arg(parser)
  parser.add_argument(
    '--update-inventory',
    action='store_true',
    help='Refetch and overwrite existing daily inventory files.',
  )
  parser.add_argument(
    '--update-locations',
    action='store_true',
    help='Refetch station locations even when cached locations already exist.',
  )
  _add_debug_arg(parser)

  args = parser.parse_args()

  check_userid(args.userid)

  return args


def parse_location_args():
  import textwrap
  import argparse

  description = """
  Reads inventory file and fetches data on each station's first and last available day to get geographic latitude and longitude. Writes results to locations.json.
  """

  epilog = """
  Examples:
    Fetch locations for all stations, using cached location data when available:
      supermag-locations --userid USERID
    Fetch locations for all stations, refetching location data even when cached data found:
      supermag-locations --update --userid USERID
    Fetch location for a single station, using cached location data when available:
      supermag-locations --station-id ABK --userid USERID
    Fetch location for a single station, refetching location data even when cached data found:
      supermag-locations --station-id ABK --update --userid USERID
  """
  epilog = textwrap.dedent(epilog)

  parser = argparse.ArgumentParser(
    description=description,
    epilog=epilog,
    formatter_class=argparse.RawDescriptionHelpFormatter
  )

  _add_userid_arg(parser)
  _add_output_dir_arg(parser, CONFIG['common']['output_dir'])
  _add_station_id_arg(parser)
  parser.add_argument(
    '--update',
    action='store_true',
    help='Refetch location data even when cached location information found.',
  )
  _add_debug_arg(parser)

  args = parser.parse_args()

  check_userid(args.userid)

  return args


def main_data():
  # Called when running `python -m supermag.data` or supermag-data from the command line.
  # Parses command-line arguments, calls data() or indices(), and writes output to a file.
  import pathlib

  from .data import data
  from .data import indices

  args = parse_data_args()

  if args.debug:
    logger.setLevel("DEBUG")

  logger.debug("Parsed command-line arguments:")
  for arg in vars(args):
    logger.debug(f"  {arg}: {getattr(args, arg)}")

  if args.dataset.lower() == 'indices':
    kwargs = {
      'format': args.format,
      'cache': args.cache,
      'ignore_cache': args.ignore_cache,
      'cache_dir': args.cache_dir,
      'cafile': args.cafile
    }
    result, error = indices(args.userid, args.start, args.extent, **kwargs)
  else:
    kwargs = {
      'baseline': args.baseline,
      'delta': args.delta,
      'format': args.format,
      'cache': args.cache,
      'ignore_cache': args.ignore_cache,
      'cache_dir': args.cache_dir,
      'cafile': args.cafile
    }
    result, error = data(args.userid, args.dataset, args.start, args.extent, **kwargs)

  if error is not None:
    logger.error(f"Error getting: {error['url']}")
    logger.error(f"Error message: {error['error']}")
  else:
    ext = args.format
    ext2 = ""
    if args.format == 'dataframe' or args.format == 'list':
      ext2 = '.pkl'
    if args.output_file is not None:
      output_file = args.output_file
    else:
      if args.dataset.lower() == 'indices':
        fname = f"supermag-{args.dataset}-{args.start}-{args.stop}-indices.{ext}{ext2}"
      else:
        baseline_str = args.baseline if args.baseline is not None else 'none'
        delta_str = args.delta if args.delta is not None else 'none'
        fname = f"supermag-{args.dataset}-{args.start}-{args.stop}-baseline_{baseline_str}-delta_{delta_str}.{ext}{ext2}"
      output_file = pathlib.Path(args.output_dir) / fname

    output_file.parent.mkdir(parents=True, exist_ok=True)

    if args.format == 'json':
      import json
      output_file.write_text(json.dumps(result, indent=2) + '\n')
    elif args.format == 'csv':
      output_file.write_text(result + '\n')
    elif args.format == 'dataframe':
      result.to_pickle(output_file)
    elif args.format == 'list':
      import pickle
      with output_file.open('wb') as f:
        pickle.dump(result, f)

    logger.info(f"Wrote {output_file}")


def main_inventory():
  args = parse_inventory_args()

  if args.debug:
    logger.setLevel("DEBUG")

  kwargs = {
    'output_dir': args.output_dir,
    'update_inventory': args.update_inventory,
    'update_locations': args.update_locations,
    'station_id': args.station_id
  }

  from .inventory import inventory
  inventory(args.userid, args.start, args.stop, **kwargs)

  if args.station_id is None:
    import pathlib
    _move_logs('supermag-inventory', pathlib.Path(args.output_dir) / 'inventory')


def main_locations():
  args = parse_location_args()

  if args.debug:
    logger.setLevel("DEBUG")

  kwargs = {
    'output_dir': args.output_dir,
    'station_id': args.station_id,
    'update': args.update
  }

  from .locations import locations
  locations(args.userid, **kwargs)

  if args.station_id is not None:
    _move_logs('supermag-locations', args.output_dir)


def _move_logs(log_prefix, output_dir):
  import shutil
  import pathlib

  # Rename log prefix by removing 'supermag-' prefix from log file names
  log_files = [f'{log_prefix}.log', f'{log_prefix}.error.log']
  cwd = pathlib.Path.cwd()
  for i, log_file in enumerate(log_files):
    src = cwd / log_file
    dst_name = log_file
    if dst_name.startswith('supermag-'):
      dst_name = dst_name[len('supermag-'):]
    dst = cwd / dst_name
    if src.exists() and src != dst:
      shutil.move(str(src), str(dst))
    log_files[i] = dst_name

  from .util import move_log_files
  move_log_files(log_files, output_dir, archive=True)


def _add_userid_arg(parser):
  parser.add_argument(
    '--userid',
    required=True,
    help='SuperMAG user ID (required).',
  )


def _add_debug_arg(parser):
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.'
  )


def _add_output_dir_arg(parser, default):
  parser.add_argument(
    '--output-dir',
    default=default,
    help='Path to write output file. Ignored if --output-file is given. Default: current directory.'
  )


def _add_cafile_arg(parser):
  parser.add_argument(
    '--cafile',
    default='none',
    type=str,
    help="CA bundle setting: 'default', 'none', or path to PEM file. Default: default."
  )


def _add_station_id_arg(parser):
  parser.add_argument(
    '--station-id',
    default=None,
    help='Only include the given station ID in the combined inventory output',
  )


def _add_start_arg(parser, start):
  parser.add_argument(
    '--start',
    default=start,
    help=f'First UTC day to fetch, in YYYY-MM-DD format. Default: {start}',
  )


def _add_stop_arg(parser, stop):
  parser.add_argument(
    '--stop',
    default=stop,
    help=f'Last UTC day to fetch, in YYYY-MM-DD format. Default: {stop}',
  )
