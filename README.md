# supermag

Alternative SuperMAG API and scripts for creating list of days where data are available for each ground magnetometer station and geographic location information.

[Sample output](http://mag.gmu.edu/git-data/supermag)

# Install

```
pip install -e supermag
```

# Examples

## `supermag-data`

```
supermag-data --help

supermag-data --userid USERID --station ABK --start 2001-01-01T00:00Z --stop 2001-01-01T00:01Z --debug

supermag-data --userid USERID --station ABK --start 2001-01-01T00:00Z --stop 2001-01-01T00:01Z --debug
```

## `supermag-inventory`

```
supermag-inventory --help

# Sample run
supermag-inventory --output-dir data --start 1970-01-01 --stop 1970-01-10 --debug

# Full run, only fetching daily inventories not found in cache.
supermag-inventory --output-dir data --debug

# Re-run, re-fetching all daily inventories.
supermag-inventory --output-dir data --update-inventory --debug
```

