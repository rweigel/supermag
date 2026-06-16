import logging


LOG_FORMAT = '%(name)s: %(message)s'


def path_relative_to_cwd(path):
  import os
  from pathlib import Path
  return Path(os.path.relpath(Path(path).resolve(), Path.cwd()))


def check_userid(userid):
  if not userid:
    raise ValueError("SuperMAG user id is required")

  if userid == 'USERID':
    raise ValueError("Provide a valid SuperMAG user id instead of the placeholder 'USERID'")


def configure_logging(name, level=logging.DEBUG, format_string=LOG_FORMAT):
  logging.basicConfig(level=level, format=format_string)
  logger = logging.getLogger(name)
  logger.setLevel(level)
  return logger


def set_logging_level(level, logger_names=None):
  logging.getLogger().setLevel(level)
  if logger_names is None:
    return

  for logger_name in logger_names:
    logging.getLogger(logger_name).setLevel(level)
