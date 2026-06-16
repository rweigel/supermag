def config(what):
  import json
  from pathlib import Path

  config_path = Path(__file__).parent / 'config.json'
  with open(config_path) as f:
    config = json.load(f)

  if what not in config:
    raise ValueError(f"Config section '{what}' not found in {config_path}")

  return config[what]