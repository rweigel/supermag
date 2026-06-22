import json
import pickle

# First tval and tval_iso in test data response.
tval_iso = '2001-01-01T00:00Z'
tval = 978307200.0  # Jan 1, 2001

userid = None

def check_output(data,
                n_records=1,
                dataset_type='mag',
                format="json",
                output_target="response"):

  import supermag

  CONFIG = supermag.config('data')

  keys_raw = CONFIG[dataset_type]['response_parameters']
  if dataset_type == 'indices':
    keys_csv = keys_raw.copy()
    # Replace vector fields in place with component names
    for vector in ['bgse', 'bgsm', 'vgse', 'vgsm']:
      idx = keys_csv.index(vector)
      keys_csv[idx:idx+1] = [f"{vector}_X", f"{vector}_Y", f"{vector}_Z"]
  else:
    keys_csv = [key for key in keys_raw if key not in ['N', 'E', 'Z']]
    keys_csv += ['N_nez', 'N_geo', 'E_nez', 'E_geo', 'Z_nez', 'Z_geo']

  if format == 'csv-hapi':
    keys_csv = ['Time'] + [key for key in keys_csv if key not in ['tval']]
  if format == 'csv-hapi-noheader':
    keys_csv = ['Time'] + [key for key in keys_csv if key not in ['tval']]

  keys_df = ['tval_datetime', 'tval_iso'] + keys_csv

  # Raw JSON format
  if format == 'json':
    # Raw JSON format
    assert len(data) == n_records, f"Expected {n_records} row(s) in output {output_target}, found {len(data)}"
    assert list(data[0].keys()) == keys_raw, f"Expected JSON keys {keys_raw} in output {output_target}, found {list(data[0].keys())}"
    assert data[0]['tval'] == tval, f"Expected tval {tval} in first row of output {output_target}, found {data[0]['tval']}"

  # Dataframe
  if format == 'dataframe':
    assert list(data.columns) == keys_df, f"Expected DataFrame columns {keys_df} in output {output_target}, found {list(data.columns)}"
    assert len(data) == n_records, f"Expected {n_records} row(s) in output {output_target}, found {len(data)}"
    assert data.iloc[0]['tval_iso'] == tval_iso, f"Expected tval_iso {tval_iso} in first row of output {output_target}, found {data.iloc[0]['tval_iso']}"
    assert data.iloc[0]['tval'] == tval, f"Expected tval {tval} in first row of output {output_target}, found {data.iloc[0]['tval']}"

  # CSV
  if format.startswith('csv'):
    lines = [line for line in data.splitlines() if line]
    if format == 'csv-hapi-noheader':
      assert len(lines) == n_records, f"Expected {n_records} row(s) in output {output_target}, found {len(lines)} lines"
      data1 = lines[0].split(',')
    else:
      assert len(lines) == n_records + 1, f"Expected header + 1 row in output {output_target}, found {len(lines)} lines"
      assert lines[0].split(',') == keys_csv, f"Expected CSV header keys {keys_csv} in output {output_target}, found {lines[0].split(',')}"
      data1 = lines[1].split(',')

    if format.startswith('csv-hapi'):
      assert data1[0] == str(tval_iso), f"Expected first CSV data line to start with '{tval_iso},', found {data1[0]}"
    else:
      assert data1[0] == str(tval), f"Expected first CSV data line to start with '{tval},', found {data1[0]}"


def _check_output_file(output_file, n_records=1, dataset_type='mag', format=None, ext=None):
  assert output_file.is_file(), f"Output file not found: {output_file}"

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

  kwargs = {
    'n_records': n_records,
    'dataset_type': dataset_type,
    'output_target': output_file,
  }
  if format == 'json' and ext == 'json':
    with output_file.open('r') as f:
      data = json.load(f)

  if format == 'csv' and ext == 'csv':
    data = output_file.read_text()

  if ext == 'pkl':
    with output_file.open('rb') as f:
      data = pickle.load(f)

  check_output(data, **kwargs, format=format)


def check_equivalent(all_formats, dataset_type='mag'):
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
    if dataset_type == 'mag':
      for comp in ['N', 'E', 'Z']:
        # Flatten 'N', 'E', 'Z' dicts in JSON to match CSV/DataFrame structure.
        if isinstance(row[comp], dict):
          row[f"{comp}_nez"] = row[comp].get('nez')
          row[f"{comp}_geo"] = row[comp].get('geo')
          del row[comp]
    if dataset_type == 'indices':
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


def parse_args():
  import argparse

  from supermag.util import logger

  logger.setLevel('DEBUG')

  parser = argparse.ArgumentParser()
  parser.add_argument('--userid', required=True, help='SuperMAG user ID (required).')
  args = parser.parse_args()

  return args
