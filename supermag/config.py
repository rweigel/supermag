def config(what=None):
  import json
  from pathlib import Path

  config_path = Path(__file__).parent / 'config.json'
  try:
    with open(config_path) as f:
      config = json.load(f)
  except Exception as e:
    raise RuntimeError(f"Failed to load config from {config_path}: {e}")

  if what is None:
    return config

  if what not in config:
    raise ValueError(f"Config section '{what}' not found in {config_path}")

  return config[what]