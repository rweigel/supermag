import logging

from .util import configure_logging
logger = configure_logging(__name__, level=logging.INFO)

def parse_args():
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
      '  supermag-data --userid USERID --station ABK\n'
      '  supermag-data --userid USERID --station ABK --start 2001-01-01T00:00Z --stop 2001-01-01T01:00Z\n'
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

  # Normalise times to HH:MMZ
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


def main():
  # Called when running `python -m supermag.data` or supermag-data from the command line.
  # Parses command-line arguments, calls data() or indices(), and writes output to a file.
  import pathlib
  from .util import set_logging_level
  from .cli import parse_args

  from .data import data
  from .data import indices

  args = parse_args()

  if args.debug:
    set_logging_level(logging.DEBUG, [__name__])

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
