The following are notes on issues encountered split by whether they are relevant to the HAPI server.

# Relevant to HAPI server

## Wrong start

## Problem with Indices

We've discussed before the fact that there is an issue with the server and indices. In the revised metadata, there is a dataset called `indices` that has all indices. There is no split.

## Current HAPI server ignoring baseline option

The current server returns the same values independent of baseline, which is the same result as shown in the [table at SuperMAG](https://supermag.jhuapl.edu/line/?fidelity=low&tab=view&start=2000-01-01T00%3A00%3A00.000Z&interval=00%3A05&stations=ABK&baseline=all&delta=none) with `Subtract baseline` selected (`baseline=all&delta=none`).

```
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

Due to this, I suggest we use in the new server

* `ABK/PT1M/NEZ` (baseline = none, delta=none)
* `ABK/PT1M/XYZ` (baseline = none, delta=none)
* `ABK/baseline_all/NEZ` (baseline = all, delta=none)
* `ABK/baseline_all/XYZ` (baseline = all, delta=none)
* `ABK/baseline_yearly/NEZ` (baseline = all, delta=none)
* `ABK/baseline_yearly/XYZ` (baseline = all, delta=none)

With the above, only responses for the last two will change. The first two correspond to no baseline removal (and no delta). The shorter name is consistent with INTERMAGNET and WDC, who use this form for the un-modified magnetic field measurements. We will remove

* `ABK/baseline_none/NEZ`
* `ABK/baseline_none/XYZ`

and users will get an error instead of wrong data if they try it.

## Max Request Extent

Sandy had the max request duration set at one year. But I find it to be about 97 days.

## Location Changes

## The word "indice"

The term "indice" is used in the client software as the singular form of "indices". It [is archaic](https://books.google.com/ngrams/graph?content=index%2Cindice&year_start=1800&year_end=2022&corpus=en&smoothing=3), and the people who derived geomagnetic indices (going back at least to [Mayaud](https://isgi.unistra.fr/Documents/References/Mayaud_GMS_1980.pdf)) used "index" or "indices", but not "indice".

In the revised HAPI metadata, I've used index, but may change back to be consistent.

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

## Issues with `decl`

At https://supermag.jhuapl.edu/line/?fidelity=low&start=1970-01-01T00%3A00%3A00.000Z&interval=1%3A00%3A00&stations=PAF&tab=view decl `decl` is often 0 or 180 when the magnetic field data are fill values, but not always, e.g., at 00:32. 

The IDL and Python client documentation states, "The Declination from IGRF Model ..." However, https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2012JA017683 describes a derivation of declination from the individual station data, not from IGRF. The fact that decl is often 0 or 180 when the field values are filled suggests that when there is no field data, the individual station data are used for computing decl rather than the IGRF (otherwise, the 0 or 180 fill would not be needed because the IGRF model just needs a time and geographic location).

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

