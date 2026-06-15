import sys
import pathlib
import tempfile
import subprocess

# pytest -v -s test/test_cli.py

base_cmd = [sys.executable, '-m', 'supermag.data']

tmpdir = tempfile.gettempdir()

def _remove(file_path):
  if file_path.exists():
    file_path.unlink()

def test_help():

  cmd = base_cmd + ['--help']
  print(f"Testing {' '.join(cmd)}")
  result = subprocess.run(cmd, capture_output=True, text=True)
  assert result.returncode == 0, result.stderr
  assert "Fetch SuperMAG station data via data()" in result.stdout

def test_default():
  output_file = pathlib.Path(tmpdir) / 'test_output.json'
  cmd = base_cmd + [
          '--userid', 'superhapi',
          '--output-file', str(output_file),
         ]
  print(f"Testing {' '.join(cmd)}")
  result = subprocess.run(cmd, capture_output=True, text=True)
  assert result.returncode == 0, result.stderr
  # Read json file to verify it was created and is valid JSON
  assert output_file.is_file(), f"Expected output file not found: {output_file}"
  try:
    import json
    with output_file.open('r') as f:
      data = json.load(f)
  except Exception as error:
    assert False, f"Failed to read output JSON file: {error}"


  assert len(data) == 1, f"Expected one row in output file {output_file}, found {len(data)}"

  assert data[0]['tval'] == 978307200.0, f"Expected tval 978307200.0 in first row of output file {output_file}, found {data[0]['tval']}"

  _remove(output_file)

if __name__ == '__main__':
  test_help()
  test_default()