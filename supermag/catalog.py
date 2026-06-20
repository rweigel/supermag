from .util import logger

from .config import config
CONFIG = config()

def catalog(userid,
          start=None,
          stop=None,
          output_dir=CONFIG['common']['output_dir'],
          update_inventory=False,
          update_locations=False,
          dataset=None, # HAPI dataset ID to filter by
          cafile=None):

  logger.info("Generating SuperMAG HAPI catalog")

  filter = False
  if start is not None or stop is not None or dataset is not None:
    filter = True
    logger.info("  Applying filters:")
  if start is not None:
    logger.info(f"    stations with start date {start} or after")
  if stop is not None:
    logger.info(f"    stations with stop date {stop} or before")
  if dataset is not None:
    logger.info(f"    datasets with HAPI ID that starts with {dataset}")

  station_id = dataset.split('/')[0] if dataset else None

  from .inventory import inventory
  kwargs = {
    'start': start,
    'stop': stop,
    'output_dir': output_dir,
    'update_inventory': update_inventory,
    'update_locations': update_locations,
    'include_locations': True,
    'station_id': station_id,
    'cafile': cafile
  }

  logger.info("Getting inventory")
  inventory = inventory(userid, **kwargs)

  logger.info("Building catalog from inventory")
  cadence = 'PT1M'
  catalog = []
  for entry in inventory:
    for sub_dataset in ['baseline_none', 'baseline_yearly', 'baseline_all']:
      for sub_sub_dataset in ['XYZ', 'NEZ']:

        dataset_id = f"{entry['id']}/{sub_dataset}/{cadence}/{sub_sub_dataset}"

        # Keep only the metadata for the requested dataset or any dataset that
        # starts with the requested dataset.
        if dataset and dataset_id != dataset:
          if not dataset_id.startswith(dataset):
            continue

        dataset_metadata = _dataset_template(dataset_id, entry)

        catalog.append(dataset_metadata)

  logger.info(f"Built catalog with {len(catalog)} datasets from {len(inventory)} magnetometer stations")
  if len(catalog) == 0:
    if filter:
      logger.warning("No HAPI datasets found given the start, stop, and dataset filters")
    else:
      raise ValueError("No HAPI datasets found")

  kwargs = {
    'start': start,
    'stop': stop,
    'station_id': station_id,
    'partial_inventory': filter,
    'file_type': 'catalog'
  }
  from .util import write_files
  write_files(catalog, output_dir, **kwargs)

  return catalog


def _dataset_template(dataset_id, inventory_entry):

  import json
  import pathlib

  # Read catalog.mag.json from the dir of this script
  _catalog_file = pathlib.Path(__file__).parent / 'catalog.mag.json'
  with open(_catalog_file) as f:
    dataset = json.load(f)


  station_id, cadence, baseline, csys = dataset_id.split('/')

  station_info = inventory_entry.get('station', {})
  station_name = station_info.get('name', None)
  if station_name is None:
    station_name = ''
  else:
    station_name = f"({station_name})"


  # Populate dataset metadata with the dataset ID, title, and inventory information
  dataset['id'] = dataset_id
  dataset['title'] = dataset['title'].format(station_id=station_id, station_name=station_name, cadence=cadence, baseline=baseline)
  dataset['info']['startDate'] = inventory_entry["startDate"]
  dataset['info']['stopDate'] = inventory_entry["stopDate"]
  dataset['info']['cadence'] = cadence
  dataset['info']['description'] = dataset['info']['description'].format(title=dataset['title'])


  # Update the Field_Vector description based on the coordinate system
  Field_Vector = dataset['info']['parameters'][1]
  if csys == 'XYZ':
    Field_Vector['description'] =Field_Vector['description_XYZ']
  elif csys == 'NEZ':
    Field_Vector['description'] = Field_Vector['description_NEZ']
  del Field_Vector['description_XYZ']
  del Field_Vector['description_NEZ']


  # Add geographic location information
  if 'station' in inventory_entry:
    glat = inventory_entry['station'].get('glat', None)
    glon = inventory_entry['station'].get('glon', None)
    if glat is not None and glon is not None:
      dataset['info']['location'] = [glat, glon]
    else:
      del dataset['info']['location']

  # Add additional metadata
  additionalMetadata = []
  if station_info is not None:
    additionalMetadata.append({
      "name": "Magnetometer Station Information",
      "content": station_info,
      "contentURL": CONFIG['inventory']['station_info_url'],
      "aboutURL": CONFIG['inventory']['station_info_url_desc']
    })

  # Add additional location metadata
  location_info = inventory_entry.get('location', {})
  if location_info is not None:
    additionalMetadata.append({
      "name": "Location Details",
      "content": location_info
    })

  dataset['info']['additionalMetadata'] = additionalMetadata

  return dataset
