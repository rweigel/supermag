The following are notes on issues encountered split by whether they are relevant to the HAPI server.

# Error Conditions

On 2026-06-27, I was getting `failed to fork /drive/...` for either inventory requests or a request for the [station list](https://supermag.jhuapl.edu/lib/services/?service=stations&fmt=json) (it started working before I could write down the drive path it gave and I don't recall if it was an inventory request or a station list request that triggered the error). At that time, data requests failed and the response was an empty body. We are using a search for the string `ERROR` in the data responses. Wit this new case, we also need to infer that an empty string means server-side error and not conclude that there is not data in the requested interval (which usually results in a response of `[]`).

I suggest also using `HTTP 5xx` or `HTTP 4xx` response codes in the headers. When detected, we can look in the body to determine the actual error message reliably.

# Relevant to HAPI server

## Inventory not Consistent with Station List

The [station list](https://supermag.jhuapl.edu/lib/services/?service=stations&fmt=json) returns more stations than in the combined station list found by making inventory requests on each day from 1970-01-01 through tomorrow.

See [stations.error.log](http://mag.gmu.edu/git-data/supermag/supermag-data/stations/station.error.log).

## Wrong start

Many stations don't return data on the [start or stop day reported](https://supermag.jhuapl.edu/lib/services/?service=stations&fmt=json). See [samples.json](http://mag.gmu.edu/git-data/supermag/supermag-data/inventory/samples.json) and search on "error". Some stations don't have data 7 days after the reported start or seven days before the reported end; Search on "No data".

And when I try the reported start date at
https://supermag.jhuapl.edu/line/?fidelity=low&start=2005-08-31T00%3A00%3A00.000Z&interval=1%3A00%3A00&tab=view&stations=T40, I get a spinner that never stops.

We've worked around this by making requests to find the first day when the web service API returns data.

## Problem with Indices

We've discussed before the fact that there is an issue with the current HAPI server and indices. In the revised metadata, there is a dataset called `indices` that has all indices. There is no split and the `indices_X` datasets have been removed as they were redundant and sometimes returning invalid data.

## Current HAPI server ignoring baseline option

The current HAPI server returns the same values independent of baseline. The values returned in all cases is the same result as that shown in the [table at SuperMAG](https://supermag.jhuapl.edu/line/?fidelity=low&tab=view&start=2000-01-01T00%3A00%3A00.000Z&interval=00%3A05&stations=ABK&baseline=all&delta=none) with only `Subtract baseline` selected (`baseline=all&delta=none`).

```bash
+ curl 'https://supermag.jhuapl.edu/hapi/data?dataset=abk/baseline_all/PT1M/NEZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z'
2000-01-01T00:00Z,-426.149872,180.963715,207.97319
2000-01-01T00:01Z,-450.025208,185.115631,195.927826
2000-01-01T00:02Z,-489.731628,156.48819,192.88147
2000-01-01T00:03Z,-437.29361,161.186615,232.834045
2000-01-01T00:04Z,-381.191345,173.60228,222.785568
+ curl 'https://supermag.jhuapl.edu/hapi/data?dataset=abk/baseline_yearly/PT1M/NEZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z'
2000-01-01T00:00Z,-426.149872,180.963715,207.97319
2000-01-01T00:01Z,-450.025208,185.115631,195.927826
2000-01-01T00:02Z,-489.731628,156.48819,192.88147
2000-01-01T00:03Z,-437.29361,161.186615,232.834045
2000-01-01T00:04Z,-381.191345,173.60228,222.785568
+ curl 'https://supermag.jhuapl.edu/hapi/data?dataset=abk/baseline_none/PT1M/NEZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z'
2000-01-01T00:00Z,-426.149872,180.963715,207.97319
2000-01-01T00:01Z,-450.025208,185.115631,195.927826
2000-01-01T00:02Z,-489.731628,156.48819,192.88147
2000-01-01T00:03Z,-437.29361,161.186615,232.834045
2000-01-01T00:04Z,-381.191345,173.60228,222.785568

+ curl 'https://supermag.jhuapl.edu/hapi/data?dataset=abk/baseline_all/PT1M/XYZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z'
2000-01-01T00:00Z,-440.024603,143.978916,207.97319
2000-01-01T00:01Z,-464.166958,146.080524,195.927826
2000-01-01T00:02Z,-501.288578,114.172601,192.88147
2000-01-01T00:03Z,-449.441928,123.323879,232.834045
2000-01-01T00:04Z,-394.602207,140.476657,222.785568
+ curl 'https://supermag.jhuapl.edu/hapi/data?dataset=abk/baseline_yearly/PT1M/XYZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z'
2000-01-01T00:00Z,-440.024603,143.978916,207.97319
2000-01-01T00:01Z,-464.166958,146.080524,195.927826
2000-01-01T00:02Z,-501.288578,114.172601,192.88147
2000-01-01T00:03Z,-449.441928,123.323879,232.834045
2000-01-01T00:04Z,-394.602207,140.476657,222.785568
+ curl 'https://supermag.jhuapl.edu/hapi/data?dataset=abk/baseline_none/PT1M/XYZ&parameters=Field_Vector&start=2000-01-01T00:00:00Z&stop=2000-01-01T00:05:00Z'
2000-01-01T00:00Z,-440.024603,143.978916,207.97319
2000-01-01T00:01Z,-464.166958,146.080524,195.927826
2000-01-01T00:02Z,-501.288578,114.172601,192.88147
2000-01-01T00:03Z,-449.441928,123.323879,232.834045
2000-01-01T00:04Z,-394.602207,140.476657,222.785568
```

Due to this, I suggest we use in the new server dataset IDs of the form

* `ABK/PT1M/NEZ` (baseline = none, delta=none)
* `ABK/PT1M/XYZ` (baseline = none, delta=none)
* `ABK/baseline_all/NEZ` (baseline = all, delta=none)
* `ABK/baseline_all/XYZ` (baseline = all, delta=none)
* `ABK/baseline_yearly/NEZ` (baseline = all, delta=none)
* `ABK/baseline_yearly/XYZ` (baseline = all, delta=none)

With the above, only responses for the last two will change from the current HAPI server. The first two correspond to no baseline removal (and no delta). The shorter name is consistent with INTERMAGNET and WDC, who use this form for the un-modified magnetic field measurements. We will remove

* `ABK/baseline_none/NEZ`
* `ABK/baseline_none/XYZ`

and users will get an error instead of wrong data if they try it.

## Max Request Extent

The current HAPI server has the max request duration set at one year, but I find it to be about 97 days.

## Geographic Location Precision and Changes

### Precision

We had some error tests that failed because the [response for the station list](https://supermag.jhuapl.edu/lib/services/?service=stations&fmt=json), e.g.,

```json
"station": {
  "name": "Dumont Durville",
  "operator": [
    "INTERMAGNET",
    "BCMT"
  ],
  "glat": -66.67,
  "glon": 140.01
}
```

has `glat` and `glon` to two decimal places (corresponding to a precision of ~1 km on Earth's surface) but the data has six (corresponding to ~10 cm)

```json
"data": {
  "tval": 0.0,
  "ext": 60.0,
  "iaga": "DRV",
  "glon": 140.009995,
  "glat": -66.669998,
  "mlt": null,
  "mcolat": 90.0,
  "decl": 180.0,
  ...
```

We've changed the comparison to check that the data values rounded to two decimal places match the station list information. Even with this, there are some mismatches. Search on `"firstRecordMatchesReported": false` in (http://mag.gmu.edu/git-data/supermag/supermag-data/inventory/samples.json).

We've also found cases where the values for `glat` and `glon` in the first record on the start date does not exactly match that in the last record on the stop date. Search on `"firstRecordMatchesLast": false` in (http://mag.gmu.edu/git-data/supermag/supermag-data/inventory/samples.json). The maximum difference corresponds to a change in location of ~3.7 km. This won't matter for most purposes, but in the past I have given presentations where I include a Google Maps image of the location of an ground magnetometer or GIC instrument and having an accurate location was useful.

### Changes

## The word "indice"

The term "indice" is used in the client software as the singular form of "indices". It [is archaic](https://books.google.com/ngrams/graph?content=index%2Cindice&year_start=1800&year_end=2022&corpus=en&smoothing=3), and the people who derived geomagnetic indices (going back at least to [Mayaud](https://isgi.unistra.fr/Documents/References/Mayaud_GMS_1980.pdf)) used "index" or "indices", but not "indice".

In the revised HAPI metadata, I've used index, but may change back to be consistent. I am not sure if it is better to have the expected word or to be consistent with the terminology used in the SuperMAG clients.

## Inconsistent Responses

This request returns no data at `tval=0.0` (1970-01-01T00:00:00.0Z)

https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=1970-01-01&extent=60&station=DRV&delta=none&baseline=none&mlt&geo&decl&sza&logon=USERID

Same if `extent=600`. If `extent=660`, data are returned:

https://supermag.jhuapl.edu/services/data-api.php?python&nohead&start=1970-01-01&extent=660&station=DRV&delta=none&baseline=none&mlt&geo&decl&sza&logon=USERID

Some servers also do this, but it is not recommended because it is somewhat unexpected. The HAPI server will reproduce this behavior and it is not a major issue. However, it may be associated with a subtle bug somewhere deep in the server code.

## Question about `mlt`

For the HAPI metadata, we need to know the correct fill values.

curl "https://supermag.jhuapl.edu/services/data-api.php?python&nohead&logon=superhapi&start=1979-01-01&extent=86400&station=ABK&start=1979-01-01&extent=86400&baseline=none&delta=none&mlt&geo&decl&sza"

I see
```
"mlt": null, "mcolat": 90.0, "decl": 180.0
```

Is `mlt=null` the fill value that is always used? Similar question for `mcolat` and `decl` (but see above for the fact that sometimes `decl=0.0` seems to be used as fill).

The current HAPI server does not return any data for this time interval

* https://supermag.jhuapl.edu/hapi/data?dataset=abk/baseline_none/PT1M/XYZ&parameters=Field_Vector,mlt&start=1979-01-01T00:00Z&stop=1980-01-02T00:00Z"

* https://supermag.jhuapl.edu/hapi/data?dataset=abk/baseline_none/PT1M/NEZ&parameters=Field_Vector,mlt&start=1979-01-01T00:00Z&stop=1980-01-02T00:00Z

I suspect it is due to not handling the `null`.

## Question about `decl`

At https://supermag.jhuapl.edu/line/?fidelity=low&start=1970-01-01T00%3A00%3A00.000Z&interval=1%3A00%3A00&stations=PAF&tab=view decl `decl` is often 0 or 180 when the magnetic field data are fill values, but not always, e.g., at 00:32. 

The IDL and Python client documentation states, "The Declination from IGRF Model ..." However, https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2012JA017683 describes a derivation of declination from the individual station data, not from IGRF (see Equation 2). The fact that decl is often 0 or 180 when the field values are filled suggests that when there is no field data, the individual station data are used for computing decl rather than the IGRF (otherwise, the 0 or 180 fill would not be needed because the IGRF model just needs a time and geographic location). Also declination is usually defined as the angle between local magnetic north and geographic north, not IGRF magnetic north.

For the HAPI metadata, we would like to provide the correct definition of `decl`.

## Question about `MLAT`

At 
https://supermag.jhuapl.edu/line/?fidelity=low&start=2005-07-01T00%3A00%3A00.000Z&interval=1%3A00%3A00&tab=view&stations=ABK

I see 65.35 for MLAT. In the data, e.g.,

https://supermag.jhuapl.edu/line/?fidelity=low&start=2005-07-01T00%3A00%3A00.000Z&interval=1%3A00%3A00&tab=view&stations=ABK

I see

```
MCOLAT = 24.65 (MLAT=65.35) on 2005-01-01T00:00Z
MCOLAT = 24.61 (MLAT=65.39) on 2005-07-01T00:00Z
MCOLAT = 27.52 (MLAT=62.48) on 2005-12-31T00:00Z.
```

So is the MLAT in [the table](https://supermag.jhuapl.edu/line/?fidelity=low&start=2005-07-01T00%3A00%3A00.000Z&interval=1%3A00%3A00&tab=view&stations=ABK) the AACGM MLAT on 2005-01-01T00:00Z and MLAT in the data the MLAT computed using the AACGM model?

# Not relevant to HAPI server

## Meaning of "Do Not Remove Daily Baseline"

In [the table](https://supermag.jhuapl.edu/line/?fidelity=low&tab=view&start=2000-01-01T00%3A00%3A00.000Z&interval=00%3A05&stations=ABK&baseline=yearly&delta=none), selecting "Do Not Remove Daily Baseline" results in `baseline=yearly` showing up in the URL.

This is confusing because it says what is not going to be done and the user has to infer that it means "remove only the yearly baseline".

In the IDL client documentation, it is clearer what the options on the web page mean:

```
"all" (default)	Subtract both the daily and yearly NEZ baselines
"yearly"	Subtract the yearly NEZ baseline, but do not subtract the daily NEZ baseline
"none"	Do not subtract either the yearly or the daily NEZ baseline
```


## `delta=median` Option

With the web service API, it does not appear that with `baseline=none`, one can subtract the median baseline. When "Do Not Remove Any Baseline" is selected on the table: https://supermag.jhuapl.edu/line/?fidelity=low&start=1970-01-01T00%3A00%3A00.000Z&interval=1%3A00%3A00&stations=PAF&tab=view&baseline=none&delta=median, there is a `delta=median` in the URL. With the web service API, one can set `delta=none` or `delta=start`, but not `delta=median`.

## Issues with `decl`

At https://supermag.jhuapl.edu/line/?fidelity=low&start=1970-01-01T00%3A00%3A00.000Z&interval=1%3A00%3A00&stations=PAF&tab=view decl `decl` is often 0 or 180 when the magnetic field data are fill values, but not always, e.g., at 00:32. 

The IDL and Python client documentation states, "The Declination from IGRF Model ..." However, https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2012JA017683 describes a derivation of declination from the individual station data, not from IGRF. The fact that decl is often 0 or 180 when the field values are filled suggests that when there is no field data, the individual station data are used for computing decl rather than the IGRF (otherwise, the 0 or 180 fill would not be needed because the IGRF model just needs a time and geographic location).

## `SME.MLT` on SuperMAG site

I can plot SME.MLT
https://supermag.jhuapl.edu/indices/?fidelity=low&layers=SME.MLT&start=2001-01-01T00%3A00%3A00.000Z&step=60&tab=plot

but not view it in the table

https://supermag.jhuapl.edu/indices/?fidelity=low&layers=SME.MLT&start=2001-01-01T00%3A00%3A00.000Z&step=60&tab=view

