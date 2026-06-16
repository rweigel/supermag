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
    '--station',
    default=default_station,
    help=f'SuperMAG station ID. Default: {default_station}.',
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

  return args

