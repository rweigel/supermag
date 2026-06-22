# Usage:
#   pytest test_indices.py --userid USERID
#   python test_indices.py --userid USERID
import supermag
from util import userid, check_output, check_equivalent

def test_default(userid=userid):

  data, error = supermag.indices(userid, '2001-01-01T00:00:00Z', 60)
  assert error is None, f"Expected no error in response, found: {error}"
  check_output(data, dataset_type='indices', n_records=1)


def test_format(userid=userid):
  all_formats = {}
  for format in ['json', 'csv', 'dataframe']:
    data, error = supermag.indices(userid, '2001-01-01T00:00:00Z', 60, format=format)
    assert error is None, f"Expected no error in response, found: {error}"
    check_output(data, dataset_type='indices', n_records=1, format=format)
    all_formats[format] = data

  check_equivalent(all_formats, dataset_type='indices')


if __name__ == "__main__":
  from util import parse_args
  args = parse_args()
  test_default(userid=args.userid)
  test_format(userid=args.userid)
