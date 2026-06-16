import logging

from .util import configure_logging
logger = configure_logging(__name__)

def parse_data_args():
  import pathlib
  import argparse

  default_cache_dir = 'supermag-cache'

  # If these defaults changed, will need to update tests.
  default_station = 'ABK'
  default_start = '2001-01-01T00:00Z'
  default_stop  = '2001-01-01T00:01Z'

  parser = argparse.ArgumentParser(
    description='Fetch SuperMAG station data via data().',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=(
      'Examples:\n'
      '  supermag-data --userid USERID\n'
      '  supermag-data --userid USERID --dataset indices --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z\n'
      '  supermag-data --userid USERID --dataset ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z\n'
      '  supermag-data --userid USERID --dataset ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z\n'
    ),
  )
  parser.add_argument(
    '--dataset',
    default=default_station,
    help=f'"indices" or magnetometer IAGA ID (e.g., BOU). Default: {default_station}.',
  )
  parser.add_argument(
    '--userid',
    required=True,
    help='SuperMAG user ID (required).',
  )
  parser.add_argument(
    '--start',
    default=default_start,
    help=f'Start time (YYYY-MM-DDTHH:MMZ or full ISO). Default: {default_start}.',
  )
  parser.add_argument(
    '--stop',
    default=default_stop,
    help=f'Stop time (YYYY-MM-DDTHH:MMZ or full ISO). Default: {default_stop}.',
  )
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
    help='Disable caching entirely.'
  )
  parser.add_argument(
    '--ignore-cache',
    action='store_true',
    help='Re-fetch even if a cache file exists.'
  )
  parser.add_argument(
    '--cache-dir',
    default=default_cache_dir,
    type=pathlib.Path,
    help=f'Base directory for cache storage. Default: {default_cache_dir}.'
  )
  parser.add_argument(
    '--cafile',
    default='none',
    type=str,
    help="CA bundle setting: 'default', 'none', or path to PEM file. Default: default."
  )
  parser.add_argument(
    '--timeout',
    default=30,
    type=float,
    help='Request timeout in seconds. Default: 30.'
  )
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.'
  )
  parser.add_argument(
    '--output-dir',
    default=".",
    help='Path to write output file. Ignored if --output-file is given. Default: current directory.'
  )
  parser.add_argument(
    '--output-file',
    default=None,
    type=pathlib.Path,
    help='Path to write output. If not given, writes to supermag-{station}-{start}-{stop}-{baseline}-{delta}.{format}'
  )
  args = parser.parse_args()

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
  import argparse
  import sys
  import datetime as dt
  from pathlib import Path

  from .util import path_relative_to_cwd

  from .config import config
  CONFIG = config('inventory')

  default_start = '1970-01-01'
  tomorrow = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)
  default_stop  = (tomorrow).isoformat()

  epilog =  'Examples:\n'
  epilog += '  supermag-inventory\n'
  epilog += '  supermag-inventory --update-inventory\n'
  epilog += '  supermag-inventory --update-locations\n'
  epilog += '  supermag-inventory --start 2000-01-01 --stop 2000-01-03 --update-inventory --update-locations\n'

  description = 'Fetch daily SuperMAG inventories and create inventory.json file with list of avaialble dates for each station.'
  description += '\n\nIf --station-id, --start, or --stop is given, output is written to OUTPUT_DIR/partial\n'

  parser = argparse.ArgumentParser(
    description=description,
    epilog=epilog,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )

  parser.add_argument(
    '--start',
    default=default_start,
    help=f'First UTC day to fetch, in YYYY-MM-DD format. Default: {default_start}',
  )
  parser.add_argument(
    '--stop',
    default=default_stop,
    help=f'Last UTC day to fetch, in YYYY-MM-DD format. Default: {default_stop}',
  )
  parser.add_argument(
    '--output-dir',
    default=CONFIG['output_dir'],
    type=Path,
    help=f'Base directory for outputs. Default: {path_relative_to_cwd(CONFIG['output_dir'])}',
  )
  parser.add_argument(
    '--station-id',
    default=None,
    help='Only include the given station ID in the combined inventory output',
  )
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
  parser.add_argument(
    '--timeout',
    default=CONFIG['timeout'],
    type=int,
    help=f'HTTP timeout in seconds for each fetch. Default: {CONFIG['timeout']}',
  )
  parser.add_argument(
    '--delay',
    default=CONFIG['delay'],
    type=float,
    help=f'Delay in seconds between actual HTTP requests. Default: {CONFIG['delay']}',
  )
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.',
  )
  args = parser.parse_args()
  args.partial_inventory = '--start' in sys.argv[1:] or '--stop' in sys.argv[1:]
  return args


def main_data():
  # Called when running `python -m supermag.data` or supermag-data from the command line.
  # Parses command-line arguments, calls data() or indices(), and writes output to a file.
  import pathlib
  from .util import set_logging_level

  from .data import data
  from .data import indices

  args = parse_data_args()

  if args.debug:
    set_logging_level(logging.DEBUG)

  logger.debug("Parsed command-line arguments:")
  for arg in vars(args):
    logger.debug(f"  {arg}: {getattr(args, arg)}")

  if args.dataset.lower() == 'indices':
    kwargs = {
      'format': args.format,
      'cache': args.cache,
      'ignore_cache': args.ignore_cache,
      'cache_dir': args.cache_dir,
      'cafile': args.cafile,
      'timeout': args.timeout,
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
      'cafile': args.cafile,
      'timeout': args.timeout,
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
  from .util import set_logging_level

  args = parse_inventory_args()

  if args.debug:
    set_logging_level(logging.DEBUG)

  kwargs = {
    'output_dir': args.output_dir,
    'update_inventory': args.update_inventory,
    'update_locations': args.update_locations,
    'station_id': args.station_id,
    'partial_inventory': args.partial_inventory,
    'timeout': args.timeout,
    'delay': args.delay,
  }

  from .inventory import inventory
  inventory(args.start, args.stop, **kwargs)

