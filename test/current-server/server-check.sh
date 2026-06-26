# All seem to return the same as content in table at
# https://supermag.jhuapl.edu/line/?fidelity=low&tab=view&start=2000-01-01T00%3A00%3A00.000Z&interval=00%3A05&stations=ABK&baseline=all&delta=none

set -x

curl -s "https://supermag.jhuapl.edu/hapi/data?dataset=bou/baseline_all/PT1M/NEZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z"
curl -s "https://supermag.jhuapl.edu/hapi/data?dataset=bou/baseline_yearly/PT1M/NEZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z"
curl -s "https://supermag.jhuapl.edu/hapi/data?dataset=bou/baseline_none/PT1M/NEZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z"

echo "\n"

curl -s "https://supermag.jhuapl.edu/hapi/data?dataset=bou/baseline_all/PT1M/XYZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z"
curl -s "https://supermag.jhuapl.edu/hapi/data?dataset=bou/baseline_yearly/PT1M/XYZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z"
curl -s "https://supermag.jhuapl.edu/hapi/data?dataset=bou/baseline_none/PT1M/XYZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z"
