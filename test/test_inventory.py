# pytest test_inventory.py --userid USERID

import supermag
from util import userid

# Change these to True when this test script complete
update_inventory = False
update_locations = False

def test_simple(userid=userid):
  kwargs = {
    'start': '1970-01-01',
    'stop': '1970-01-10',
    'update_inventory': True,
    'update_locations': True
  }

  inventory = supermag.inventory(userid, **kwargs)
  assert inventory is not None, "Expected inventory to be non-None"
  assert isinstance(inventory, list), "Expected inventory to be a list"
  assert len(inventory) > 0, "Expected inventory to have at least one item"
  found = False
  for item in inventory:
    assert isinstance(item, dict), "Expected each inventory item to be a dictionary"
    for keys in ['id', 'startDate', 'stopDate', 'available_percent', 'location']:
      assert keys in item, f"Expected each inventory item to have a '{keys}' key"
    if item['id'] == 'DRV':
      found = True
  assert found, "Expected to find an inventory item with id 'DRV'"

if __name__ == "__main__":
  test_simple(userid='superhapi')