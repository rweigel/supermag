# Usage:
#   pytest test_inventory.py --userid USERID
#   python test_inventory.py --userid USERID

import supermag
from util import userid


def test_short(userid=userid):
  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-10',
    'update_inventory': True,
    'update_samples': True
  }

  inventory = supermag.inventory(userid, **kwargs)

  assert inventory is not None, "Expected inventory to be not None"
  assert isinstance(inventory, list), "Expected inventory to be a list"
  assert len(inventory) > 0, "Expected inventory to have at least one item"

  found = False
  for item in inventory:

    msg = "Expected each inventory item to be a dictionary"
    assert isinstance(item, dict), msg
    keys_expected = [
                      'id',
                      'startDate',
                      'stopDate',
                      'station',
                      'availability',
                      'sample'
                    ]

    for key in keys_expected:
      msg = f"Expected each inventory item to have a '{key}' key"
      assert key in item, msg

    msg = "Expected sample.firstRecord to contain a tval key"
    assert 'tval' in item['sample']['firstRecord']['data'], msg

    if item['id'] == 'DRV':
      found = True

  assert found, "Expected to find an inventory item with id 'DRV'"

  print("\n")

  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-10',
    'update_inventory': False,
    'update_samples': False
  }

  inventory_cached = supermag.inventory(userid, **kwargs)
  msg = "Expected cached inventory to match the previously fetched inventory"
  assert inventory_cached == inventory, msg

  print("\n")

  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-10',
    'update_inventory': True,
    'update_samples': False
  }

  inventory_cached = supermag.inventory(userid, **kwargs)
  msg = "Expected cached inventory to match the previously fetched inventory"
  assert inventory_cached == inventory, msg

  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-10',
    'update_inventory': False,
    'update_samples': True
  }

  inventory_cached = supermag.inventory(userid, **kwargs)
  msg = "Expected cached inventory to match the previously fetched inventory"
  assert inventory_cached == inventory, msg


if __name__ == "__main__":
  from util import parse_args
  args = parse_args()
  test_short(userid=args.userid)
