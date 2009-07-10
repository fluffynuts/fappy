import sys
if len(sys.argv) == 1:
  sys.argv.append("py2exe")
from distutils.core import setup
import py2exe
import glob
opts = {
    "py2exe": {
        "compressed": 1,
        "bundle_files" : 1,
        "optimize": 2,
        "dll_excludes": "w9xpopen.exe",
      }
    }
setup(name = "fappy", 
      description = "Fast Audio Playlist generator in PYthon", 
      version="0.9", 
      zipfile=None,
      console= [{"script":"fappy.py"}], options = opts)

