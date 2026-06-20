import sys
import json
import pathlib

import supermag
from supermag.util import logger

userid = sys.argv[1] if len(sys.argv) == 2 else None
if userid is None:
    raise ValueError("User ID must be provided as the first argument")
logger.setLevel("DEBUG")

# Parameter names from indices.json
indices_hapi = json.loads(pathlib.Path('../../supermag/indices.json').read_text())
hapi_names = [
  p['name']
  for p in indices_hapi['indices_all']['parameters']
  if p.get('name') != 'Time'
]

# Parameter names from a live indices response
data, error = supermag.indices(userid, '2001-01-01T00:00:00Z', 60, ignore_cache=False)
assert error is None, f"Error: {error}"

# Check that HAPI names are same as the API keys
api_keys = [
  k for k in data[0].keys()
  if k not in {'tval', 'tval_iso'}
]

in_api_not_hapi = sorted(set(api_keys) - set(hapi_names))
assert not in_api_not_hapi, f"Parameters in API response but not in HAPI: {in_api_not_hapi}"
logger.info("Parameter keys in API response match HAPI parameter names")

logger.info("Sample API response data")
for name in api_keys:
  logger.info(f"{name:<20}\t\t{data[0][name]}")
