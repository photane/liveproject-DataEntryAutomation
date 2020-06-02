from pathlib import Path

def getfileslist(directory, suffix = '.*'):
  """Returns list of Path objects contained within directory and its subdirectories

  Parameters:
    directory (str or Path OBJECT): Topmost directory to search
    suffix (str): filter by desired suffix (begin with '.'). If not specified, return all files.
  Returns:
    list of Path objects

   """
  path = Path(directory)
  fileslist = list(path.rglob(f'*{suffix}'))
  return fileslist
