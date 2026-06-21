import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import supermag
from supermag.util import logger

def _run_request(request_id, userid, station_id, start, extent, use_cache, cafile):
  t0 = time.perf_counter()
  result, error = supermag.data(
    userid,
    station_id,
    start,
    extent,
    use_cache=use_cache,
    cafile=cafile,
  )
  dt = time.perf_counter() - t0

  n_rows = len(result) if isinstance(result, list) else 0
  ok = error is None
  return {
    "request_id": request_id,
    "ok": ok,
    "elapsed_s": dt,
    "n_rows": n_rows,
    "error": error,
  }


def _log_results(label, results, total_elapsed):
  n_ok = sum(1 for r in results if r["ok"])
  n_err = len(results) - n_ok
  elapsed_values = [r["elapsed_s"] for r in results]
  min_elapsed = min(elapsed_values) if elapsed_values else 0.0
  max_elapsed = max(elapsed_values) if elapsed_values else 0.0
  avg_elapsed = (sum(elapsed_values) / len(elapsed_values)) if elapsed_values else 0.0

  logger.info(
    "%s completed %s requests: ok=%s error=%s total_elapsed=%.3fs",
    label,
    len(results),
    n_ok,
    n_err,
    total_elapsed,
  )
  logger.info(
    "%s request timing: min=%.3fs avg=%.3fs max=%.3fs",
    label,
    min_elapsed,
    avg_elapsed,
    max_elapsed,
  )


def _run_serial(args, extent):
  logger.info(f"Starting {args.n_par} serial data requests")
  started = time.perf_counter()
  results = []
  for i in range(args.n_par):
    item = _run_request(i, args.userid, args.station_id, args.start, extent, args.use_cache, args.cafile)
    results.append(item)
    if item["ok"]:
      logger.info(
        "serial request=%s status=ok rows=%s elapsed=%.3fs",
        item["request_id"],
        item["n_rows"],
        item["elapsed_s"],
      )
    else:
      logger.error(
        "serial request=%s status=error elapsed=%.3fs error=%s",
        item["request_id"],
        item["elapsed_s"],
        item["error"],
      )
  total_elapsed = time.perf_counter() - started
  _log_results("Serial", results, total_elapsed)
  return total_elapsed


def _run_parallel(args, extent):
  logger.info(f"Starting {args.n_par} parallel data requests")
  started = time.perf_counter()
  results = []
  with ThreadPoolExecutor(max_workers=args.n_par) as executor:
    futures = [
      executor.submit(
        _run_request,
        i,
        args.userid,
        args.station_id,
        args.start,
        extent,
        args.use_cache,
        args.cafile,
      )
      for i in range(args.n_par)
    ]

    for future in as_completed(futures):
      item = future.result()
      results.append(item)
      if item["ok"]:
        logger.info(
          "parallel request=%s status=ok rows=%s elapsed=%.3fs",
          item["request_id"],
          item["n_rows"],
          item["elapsed_s"],
        )
      else:
        logger.error(
          "parallel request=%s status=error elapsed=%.3fs error=%s",
          item["request_id"],
          item["elapsed_s"],
          item["error"],
        )

  total_elapsed = time.perf_counter() - started
  _log_results("Parallel", results, total_elapsed)
  return total_elapsed


def main():
  parser = argparse.ArgumentParser(
    description="Run parallel one-day SuperMAG data requests and log timing/results."
  )
  parser.add_argument("--userid", required=True, help="SuperMAG user ID")
  parser.add_argument("--n-par", type=int, default=3, help="Number of parallel requests (efault: 3)")
  parser.add_argument("--station-id", default="ABK", help="Station ID (default: ABK)")
  parser.add_argument("--start", default="2001-01-01", help="Start date/time (default: 2001-01-01)")
  parser.add_argument("--ignore-cache", action="store_true", help="Ignore cache for each request")
  parser.add_argument("--cafile", default=None, help="CA bundle setting: default, none, or PEM path")
  parser.add_argument("--debug", action="store_true", help="Enable debug logging")
  args = parser.parse_args()

  if args.n_par < 1:
    raise ValueError("--n-par must be >= 1")

  if args.debug:
    logger.setLevel("DEBUG")

  extent = 24 * 60 * 60
  logger.info(
    "Params: station=%s start=%s extent=%s n_par=%s use_cache=%s",
    args.station_id,
    args.start,
    extent,
    args.n_par,
    args.use_cache,
  )

  logger.info("")
  serial_elapsed = _run_serial(args, extent)

  logger.info("")
  parallel_elapsed = _run_parallel(args, extent)

  if parallel_elapsed > 0:
    speedup = serial_elapsed / parallel_elapsed
    logger.info(
      "Summary: serial_total=%.3fs parallel_total=%.3fs speed-up(serial/parallel)=%.3fx",
      serial_elapsed,
      parallel_elapsed,
      speedup,
    )
  else:
    logger.info(
      "Summary: serial_total=%.3fs parallel_total=%.3fs speed-up(serial/parallel)=undefined (parallel elapsed is zero)",
      serial_elapsed,
      parallel_elapsed,
    )


if __name__ == "__main__":
  main()
