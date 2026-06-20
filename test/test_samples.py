# pytest test_samples.py --userid USERID

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
      del item['sample']

  kwargs = {
    'update': False,
    'inventory': inventory
  }
  samples = supermag.samples(userid, **kwargs)
  assert 'DRV' in samples, f"Missing 'DRV' key in samples: {samples}"


if __name__ == "__main__":
  from util import parse_args
  args = parse_args()
  test_short(userid=args.userid)
