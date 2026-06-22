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

  assert inventory is not None, "Expected inventory to be non-None"
  assert isinstance(inventory, list), "Expected inventory to be a list"
  assert len(inventory) > 0, "Expected inventory to have at least one item"
  found = False
  for item in inventory:
    assert isinstance(item, dict), "Expected each inventory item to be a dictionary"
    for keys in ['id', 'startDate', 'stopDate', 'station', 'availability', 'location', 'sample']:
      assert keys in item, f"Expected each inventory item to have a '{keys}' key"
    assert 'glat' in item['location']['firstRecord'], "Expected location.firstRecord to keep the location summary"
    assert 'glon' in item['location']['firstRecord'], "Expected location.firstRecord to keep the location summary"
    assert 'tval' in item['sample']['firstRecord'], "Expected sample.firstRecord to contain full data from data()"
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
  assert inventory_cached == inventory, "Expected cached inventory to match the previously fetched inventory"

  print("\n")

  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-10',
    'update_inventory': True,
    'update_samples': False
  }

  inventory_cached = supermag.inventory(userid, **kwargs)
  assert inventory_cached == inventory, "Expected cached inventory to match the previously fetched inventory"

  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-10',
    'update_inventory': False,
    'update_samples': True
  }

  inventory_cached = supermag.inventory(userid, **kwargs)
  assert inventory_cached == inventory, "Expected cached inventory to match the previously fetched inventory"


if __name__ == "__main__":
  from util import parse_args
  args = parse_args()
  test_short(userid=args.userid)
