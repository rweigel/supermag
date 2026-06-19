from .util import logger

from .config import config
CONFIG = config()

def catalog(userid,
          start=None,
          stop=None,
          output_dir=None,
          update_inventory=False,
          update_locations=False,
          dataset=None,
          cafile=None):

  logger.info(f"Running catalog for user {userid}")
  logger.debug(f"Output directory: {output_dir}")
  logger.debug(f"Update inventory: {update_inventory}")
  logger.debug(f"Update locations: {update_locations}")
  logger.debug(f"dataset: {dataset}")

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

  inventory = inventory(userid, **kwargs)

  cadence = 'PT1M'
  catalog = []
  for entry in inventory:
    for sub_dataset in ['baseline_none', 'baseline_yearly', 'baseline_all']:
      for sub_sub_dataset in ['XYZ', 'NEZ']:

        id = f"{entry['id']}/{sub_dataset}/{cadence}/{sub_sub_dataset}"

        dataset = _dataset_template(id, entry)
        #_set_location_info(entry, dataset)

        catalog.append(dataset)

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
      'startDate': None,
      'stopDate': None,
      'cadence': cadence,
      'description': description,
      'datasetCitation': 'https://supermag.jhuapl.edu/info/?page=rulesoftheroad',
      'location': None,
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

  if station_info is not None:
    dataset['info']['additionalMetadata'] = {
      "name": "Magnetometer Station Information",
      "content": station_info,
      "contentURL": cfg['station_info_url'],
      "aboutURL": cfg['station_info_url']
    }

  return dataset


def _set_location_info(entry, dataset):

  location = entry['location']
  error_start = location['start'].get('error', None)
  error_stop = location['stop'].get('error', None)

  missing_location_warning = (
    'Use the dataset parameters glat and glon for per-record geographic location. '
    'See additionalMetadata/locationDeterminationDetails for details.'
  )

  if location['geo_location_changed'] is None:
    missing_location_warning = f"Station location metadata is not available on startDate and/or stopDate. {missing_location_warning}"
    dataset['info']['warning'] = [missing_location_warning]

  if location['geo_location_changed'] is True:
    missing_location_warning = f"Station location changed during the time period covered by this dataset. {missing_location_warning}"
    dataset['info']['warning'] = [missing_location_warning]

  if location['geo_location_changed'] is not None:
    if not error_start:
      dataset['info']['location'] = [location['start']['glat'], location['stop']['glon']]
    elif not error_stop:
      dataset['info']['location'] = [location['stop']['glat'], location['stop']['glon']]

  if location['geo_location_changed'] is not False:
    location_metadata = {
      'name': 'locationDeterminationDetails',
      'content': location
    }
    dataset['info']['additionalMetadata'].append(location_metadata)

