#
#
#
import os, sys
import bauble.utils as utils

def main_dir():
   if utils.main_is_frozen():
       dir = os.path.dirname(sys.executable)
   else: dir = os.path.dirname(sys.argv[0])
   if dir == "": 
       dir = os.curdir
   return dir


def lib_dir():
    if utils.main_is_frozen():
       dir = main_dir() + os.sep + 'bauble'
    else:
        dir = os.path.dirname(__file__)
    return dir
