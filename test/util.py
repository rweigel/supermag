import json
import pickle

# First tval and tval_iso in test data response.
tval_iso = '2001-01-01T00:00Z'
tval = 978307200.0  # Jan 1, 2001

userid = 'superhapi'

def check_output(data,
                  output_type='data',
                  n_records=1,
                  format=None,
                  ext=None,
                  output_file=None):
  output_target = output_file if output_file is not None else 'response'

  if output_type == 'data':
    keys_raw = ['tval_iso', 'tval', 'ext', 'iaga', 'mlt', 'mcolat', 'decl', 'sza', 'N', 'E', 'Z']
    keys_csv = ['tval_iso', 'tval', 'ext', 'iaga', 'mlt', 'mcolat', 'decl', 'sza',  'N_nez', 'N_geo', 'E_nez', 'E_geo', 'Z_nez', 'Z_geo']
  if output_type == 'indices':
    keys_raw = ['tval_iso', 'tval', 'SME', 'SML', 'SMLmlat', 'SMLmlt', 'SMLglat', 'SMLglon', 'SMLstid', 'SMU', 'SMUmlat', 'SMUmlt', 'SMUglat', 'SMUglon', 'SMUstid', 'SMEnum', 'SMEs', 'SMLs', 'SMLsmlat', 'SMLsmlt', 'SMLsglat', 'SMLsglon', 'SMLsstid', 'SMUs', 'SMUsmlat', 'SMUsmlt', 'SMUsglat', 'SMUsglon', 'SMUsstid', 'SMEsnum', 'SMEd', 'SMLd', 'SMLdmlat', 'SMLdmlt', 'SMLdglat', 'SMLdglon', 'SMLdstid', 'SMUd', 'SMUdmlat', 'SMUdmlt', 'SMUdglat', 'SMUdglon', 'SMUdstid', 'SMEdnum', 'SMEr', 'SMLr', 'SMLrmlat', 'SMLrmlt', 'SMLrglat', 'SMLrglon', 'SMLrstid', 'SMUr', 'SMUrmlat', 'SMUrmlt', 'SMUrglat', 'SMUrglon', 'SMUrstid', 'SMErnum', 'smr', 'smr00', 'smr06', 'smr12', 'smr18', 'smrnum', 'smrnum00', 'smrnum06', 'smrnum12', 'smrnum18', 'bgse', 'bgsm', 'vgse', 'vgsm', 'clockgse', 'clockgsm', 'density', 'dynpres', 'epsilon', 'newell']
    keys_csv = keys_raw.copy()
    # Replace vector fields in place with component names
    for vector in ['bgse', 'bgsm', 'vgse', 'vgsm']:
      idx = keys_csv.index(vector)
      keys_csv[idx:idx+1] = [f"{vector}_X", f"{vector}_Y", f"{vector}_Z"]

  keys_df = ['tval_datetime'] + keys_csv

  # CSV output is text.
  if isinstance(data, str):
    lines = [line for line in data.splitlines() if line]
    assert len(lines) == n_records + 1, f"Expected header + 1 row in output {output_target}, found {len(lines)} lines"
    assert lines[0].split(',') == keys_csv, f"Expected CSV header keys {keys_csv} in output {output_target}, found {lines[0].split(',')}"
    line1 = lines[1].split(',')
    assert line1[0] == str(tval_iso), f"Expected second CSV row to start with '{tval_iso},', found {line1[0]}"
    assert line1[1] == str(tval), f"Expected second CSV row to start with '{tval},', found {line1[0]}"
    return

  # DataFrame-like output supports iloc.
  if hasattr(data, 'iloc'):
    assert list(data.columns) == keys_df, f"Expected DataFrame columns {keys_df} in output {output_target}, found {list(data.columns)}"
    assert len(data) == n_records, f"Expected {n_records} row(s) in output {output_target}, found {len(data)}"
    assert data.iloc[0]['tval_iso'] == tval_iso, f"Expected tval_iso {tval_iso} in first row of output {output_target}, found {data.iloc[0]['tval_iso']}"
    assert data.iloc[0]['tval'] == tval, f"Expected tval {tval} in first row of output {output_target}, found {data.iloc[0]['tval']}"
    return

  # JSON/list output is list-based.
  if isinstance(data, list):
    assert len(data) >= 1, f"Expected at least one row in output {output_target}, found {len(data)}"
    first = data[0]

    if isinstance(first, dict):
      assert len(data) == n_records, f"Expected {n_records} row(s) in output {output_target}, found {len(data)}"
      assert set(first.keys()) == set(keys_raw), f"Expected JSON keys {keys_raw} in output {output_target}, found {first.keys()}"
      assert data[0]['tval_iso'] == tval_iso, f"Expected tval {tval_iso} in first row of output {output_target}, found {data[0]['tval_iso']}"
      assert data[0]['tval'] == tval, f"Expected tval {tval} in first row of output {output_target}, found {data[0]['tval']}"
      return

    if isinstance(first, (list, tuple)):
      assert len(data) == n_records + 1, f"Expected {n_records + 1} rows in output {output_target}, found {len(data)} rows"
      assert data[0] == keys_csv, f"Expected header keys {keys_csv} in output {output_target}, found {data[0]}"
      assert data[1][0] == tval_iso, f"Expected first data row tval_iso {tval_iso} in output {output_target}, found {data[1][0]}"
      assert data[1][1] == tval, f"Expected first data row tval {tval} in output {output_target}, found {data[1][1]}"
      return

    assert False, f"Unsupported list row type in output {output_target}: {type(first)}"

  assert False, f"Unsupported output data type in {output_target}: {type(data)}"


def _check_output_file(output_file, n_records=1, format=None, ext=None):
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
    check_output(data, n_records=n_records, output_file=output_file)
    return

  if format == 'csv' and ext == 'csv':
    csv_text = output_file.read_text()
    check_output(csv_text, n_records=n_records, output_file=output_file)
    return

  if ext == 'pkl':
    with output_file.open('rb') as f:
      data = pickle.load(f)
    check_output(data, n_records=n_records, output_file=output_file)
    return

  assert False, f"Unsupported format/ext combination: {format}.{ext}"


def check_equivalent(all_formats, data_type='data'):
  for format in ['csv', 'dataframe']:
    if format == 'csv':
      # Parse CSV text into list of lists.
      csv_text = all_formats[format]
      lines = csv_text.splitlines()
      all_formats[format] = [line.split(',') for line in lines]
    if format == 'dataframe':
      # Convert DataFrame to list of dicts.
      df = all_formats[format]
      all_formats[format] = df.to_dict(orient='records')

  # Compare values with JSON output.
  json_data = all_formats['json']
  for row in json_data:
    if data_type == 'data':
      for comp in ['N', 'E', 'Z']:
        # Flatten 'N', 'E', 'Z' dicts in JSON to match CSV/DataFrame structure.
        if isinstance(row[comp], dict):
          row[f"{comp}_nez"] = row[comp].get('nez')
          row[f"{comp}_geo"] = row[comp].get('geo')
          del row[comp]
    if data_type == 'indices':
      for comp in ['bgse', 'bgsm', 'vgse', 'vgsm']:
        # Flatten vector dicts in JSON to match CSV/DataFrame structure.
        if isinstance(row.get(comp), dict):
          for subkey, val in row[comp].items():
            row[f"{comp}_{subkey}"] = val
          del row[comp]

  for i, row in enumerate(all_formats[format]):
    json_row = json_data[i]
    if isinstance(row, list):
      # CSV: compare list values with JSON dict values.
      for j, key in enumerate(json_row.keys()):
        assert str(row[j]) == str(json_row[key]), f"Expected {key} value '{json_row[key]}' in row {i} of {format} output, found '{row[j]}'"
    elif isinstance(row, dict):
      # DataFrame: compare dict values with JSON dict values.
      for key in json_row.keys():
        assert str(row[key]) == str(json_row[key]), f"Expected {key} value '{json_row[key]}' in row {i} of {format} output, found '{row[key]}'"
    else:
      assert False, f"Unsupported row type in {format} output: {type(row)}"
