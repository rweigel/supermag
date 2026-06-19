import supermag
from util import userid, check_output, check_equivalent

def test_default(userid=userid):

  data, error = supermag.indices(userid, '2001-01-01T00:00:00Z', 60)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, output_type='indices', n_records=1)


def test_format(userid=userid):
  all_formats = {}
  for format in ['json', 'csv', 'dataframe', 'list']:
    data, error = supermag.indices(userid, '2001-01-01T00:00:00Z', 60, format=format)
    assert error is None, f"Expected no error in response, found: {error}"
    check_output(data, output_type='indices', n_records=1, format=format)
    all_formats[format] = data

  check_equivalent(all_formats, data_type='indices')


if __name__ == "__main__":
  import sys
  from supermag.util import logger

  logger.setLevel('DEBUG')

  args = sys.argv
  if len(args) == 2:
    test_default()
    test_format()
  else:
    print("Usage: python test_locations.py USERID")
