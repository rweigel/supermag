import sys
import json
import pathlib

import supermag
from supermag.util import logger

userid = sys.argv[1] if len(sys.argv) == 2 else None
if userid is None:
  raise ValueError("User ID must be provided as the first argument")

# API => HAPI parameter name mapping
map = {
  'SMEnum':  'NUM',
  'SMErnum': 'NUMr',
  'SMEsnum': 'NUMs',
  'SMEdnum': 'NUMd',
  'dynpres': 'pdyn'
}

userid = sys.argv[1] if len(sys.argv) == 2 else None
supermag.util.logger.setLevel("DEBUG")

# Parameter names from indices_old/indices_*.json
hapi_dir = pathlib.Path('indices_old')
hapi_files = sorted(hapi_dir.glob('indices_*.json'))

hapi_names = {}
for file_path in hapi_files:
  key = file_path.stem
  val = json.loads(file_path.read_text())
  hapi_names[key] = [p['name'] for p in val['parameters'] if p['name'] != 'Time']

# Parameter names from a live indices response
data, error = supermag.indices(userid, '2001-01-01T00:00:00Z', 60, use_cache=False)
assert error is None, f"Error: {error}"

logger.info("")
logger.info("api name (hapi if differs)\t\tsample value")
api_names = []
api_names_mapped = []
for name in list(data[0].keys()):
  if name == 'tval_iso':
    # tval_iso is added by the client; drop it for comparison
    continue
  api_names.append(name)
  api_names_mapped.append(map.get(name, name))
  if name in map:
    display_name = f"{name} ({map[name]})"
  else:
    display_name = f"{name}"

  logger.info(f"{display_name:<20}\t\t{data[0][name]}")

logger.info("")
for key, names in hapi_names.items():
  logger.info(f"--- {key} ({len(names)} params) ---")
  in_hapi_not_api = sorted(set(names) - set(api_names))
  in_hapi_not_api_mapped = sorted(set(names) - set(api_names_mapped))
  if in_hapi_not_api:
      logger.info(f"  In HAPI {key} but not in API response: {in_hapi_not_api}")
      logger.info(f"  After mapping: {in_hapi_not_api_mapped}")
  else:
      logger.info(f"  Match: All parameters from {key} are in the API response")
  logger.info("")
