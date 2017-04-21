#!/usr/bin/env python
#
# test tool for PostgreSQL Commitfest website
#
# written by: Andreas Scherbaum <ads@pgug.de>
#

import re
import os
import sys
import logging
import tempfile
import atexit
import shutil
import time
import subprocess
from subprocess import Popen
import socket
import sqlite3
import datetime
from time import gmtime, localtime, strftime
# config functions
from config import Config
import copy


# start with 'info', can be overriden by '-q' later on
logging.basicConfig(level = logging.INFO,
		    format = '%(levelname)s: %(message)s')


# exit_handler()
#
# exit handler, called upon exit of the script
# main job: remove the temp directory
#
# parameters:
#  none
# return:
#  none
def exit_handler():
    # do something in the end ...
    pass

# register exit handler
atexit.register(exit_handler)



#######################################################################
# main code



# config todo:
# * test technology (Docker, LXC, ...)


config = Config()
config.parse_parameters()
config.load_config()
config.build_and_verify_config()


# by now the lockfile is acquired, there is no other instance running
# before starting new jobs, cleanup remaining old ones

# startup
config.cleanup_old_dirs_and_files()



# main mode



