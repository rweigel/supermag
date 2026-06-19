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

        cadence_str = ""
        if cadence == 'PT1M':
          cadence_str = "at 1-minute cadence"
        if cadence == 'PT1S':
          cadence_str = "at 1-second cadence"

        title = f"Data from magnetometer station {entry['id']} {cadence_str} "
        title += f"with baseline removal option '{sub_dataset}' "

        dataset = _dataset_template(id, title, cadence, sub_sub_dataset)

        #_set_location_info(entry, dataset)

        catalog.append(dataset)

  return catalog


def _dataset_template(id, title, cadence, csys):

  description = """
  Ground-based magnetometer dataset IDs have the form
  {station_id}/PT1M/{baseline_choice}/{frame}, where
  {baseline_choice} is 'baseline_none', 'baseline_yearly' (yearly trend removed),
  or 'baseline_all' (yearly trend and start value subtracted);
  see https://supermag.jhuapl.edu/mag/?fidelity=low&tab=description. {frame}
  = 'XYZ' corresponds to geographic coordinates (X=North, Y=East, Z=vertical down);
  frame = 'NEZ' corresponds to local geomagnetic coordinates
  (N=North, E=East, Z=vertical down).
  """
  # Join description lines and remove leading/trailing whitespace
  description = ' '.join(line.strip() for line in description.strip().splitlines())

  note = """
  The location given in this metadata is the first valid glat, glon of the 
  station found by requesting data on startDate. If this does not match the 
  location on the last valid glat, glon on stopDate, then this JSON response 
  will include a warning. In this case, the location of the station must be 
  obtained from the dataset parameters glat and glon.
  """
  note = ' '.join(line.strip() for line in note.strip().splitlines())

  if csys == 'NEZ':
    description = 'N_geo, E_geo, Z_geo, the local geomagnetic N, E, Z vector components'
  elif csys == 'XYZ':
    description = 'N_geo, E_geo, Z_geo, the geographic N, E, Z vector components'

  dataset = {
    'id': id,
    'title': title,
    'info': {
      'startDate': None,
      'stopDate': None,
      'cadence': cadence,
      'maxRequestDuration': 'P1Y',
      'datasetCitation': 'https://supermag.jhuapl.edu/info/?page=rulesoftheroad',
      'description': description,
      'location': None,
      'additionalMetadata': [
        {
          "name": "iaga",
          "content": None
        },
        {
          "name": "baselines",
          "contentURL": "https://supermag.jhuapl.edu/mag/?fidelity=low&tab=description",
          "content": "Subtract the daily variations and yearly trend (using Gjerloev, 2012)"
        }
      ],
      'parameters': [
        {
          "length": 24,
          "name": "Time",
          "type": "isotime",
          "units": "UTC"
        },
        {
          "name": "Field_Vector",
          "type": "double",
          "units": "nT",
          "size": [
            3
          ],
          "fill": "999999.0",
          "description": None,
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
          "description": "declination in degrees computed using the IGRF model"
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

