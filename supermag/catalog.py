from .util import logger

from .config import config
CONFIG = config()

def catalog(userid,
          start=None,
          stop=None,
          output_dir=CONFIG['common']['output_dir'],
          update_inventory=False,
          update_locations=False,
          dataset=None,
          cafile=None):

  logger.info("Generating SuperMAG HAPI catalog")

  from .inventory import inventory
  kwargs = {
    'start': start,
    'stop': stop,
    'output_dir': output_dir,
    'update_inventory': update_inventory,
    'update_locations': update_locations,
    'include_locations': True,
    'station_id': dataset,
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

        id = f"{entry['id']}/{sub_dataset}/{cadence}/{sub_sub_dataset}"

        dataset_metadata = _dataset_template(id, entry)

        catalog.append(dataset_metadata)

  return catalog


def _dataset_template(dataset_id, inventory_entry):

  def join(s):
    # Join description lines and remove leading/trailing whitespace
    return ' '.join(line.strip() for line in s.strip().splitlines())

  station_id, cadence, baseline, csys = dataset_id.split('/')

  station_info = inventory_entry.get('station', {})
  name = station_info.get('name', None)
  if name is None:
    name = ''
  else:
    name = f"({name})"

  title = f"""
  Data from magnetometer station {station_id} {name} {cadence} with baseline removal
  option '{baseline}'.
  """
  title = join(title)

  description = f"""
  {title} SuperMag ground-based magnetometer datasets have HAPI dataset IDs in the form
  IAGA_ID/CADENCE/BASELINE_OPTION/COORD_SYS, where IAGA_ID is the IAGA station
  code, CADENCE is the data cadence in ISO 8601 duration format, BASELINE_OPTION
  is the baseline removal option, and COORD_SYS is the coordinate system. 
  BASELINE_OPTION is one of 'baseline_none' (no baseline removal), 'baseline_yearly'
  (yearly trend removed), or 'baseline_all' (yearly trend and daily variation
  removed). See Gjerloev, 2012 (https://doi.org/10.1029/2012JA017683) for details. 
  COORD_SYS = 'XYZ' corresponds to geographic coordinates (X=North, Y=East, 
  Z=vertical down); 'NEZ' corresponds to local geomagnetic coordinates (N=North, 
  E=East, Z=vertical down). See https://supermag.jhuapl.edu/mag/?tab=description
  for additional details and a description of the parameters sza, decl, mcolat, 
  and mlt.
  """
  description = join(description)

  note = """
  The location given in this metadata is the first valid glat, glon of the 
  station found by requesting data on startDate. If this does not match the 
  location on the last valid glat, glon on stopDate, then this JSON response 
  will include a warning. In this case, the location of the station must be 
  obtained from the dataset parameters glat and glon.
  """
  note = join(note)

  description_field = 'Field_Vector components X, Y, and Z, correspond to the '
  if csys == 'NEZ':
    description_field += 'local geomagnetic North, East, and vertically down directions'
  elif csys == 'XYZ':
    description_field += 'geographic North, East, and vertically down directions'

  dataset = {
    'id': dataset_id,
    'title': title,
    'info': {
      'startDate': inventory_entry['startDate'],
      'stopDate': inventory_entry['stopDate'],
      'cadence': cadence,
      'description': description,
      'datasetCitation': 'https://supermag.jhuapl.edu/info/?page=rulesoftheroad',
      'maxRequestDuration': 'P1Y',
      'parameters': [
        {
          "length": 24,
          "name": "Time",
          "type": "isotime",
          "units": "UTC"
        },
        {
          "name": "Field_Vector",
          "description": description_field,
          "type": "double",
          "units": "nT",
          "fill": "999999.0",
          "size": [
            3
          ],
          "label": [
            "X",
            "Y",
            "Z"
          ]
        },
        {
          "name": "mlt",
          "type": "double",
          "units": "hours",
          "fill": None,
          "description": "magnetic local time in fractional hours"
        },
        {
          "name": "mcolat",
          "type": "double",
          "units": "degrees",
          "fill": None,
          "description": "magnetic colatitude in degrees"
        },
        {
          "name": "sza",
          "type": "double",
          "units": "degrees",
          "fill": None,
          "description": "solar zenith angle in degrees"
        },
        {
          "name": "decl",
          "type": "double",
          "units": "degrees",
          "fill": "0",
          "description": "time-averaged declination in degrees"
        },
        {
          "name": "glon",
          "type": "double",
          "units": "degrees",
          "fill": "0",
          "description": "geographic longitude in degrees"
        },
        {
          "name": "glat",
          "type": "double",
          "units": "degrees",
          "fill": "0",
          "description": "geographic latitude in degrees"
        }
      ]
    }
  }

  from .config import config
  cfg = config('inventory')

  if 'station' in inventory_entry:
    glat = inventory_entry['station'].get('glat', None)
    glon = inventory_entry['station'].get('glon', None)
    if glat is not None and glon is not None:
      dataset['info']['location'] = [glat, glon]


  additionalMetadata = []
  if station_info is not None:
    additionalMetadata.append({
      "name": "Magnetometer Station Information",
      "content": station_info,
      "contentURL": cfg['station_info_url'],
      "aboutURL": cfg['station_info_url']
    })

  location_info = inventory_entry.get('location', {})
  if location_info is not None:
    if location_info['geo_location_changed']:
      additionalMetadata.append({
        "name": "Location Details",
        "content": location_info
      })

  dataset['info']['additionalMetadata'] = additionalMetadata

  return dataset
