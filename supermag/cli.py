from .util import logger, check_userid

from .config import config
CONFIG = config()


def parse_data_args():
  import pathlib
  import sys

  default_cache_dir = CONFIG['common']['output_dir']

  description = 'Fetch SuperMAG station data via data().'

  epilog = """
  Examples:
    supermag-data --userid USERID
    supermag-data --dataset indices --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z --userid USERID
    supermag-data --dataset ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z --userid USERID
    supermag-data --dataset ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z --userid USERID
  """

  parser = _parser(description=description, epilog=epilog)

  # If these defaults changed, will need to update tests.
  default_dataset = 'ABK'
  default_start = '2001-01-01T00:00Z'
  default_stop  = '2001-01-01T00:01Z'

  _add_arg(parser, "userid")
  _add_arg(parser, "dataset", default_dataset)
  _add_arg(parser, "start", default_start)
  _add_arg(parser, "stop", default_stop)
  parser.add_argument(
    '--delta',
    default='none',
    choices=['start', 'none'],
    help='Delta parameter for the SuperMAG API. Default: none.',
  )
  parser.add_argument(
    '--baseline',
    default='none',
    choices=['all', 'yearly', 'none'],
    help='Baseline parameter for the SuperMAG API. Default: none.',
  )
  parser.add_argument(
    '--format',
    default='json',
    choices=['json', 'csv', 'csv-hapi', 'csv-hapi-noheader', 'list', 'dataframe'],
    help='Output format. Default: json.',
  )
  parser.add_argument(
    '--no-cache',
    action='store_true',
    help='Do not write or read cache. (Default is to request data from 00:00:00Z on date of start through 23:59:59Z on date of stop.)'
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
  parser.add_argument(
    '--parameters',
    default=None,
    help='Comma-separated extra parameters for magnetometer data requests (e.g., mlt,geo,decl,sza).'
  )
  _add_arg(parser, "cafile")
  _add_arg(parser, "debug")
  _add_arg(parser, "output-dir")
  parser.add_argument(
    '--print',
    action='store_true',
    help='Print output to console instead of writing a file.',
  )
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

  if args.print:
    if '--output-dir' in sys.argv or '--output-file' in sys.argv:
      raise ValueError('--print cannot be used with --output-dir or --output-file')

  if args.parameters is not None and args.dataset.lower() == 'indices':
    raise ValueError('--parameters is not supported when --dataset indices is used')

  return args


def parse_inventory_args():
  import inspect
  from .inventory import inventory

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

  description = _unwrap_description(inspect.getdoc(inventory))
  description += "\n\nIf --station-id, --start, or --stop is given, output is written to OUTPUT_DIR/partial."

  parser = _parser(description=description, epilog=epilog)

  _add_arg(parser, "userid")
  _add_arg(parser, "start", default_start)
  _add_arg(parser, "stop", default_stop)
  _add_arg(parser, "output-dir")
  _add_arg(parser, "station-id")
  _add_arg(parser, "update-inventory")
  _add_arg(parser, "update-locations")
  _add_arg(parser, "print")
  _add_arg(parser, "cafile")
  _add_arg(parser, "debug")

  args = parser.parse_args()

  check_userid(args.userid)

  return args


def parse_samples_args():
  import inspect
  from .samples import samples
  description = _unwrap_description(inspect.getdoc(samples))

  epilog = """
  Examples:
    Fetch samples for all stations, using cached sample data when available:
      supermag-samples --userid USERID
    Fetch samples for all stations, refetching sample data even when cached data found:
      supermag-samples --update --userid USERID
    Fetch sample for a single station, using cached sample data when available:
      supermag-samples --station-id ABK --userid USERID
    Fetch sample for a single station, refetching sample data even when cached data found:
      supermag-samples --station-id ABK --update --userid USERID
  """

  parser = _parser(description=description, epilog=epilog)

  _add_arg(parser, "userid")
  _add_arg(parser, "output-dir")
  _add_arg(parser, "station-id")
  parser.add_argument(
    '--update',
    action='store_true',
    help='Refetch location data even when cached location information found.',
  )
  _add_arg(parser, "print")
  _add_arg(parser, "cafile")
  _add_arg(parser, "debug")

  args = parser.parse_args()

  check_userid(args.userid)

  return args


def parse_catalog_args():

  description = "Create catalog-all.json from inventory.json"
  epilog = """
  Examples:
    Full run:
      supermag-catalog --userid USERID
    Short tests:
      supermag-catalog --start 1970-01-01 --stop 1970-01-03 --userid USERID
      supermag-catalog --start 1970-01-01 --stop 1970-01-03 --userid USERID
      supermag-catalog --start 1970-01-01 --stop 1970-01-03 --update-inventory --userid USERID
      supermag-catalog --start 1970-01-01 --stop 1970-01-03 --update-inventory --update-locations --userid USERID
  """

  parser = _parser(description=description, epilog=epilog)

  _add_arg(parser, "userid")
  _add_arg(parser, "dataset")
  _add_arg(parser, "start")
  _add_arg(parser, "stop")
  _add_arg(parser, "output-dir")
  _add_arg(parser, "update-inventory")
  _add_arg(parser, "update-locations")
  _add_arg(parser, "print")
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.',
  )
  _add_arg(parser, "cafile")

  args = parser.parse_args()
  check_userid(args.userid)

  return args


def main_data():
  # Called when running `python -m supermag.data` or supermag-data from the command line.
  # Parses command-line arguments, calls data() or indices(), and writes output to a file.
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
      'parameters': args.parameters,
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
    raise SystemExit(1)
  else:
    if _print_data_if_requested(result, args.print, None, data_format=args.format):
      return

    _write_file_if_requested(result, args)


def main_inventory():
  args = parse_inventory_args()

  if args.debug:
    logger.setLevel("DEBUG")

  kwargs = {
    'output_dir': args.output_dir,
    'update_inventory': args.update_inventory,
    'update_locations': args.update_locations,
    'station_id': args.station_id,
    'cafile': args.cafile
  }

  from .inventory import inventory
  inventory_dict = inventory(args.userid, args.start, args.stop, **kwargs)

  _print_data_if_requested(inventory_dict, args.print, args.station_id)
  _move_logs('supermag-inventory', args, kind='inventory')


def main_samples():
  args = parse_samples_args()

  if args.debug:
    logger.setLevel("DEBUG")

  kwargs = {
    'output_dir': args.output_dir,
    'station_id': args.station_id,
    'update': args.update
  }

  from .samples import samples
  samples_dict = samples(args.userid, **kwargs)

  _print_data_if_requested(samples_dict, args.print, args.station_id)
  _move_logs('supermag-samples', args, kind='samples')


def main_catalog():
  args = parse_catalog_args()
  kwargs = {
    'start': args.start,
    'stop': args.stop,
    'output_dir': args.output_dir,
    'update_inventory': args.update_inventory,
    'update_locations': args.update_locations,
    'dataset': args.dataset,
    'cafile': args.cafile
  }

  from .catalog import catalog
  catalog_dict = catalog(args.userid, **kwargs)

  _move_logs('supermag-catalog', args, kind='catalog')

  _print_data_if_requested(catalog_dict, args.print, args.dataset)


def _parser(description=None, epilog=None):
  import textwrap
  import argparse
  return argparse.ArgumentParser(
    description=textwrap.dedent(description),
    epilog=textwrap.dedent(epilog),
    formatter_class=argparse.RawDescriptionHelpFormatter
  )


def _unwrap_description(text):
  if text is None:
    return ''

  # Allow docstrings to include internal sections separated by ----
  # while keeping only the leading summary for CLI help output.
  text = text.split('----', 1)[0].rstrip()

  paragraphs = [
    ' '.join(line.strip() for line in block.splitlines() if line.strip())
    for block in text.split('\n\n')
  ]
  paragraphs = [paragraph for paragraph in paragraphs if paragraph]
  return '\n\n'.join(paragraphs)


def _print_data_if_requested(data, print_arg, selector_arg=None, data_format='json'):
  should_print = (print_arg is True) or (print_arg is None and selector_arg is not None)
  if not should_print:
    return False

  if data_format == 'json':
    import json
    print(json.dumps(data, indent=2) + '\n')
  elif data_format in ['csv', 'csv-hapi', 'csv-hapi-noheader']:
    print(data + '\n')
  elif data_format == 'dataframe':
    print(data)
  elif data_format == 'list':
    import pprint
    print(pprint.pformat(data) + '\n')
  else:
    print(data)

  return True


def _write_file_if_requested(data, args):
  import pathlib

  data_format = args.format

  ext = data_format
  ext2 = ""
  if data_format == 'dataframe' or data_format == 'list':
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

  if data_format == 'json':
    import json
    output_file.write_text(json.dumps(data, indent=2) + '\n')
  elif data_format in ['csv', 'csv-hapi', 'csv-hapi-noheader']:
    output_file.write_text(data + '\n')
  elif data_format == 'dataframe':
    data.to_pickle(output_file)
  elif data_format == 'list':
    import pickle
    with output_file.open('wb') as f:
      pickle.dump(data, f)
  else:
    raise ValueError(f"Unsupported data format for file write: {data_format}")

  logger.info(f"Wrote {output_file}")


def _add_arg(parser, arg, default=None):

  if arg == "userid":
    parser.add_argument(
      '--userid',
      required=True,
      help='SuperMAG user ID (required).',
    )
  if arg == "debug":
    parser.add_argument(
      '--debug',
      action='store_true',
      help='Enable debug logging.'
    )
  if arg == "output-dir":
    default = CONFIG['common']['output_dir']
    parser.add_argument(
      '--output-dir',
      default=default,
      help=f'Path to write output file. Ignored if --output-file is given. Default: {default}.'
    )
  if arg == "cafile":
    parser.add_argument(
      '--cafile',
      default='none',
      type=str,
      help="CA bundle setting: 'default', 'none', or path to PEM file. Default: 'none'."
    )
  if arg == "station-id":
    parser.add_argument(
      '--station-id',
      default=None,
      help='Only include the given station ID in the combined inventory output',
    )
  if arg == "start":
    parser.add_argument(
      '--start',
      default=default,
      help=f'First UTC day to fetch, in YYYY-MM-DD format. Default: {default}',
    )
  if arg == "stop":
    parser.add_argument(
      '--stop',
      default=default,
      help=f'Last UTC day to fetch, in YYYY-MM-DD format. Default: {default}',
    )
  if arg == "update-inventory":
    parser.add_argument(
      '--update-inventory',
      action='store_true',
      help='Refetch and overwrite existing daily inventory files.',
    )
  if arg == "update-locations":
    parser.add_argument(
      '--update-locations',
      action='store_true',
      help='Refetch station locations even when cached locations already exist.',
    )
  if arg == "dataset":
    parser.add_argument(
      '--dataset',
      default=default,
      help=f'"indices" or IAGA magnetometer station ID (e.g., "BOU"). Default: {default}.',
    )
  if arg == "print":
    parser.add_argument(
      '--print',
      action='store_true',
      default=None,
      help='Print JSON to console. Default: print only when --station-id or --dataset is given.',
    )


def _move_logs(log_prefix, args, kind):
  import shutil
  import pathlib
  from .util import _partial_output_stem

  if kind == 'inventory':
    from .util import data_range
    default_start, default_stop = data_range()
    partial = args.station_id is not None or args.start != default_start or args.stop != default_stop
    subdir = 'inventory'
  elif kind == 'samples':
    partial = args.station_id is not None
    subdir = 'inventory'
  elif kind == 'catalog':
    partial = args.dataset is not None or args.start is not None or args.stop is not None
    subdir = 'catalog'
  else:
    raise ValueError(f'Unknown log kind: {kind}')

  output_dir = pathlib.Path(args.output_dir) / subdir
  if partial:
    output_dir = output_dir / 'partial'

  # Rename log prefix by removing 'supermag-' prefix from log file names
  log_files = [f'{log_prefix}.log', f'{log_prefix}.error.log']
  cwd = pathlib.Path.cwd()
  partial_stem = _partial_output_stem(
    file_type=subdir,
    station_id=getattr(args, 'station_id', None),
    dataset=getattr(args, 'dataset', None),
    start=getattr(args, 'start', None),
    stop=getattr(args, 'stop', None),
    partial=partial,
  )
  for i, log_file in enumerate(log_files):
    src = cwd / log_file
    if partial:
      ext = '.error.log' if log_file.endswith('.error.log') else '.log'
      dst_name = f'{partial_stem}{ext}'
    else:
      dst_name = log_file[len('supermag-'):] if log_file.startswith('supermag-') else log_file

    dst = cwd / dst_name
    if src.exists() and src != dst:
      shutil.move(str(src), str(dst))
    log_files[i] = dst_name

  from .util import move_log_files
  archive_logs = not (kind == 'inventory' and partial)
  move_log_files(log_files, output_dir, archive=archive_logs)
