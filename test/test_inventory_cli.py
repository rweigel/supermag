# Usage:
#   pytest test_inventory_cli.py --userid USERID
#   python test_inventory_cli.py --userid USERID
from types import SimpleNamespace

import supermag.cli as cli
import supermag.util as util


def test_partial_inventory_log_names_match_json_selector(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  monkeypatch.setattr(util, 'data_range', lambda: ('1970-01-01', '1970-01-10'))

  (tmp_path / 'supermag-inventory.log').write_text('info\n')
  (tmp_path / 'supermag-inventory.error.log').write_text('error\n')

  args = SimpleNamespace(
    output_dir=tmp_path / 'output',
    station_id=None,
    start='1970-01-01',
    stop='1970-01-09',
  )

  cli._move_logs('supermag-inventory', args, kind='inventory')

  expected_dir = tmp_path / 'output' / 'inventory' / 'partial'
  assert (expected_dir / 'inventory-1970-01-01-1970-01-09.log').is_file()
  assert (expected_dir / 'inventory-1970-01-01-1970-01-09.error.log').is_file()
  assert not (expected_dir / 'inventory-1970-01-09.log').exists()