import sys
import pathlib
import tempfile
import subprocess

from util import _check_output_file, userid

# pytest -v -s test/test_cli.py

base_cmd = [sys.executable, '-m', 'supermag.data']

tmpdir = tempfile.gettempdir()

def test_help():

  cmd = base_cmd + ['--help']
  _run_test_command(cmd)


def test_default():
  output_file = pathlib.Path(tmpdir) / 'test_default.json'
  _remove(output_file)

  cmd = base_cmd + [
          '--userid', userid,
          '--output-file', str(output_file),
          '--ignore-cache'
         ]
  _run_test_command(cmd)
  _check_output_file(output_file, format='json', ext='json', n_records=1)
  _remove(output_file)


def test_format():

  for format in ['json', 'csv', 'dataframe', 'list']:
    ext = ""
    if format == 'json':
      ext = 'json'
    elif format == 'csv':
      ext = 'csv'
    else:
      ext = 'pkl'

    output_file = pathlib.Path(tmpdir) / f'test_format.{format}.{ext}'
    _remove(output_file)

    cmd = base_cmd + [
            '--userid', 'superhapi',
            '--format', format,
            '--output-file', str(output_file),
            '--ignore-cache'
          ]

    _run_test_command(cmd)
    _check_output_file(output_file, format=format, ext=ext, n_records=1)
    _remove(output_file)


def _remove(file_path):
  if file_path.exists():
    file_path.unlink()


def _run_test_command(cmd):
  print(f"Testing {' '.join(cmd)}")
  result = subprocess.run(cmd, capture_output=True, text=True)
  assert result.returncode == 0, result.stderr


if __name__ == '__main__':
  test_help()
  test_default()
  test_format()