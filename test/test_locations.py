# pytest test_locations.py --userid USERID

import supermag
from util import userid

def test_short(userid=userid):

  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-03',
    'update_inventory': False,
    'update_locations': False
  }

  inventory = supermag.inventory(userid, **kwargs)

  print(inventory)
  print("\n")

  for item in inventory:
    if item['id'] == 'DRV':
      del item['location']

  kwargs = {
    'update': False,
    'inventory': inventory
  }
  locations = supermag.locations(userid, **kwargs)
  assert 'DRV' in locations, f"Missing 'DRV' key in locations: {locations}"


if __name__ == "__main__":

  import sys
  from supermag.util import logger

  logger.setLevel('DEBUG')

  args = sys.argv
  if len(args) == 2:
    userid = args[1]
  else:
    print("Usage: python test_locations.py USERID")

  test_short(userid=args[1])
