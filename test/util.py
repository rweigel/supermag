import json
import pickle

tval = 978307200.0  # Jan 1, 2001

userid = 'superhapi'

def _check_output(data, n_records=1, format=None, ext=None, output_file=None):
  output_target = output_file if output_file is not None else 'response'

  keys = ['tval', 'ext', 'iaga', 'mlt', 'mcolat', 'decl', 'sza',  'N_nez', 'N_geo', 'E_nez', 'E_geo', 'Z_nez', 'Z_geo']
  keys_raw = ['tval', 'ext', 'iaga', 'mlt', 'mcolat', 'decl', 'sza', 'N', 'E', 'Z']
  keys_df = ['tval_datetime'] + keys

  # CSV output is text.
  if isinstance(data, str):
    lines = [line for line in data.splitlines() if line]
    assert len(lines) == n_records + 1, f"Expected header + 1 row in output {output_target}, found {len(lines)} lines"
    assert lines[0].split(',') == keys, f"Expected CSV header keys {keys} in output {output_target}, found {lines[0].split(',')}"
    assert lines[0].startswith('tval,'), f"Expected CSV header to start with 'tval,', found {lines[0]}"
    assert lines[1].startswith(f'{tval},'), f"Expected first CSV row to start with '{tval},', found {lines[1]}"
    return

  # DataFrame-like output supports iloc.
  if hasattr(data, 'iloc'):
    assert list(data.columns) == keys_df, f"Expected DataFrame columns {keys_df} in output {output_target}, found {list(data.columns)}"
    assert len(data) == n_records, f"Expected {n_records} row(s) in output {output_target}, found {len(data)}"
    assert data.iloc[0]['tval'] == tval, f"Expected tval {tval} in first row of output {output_target}, found {data.iloc[0]['tval']}"
    return

  # JSON/list output is list-based.
  if isinstance(data, list):
    assert len(data) >= 1, f"Expected at least one row in output {output_target}, found {len(data)}"
    first = data[0]

    if isinstance(first, dict):
      assert len(data) == n_records, f"Expected {n_records} row(s) in output {output_target}, found {len(data)}"
      assert set(first.keys()) == set(keys_raw), f"Expected JSON keys {keys_raw} in output {output_target}, found {set(first.keys())}"
      assert data[0]['tval'] == tval, f"Expected tval {tval} in first row of output {output_target}, found {data[0]['tval']}"
      return

    if isinstance(first, (list, tuple)):
      assert len(data) == n_records + 1, f"Expected {n_records + 1} rows in output {output_target}, found {len(data)} rows"
      assert data[0] == keys, f"Expected header keys {keys} in output {output_target}, found {data[0]}"
      assert data[0][0] == 'tval', f"Expected first header entry to be 'tval' in output {output_target}, found {data[0][0]}"
      assert data[1][0] == tval, f"Expected first data row tval {tval} in output {output_target}, found {data[1][0]}"
      return

    assert False, f"Unsupported list row type in output {output_target}: {type(first)}"

  assert False, f"Unsupported output data type in {output_target}: {type(data)}"


def _check_output_file(output_file, format=None, ext=None):
  assert output_file.is_file(), f"Expected output file not found: {output_file}"

  if format is None and ext is None:
    suffix = output_file.suffix.lower()
    if suffix == '.json':
      format, ext = 'json', 'json'
    elif suffix == '.csv':
      format, ext = 'csv', 'csv'
    elif suffix == '.pkl':
      format, ext = 'pickle', 'pkl'
    else:
      assert False, f"Unsupported output file extension: {suffix}"

  if format == 'json' and ext == 'json':
    with output_file.open('r') as f:
      data = json.load(f)
    _check_output(data, format, ext, output_file=output_file)
    return

  if format == 'csv' and ext == 'csv':
    csv_text = output_file.read_text()
    _check_output(csv_text, format, ext, output_file=output_file)
    return

  if ext == 'pkl':
    with output_file.open('rb') as f:
      data = pickle.load(f)
    _check_output(data, format, ext, output_file=output_file)
    return

  assert False, f"Unsupported format/ext combination: {format}.{ext}"