import re
import os
import sys
import shutil
import subprocess
import argparse
import yaml
import logging
import hashlib
import string
import atexit
from lockfile import LockFile, LockTimeout
from subprocess import Popen
from distutils.version import LooseVersion
if sys.version_info[0] < 3:
    reload(sys)
    sys.setdefaultencoding('utf8')


class Config:

    def __init__(self):
        self.__cmdline_read = 0
        self.__configfile_read = 0
        self.__fully_initiated = 0
        self.arguments = False
        self.argument_parser = False
        self.configfile = False
        self.config = False
        self.output_help = True
        self.lockfile_handle = False
        self.lockfile_name = False

        if (os.environ.get('HOME') is None):
            logging.error("$HOME is not set!")
            sys.exit(1)
        if (os.path.isdir(os.environ.get('HOME')) is False):
            logging.error("$HOME does not point to a directory!")
            sys.exit(1)

        atexit.register(self.exit_handler)



    def exit_handler(self):
        if (self.__fully_initiated == 1 and self.lockfile_name is not False):
            if (hasattr(self.lockfile_handle, 'release') is True):
                self.lockfile_handle.release()
                logging.debug("lock on " + self.lockfile_name + " released")



    # config_help()
    #
    # flag if help shall be printed
    #
    # parameter:
    #  - self
    #  - True/False
    # return:
    #  none
    def config_help(self, config):
        if (config is False or config is True):
            self.output_help = config
        else:
            print("")
            print("invalid setting for config_help()")
            sys.exit(1)



    # print_help()
    #
    # print the help
    #
    # parameter:
    #  - self
    # return:
    #  none
    def print_help(self):
        if (self.output_help is True):
            self.argument_parser.print_help()



    # parse_parameters()
    #
    # parse commandline parameters, fill in array with arguments
    #
    # parameter:
    #  - self
    # return:
    #  none
    def parse_parameters(self):
        parser = argparse.ArgumentParser(description = 'PostgreSQL Commitfest Test Tool',
                                         epilog = 'For questions, please see http://postgresql.org/',
                                         add_help = False)
        self.argument_parser = parser
        parser.add_argument('--help', default = False, dest = 'help', action = 'store_true', help = 'show this help')
        parser.add_argument('-c', '--config', default = '', dest = 'config', help = 'configuration file')
        # store_true: store "True" if specified, otherwise store "False"
        # store_false: store "False" if specified, otherwise store "True"
        parser.add_argument('-v', '--verbose', default = False, dest = 'verbose', action = 'store_true', help = 'be more verbose')
        parser.add_argument('-q', '--quiet', default = False, dest = 'quiet', action = 'store_true', help = 'run quietly')


        # parse parameters
        args = parser.parse_args()

        if (args.help is True):
            self.print_help()
            sys.exit(0)

        if (args.verbose is True and args.quiet is True):
            self.print_help()
            print("")
            print("Error: --verbose and --quiet can't be set at the same time")
            sys.exit(1)

        if (args.verbose is True):
            logging.getLogger().setLevel(logging.DEBUG)

        if (args.quiet is True):
            logging.getLogger().setLevel(logging.ERROR)

        self.__cmdline_read = 1
        self.arguments = args

        return



    # load_config()
    #
    # load configuration file (YAML)
    #
    # parameter:
    #  - self
    # return:
    #  none
    def load_config(self):
        if not (self.arguments.config):
            self.__configfile_read = 1
            self.configfile = False
            return

        logging.debug("config file: " + self.arguments.config)

        if (self.arguments.config and os.path.isfile(self.arguments.config) is False):
            self.print_help()
            print("")
            print("Error: --config is not a file")
            sys.exit(1)

        try:
            with open(self.arguments.config, 'r') as ymlcfg:
                config_file = yaml.safe_load(ymlcfg)
        except:
            print("")
            print("Error loading config file")
            sys.exit(1)

        #print(config_file['git']['executable'])
        self.configfile = config_file


        # prepopulate values, avoid nasty 'KeyError" later on
        self.pre_set_configfile_value('commitfest', 'username', None)
        self.pre_set_configfile_value('commitfest', 'secret', None)
        self.pre_set_configfile_value('commitfest', 'url', None)
        self.pre_set_configfile_value('commitfest', 'number-parallel-jobs', None)

        self.pre_set_configfile_value('repository', 'url', None)

        # top-dir can only be present in the config file
        # pathnames on the commandline need to be fully specified
        self.pre_set_configfile_value('build', 'dirs', 'top-dir')
        self.pre_set_configfile_value('build', 'dirs', 'cache-dir')
        self.pre_set_configfile_value('build', 'dirs', 'build-dir')

        self.pre_set_configfile_value('build', 'options', None)

        self.pre_set_configfile_value('build', 'cleanup', 'cleanup-builds')
        self.pre_set_configfile_value('build', 'cleanup', 'cleanup-repository')
        self.pre_set_configfile_value('build', 'cleanup', 'cleanup-test-files')

        self.pre_set_configfile_value('locking', 'lockfile', None)

        self.pre_set_configfile_value('platform', 'linux', None)


        self.__configfile_read = 1
        return



    # pre_set_configfile_value()
    #
    # make sure that the specified configfile parameter is initialized
    #
    # parameter:
    #  - name of first level
    #  - name of second level (or None)
    #  - name of third level (or None)
    def pre_set_configfile_value(self, pos1, pos2, pos3):
        if (pos1 is None):
            print("Error setting configfile value")
            sys.exit(1)
        if (pos3 is not None and pos2 is None):
            print("Error setting configfile value")
            sys.exit(1)

        if (pos2 is None):
            # just pos1 is specified, this makes pos1 an actual key
            # not a container for more config elements
            if not (pos1 in self.configfile):
                self.configfile[pos1] = ''
            if (self.configfile[pos1] is None):
                self.configfile[pos1] = ''
            return

        if (pos3 is None):
            # pos1 is a dictionary
            if not (pos1 in self.configfile):
                self.configfile[pos1] = {}
            if not (pos2 in self.configfile[pos1]):
                self.configfile[pos1][pos2] = ''
            if (self.configfile[pos1][pos2] is None):
                self.configfile[pos1][pos2] = ''
            return

        # pos1 and pos2 are dictionaries
        if not (pos1 in self.configfile):
            self.configfile[pos1] = {}
        if not (pos2 in self.configfile[pos1]):
            self.configfile[pos1][pos2] = {}
        if not (pos3 in self.configfile[pos1][pos2]):
            self.configfile[pos1][pos2][pos3] = ''
        if (self.configfile[pos1][pos2][pos3] is None):
            self.configfile[pos1][pos2][pos3] = ''

        return



    # replace_home_env()
    #
    # replace placeholder for home directory with actual directory name
    #
    # parameter:
    #  - self
    #  - directory name
    # return:
    #  - directory name
    def replace_home_env(self, dir):
        #dir = string.replace(dir, '$HOME', os.environ.get('HOME'))
        dir = dir.replace('$HOME', os.environ.get('HOME'))
        dir = dir.replace('$TOPDIR', self.configfile['build']['dirs']['top-dir'])
        dir = dir.replace('$HOME', os.environ.get('HOME'))
        return dir



    # build_and_verify_config()
    #
    # verify configuration,
    # create config from commandline and config file
    #
    # parameter:
    #  - self
    # return:
    #  none
    def build_and_verify_config(self):

        ret = {}

        if (self.arguments.verbose is True and self.arguments.quiet is True):
            self.print_help()
            print("")
            print("Error: --verbose and --quiet can't be set at the same time")
            sys.exit(1)

        if (self.arguments.verbose is True):
            logging.getLogger().setLevel(logging.DEBUG)
            ret['verbose'] = True
            ret['quiet'] = False

        if (self.arguments.quiet is True):
            logging.getLogger().setLevel(logging.ERROR)
            ret['verbose'] = False
            ret['quiet'] = True


        if (self.configfile is not False):
            if (len(self.configfile['build']['dirs']['cache-dir']) > 0 and os.path.isdir(self.replace_home_env(self.configfile['build']['dirs']['cache-dir'])) is False):
                self.print_help()
                print("")
                print("Error: cache-dir is not a directory")
                print("Argument: " + self.configfile['build']['dirs']['cache-dir'])
                sys.exit(1)
        if (self.configfile is not False and self.configfile['build']['dirs']['cache-dir']):
            ret['cache-dir'] = self.replace_home_env(self.configfile['build']['dirs']['cache-dir'])
        else:
            self.print_help()
            print("")
            print("Error: cache-dir is not defined")
            sys.exit(1)
        if (ret['cache-dir'].find("'") != -1 or ret['cache-dir'].find('"') != -1):
            self.print_help()
            print("")
            print("Error: Invalid cache-dir name")
            print("Argument: " + ret['cache-dir'])
            sys.exit(1)


        if (self.configfile is not False):
            if (len(self.configfile['build']['dirs']['build-dir']) > 0 and os.path.isdir(self.replace_home_env(self.configfile['build']['dirs']['build-dir'])) is False):
                self.print_help()
                print("")
                print("Error: build-dir is not a directory")
                print("Argument: " + self.configfile['build']['dirs']['build-dir'])
                sys.exit(1)
        if (self.configfile is not False and self.configfile['build']['dirs']['build-dir']):
            ret['build-dir'] = self.replace_home_env(self.configfile['build']['dirs']['build-dir'])
        else:
            self.print_help()
            print("")
            print("Error: build-dir is not defined")
            sys.exit(1)
        if (ret['build-dir'].find("'") != -1 or ret['build-dir'].find('"') != -1):
            self.print_help()
            print("")
            print("Error: Invalid build-dir name")
            print("Argument: " + ret['build-dir'])
            sys.exit(1)


        stat_cache = os.stat(ret['cache-dir'])
        stat_build = os.stat(ret['build-dir'])
        if (stat_cache.st_dev != stat_build.st_dev):
            self.print_help()
            print("")
            print("Error: cache-dir and build-dir must be on the same filesystem")
            sys.exit(1)


        if (self.configfile is not False and len(self.configfile['git']['executable']) > 0):
            # use the executable from the configuration file
            if (self.binary_is_executable(self.configfile['git']['executable']) is False):
                self.print_help()
                print("")
                print("Error: --git-bin is not an executable")
                print("Argument: " + self.configfile['git']['executable'])
                sys.exit(1)
            ret['git-bin'] = self.configfile['git']['executable']
        else:
            # find git binary in $PATH
            tmp_bin = self.find_in_path('git')
            if (tmp_bin is False):
                self.print_help()
                print("")
                print("Error: no 'git' executable found")
                sys.exit(1)
            ret['git-bin'] = tmp_bin

        # check 'git' version number
        null_file = open(os.devnull, 'w')
        v = subprocess.check_output([ret['git-bin'], '--version'], stderr=null_file)
        null_file.close()
        # make sure the extract ends in a number, this will cut of things like "rc..."
        v_r = re.match(b'git version ([\d\.]+\d)', v)
        if (v_r):
            logging.debug("'" + str(ret['git-bin']) + "' version: " + v_r.group(1).decode())
            self.arguments.git_version = v_r.group(1).decode()
        else:
            self.print_help()
            print("")
            print("Error: cannot identify 'git' version")
            sys.exit(1)
        # 'git' version must be 2.x.x, or greater
        v_v = self.arguments.git_version.split('.')
        try:
            v_v2 = int(v_v[0])
        except ValueError:
            self.print_help()
            print("")
            print("Error: cannot identify 'git' version")
            sys.exit(1)
        if (v_v2 < 2):
            self.print_help()
            print("")
            print("Error: minimum required 'git' version is 2")
            print("Found: " + self.arguments.git_version)
            sys.exit(1)
        # all git versions below 2.7.1 are vulnerable
        if (LooseVersion(self.arguments.git_version) <= LooseVersion('2.7.1')):
                logging.warning("git version (" + self.arguments.git_version + ") is vulnerable!")


        # read value from configfile
        if (self.configfile is not False and len(str(self.configfile['git']['depth'])) > 0):
            ret['git-depth'] = self.configfile['git']['depth']
        else:
            # default value (everything)
            ret['git-depth'] = 0
        try:
            t = int(ret['git-depth'])
        except ValueError:
            self.print_help()
            print("")
            print("Error: git-depth is not an integer")
            sys.exit(1)
        if (t < 0):
            self.print_help()
            print("")
            print("Error: git-depth must be a positive integer")
            sys.exit(1)
        ret['git-depth'] = t


        if (self.configfile is not False and len(self.configfile['commitfest']['username']) > 0):
            ret['commitfest-username'] = self.configfile['commitfest']['username']
        else:
            self.print_help()
            print("")
            print("Error: No commitfest username specified")
            sys.exit(1)


        if (self.configfile is not False and len(self.configfile['commitfest']['secret']) > 0):
            ret['commitfest-secret'] = self.configfile['commitfest']['secret']
        else:
            self.print_help()
            print("")
            print("Error: No commitfest secret specified")
            sys.exit(1)


        if (self.configfile is not False and len(self.configfile['commitfest']['url']) > 0):
            ret['commitfest-url'] = self.configfile['commitfest']['url']
        else:
            self.print_help()
            print("")
            print("Error: No buildfarm url specified")
            sys.exit(1)


        if (self.configfile is not False and len(self.configfile['commitfest']['number-parallel-jobs']) > 0):
            ret['number-parallel-jobs'] = self.configfile['commitfest']['number-parallel-jobs']
        else:
            self.print_help()
            print("")
            print("Error: Number of parallel jobs not specified")
            sys.exit(1)
        try:
            t = int(ret['number-parallel-jobs'])
        except ValueError:
            self.print_help()
            print("")
            print("Error: number-parallel-jobs is not an integer")
            sys.exit(1)
        if (t < 0):
            self.print_help()
            print("")
            print("Error: number-parallel-jobs must be a positive integer")
            sys.exit(1)
        ret['number-parallel-jobs'] = t


        # do not really check if a valid repository is specified, let git deal with it
        if (self.configfile is not False and len(self.configfile['repository']['url'])) > 0:
            ret['repository-url'] = self.configfile['repository']['url']
        else:
            self.print_help()
            print("")
            print("Error: No repository url specified")
            sys.exit(1)


        if (self.configfile is not False and self.configfile['build']['cleanup']['cleanup-builds'] == 1):
            ret['cleanup-builds'] = True
        else:
            ret['cleanup-builds'] = False


        if (self.configfile is not False and self.configfile['build']['cleanup']['cleanup-repository'] == 1):
            ret['cleanup-repository'] = True
        else:
            ret['cleanup-repository'] = False


        if (self.configfile is not False and self.configfile['build']['cleanup']['cleanup-test-files'] == 1):
            ret['cleanup-test-files'] = True
        else:
            ret['cleanup-test-files'] = False


        if (self.configfile is not False and len(self.replace_home_env(self.configfile['locking']['lockfile'])) > 0):
            ret['lockfile'] = self.replace_home_env(self.configfile['locking']['lockfile'])
        else:
            ret['lockfile'] = ''
        # test tool requires a lockfile
        if (len(ret['lockfile']) == 0):
            self.print_help()
            print("")
            print("Error: a lockfile is required")
            sys.exit(1)

        if (len(ret['lockfile']) > 0):
            lock = LockFile(ret['lockfile'])
            logging.debug("trying to acquire lock on " + ret['lockfile'])
            if not lock.i_am_locking():
                try:
                    lock.acquire(timeout = 1)
                    logging.debug("acquired lock on " + ret['lockfile'])
                except LockTimeout:
                    logging.error("can't acquire lock on " + ret['lockfile'])
                    # just bail out here, something else is locking the lockfile
                    sys.exit(1)
            self.lockfile_handle = lock
            self.lockfile_name = ret['lockfile']



        self.__fully_initiated = 1
        self.config = ret

        return ret



    # get()
    #
    # get a specific config setting
    #
    # parameter:
    #  - self
    #  - config setting name
    # return:
    #  - config value
    # note:
    #  - will abort if the configuration is not yet initialized
    #  - will abort if the config setting is not initialized
    def get(self, name):
        if (self.__fully_initiated != 1):
            print("")
            print("Error: config is not initialized!")
            sys.exit(1)
        if (name in self.config):
            return self.config[name]
        else:
            print("")
            print("Error: requested config value does not exist!")
            print("Value: " + name)
            sys.exit(1)



    # getall()
    #
    # return a list of all config keys
    #
    # parameter:
    #  - self
    # return:
    #  - list with all config keys, sorted
    def getall(self):
        if (self.__fully_initiated != 1):
            print("")
            print("Error: config is not initialized!")
            sys.exit(1)

        return sorted(list(self.config.keys()))



    # isset()
    #
    # verifies if a specific config setting is initialized
    #
    # parameter:
    #  - self
    #  - config setting name
    # return:
    #  - True/False
    # note:
    #  - will abort if the configuration is not yet initialized
    def isset(self, name):
        if (self.__fully_initiated != 1):
            print("")
            print("Error: config is not initialized!")
            sys.exit(1)
        if (name in self.config):
            return True
        else:
            return False



    # set()
    #
    # set a specific config setting to a new value
    #
    # parameter:
    #  - self
    #  - config setting name
    #  - new value
    # return:
    #  none
    # note:
    #  - will abort if the configuration is not yet initialized
    def set(self, name, value):
        if (self.__fully_initiated != 1):
            print("")
            print("Error: config is not initialized!")
            sys.exit(1)
        self.config[name] = value



    # create_hashname()
    #
    # creates a hashname based on the input name
    #
    # parameter:
    #  - self
    #  - input name
    # return:
    #  - hash string
    def create_hashname(self, name):
        result = hashlib.md5(name.encode('utf-8')).hexdigest()
        logging.debug("hashname: " + name + " -> " + result)

        return result



    # from: http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
    # human_size()
    #
    # format number into human readable output
    #
    # parameters:
    #  - self
    #  - number
    # return:
    #  - string with formatted number
    def human_size(self, size_bytes):
        """
        format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
        Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
        e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
        """
        if (size_bytes == 1):
            # because I really hate unnecessary plurals
            return "1 byte"

        suffixes_table = [('bytes',0),('KB',0),('MB',1),('GB',2),('TB',2), ('PB',2)]

        num = float(size_bytes)
        for suffix, precision in suffixes_table:
            if (num < 1024.0):
                break
            num /= 1024.0

        if (precision == 0):
            formatted_size = "%d" % num
        else:
            formatted_size = str(round(num, ndigits=precision))

        return "%s %s" % (formatted_size, suffix)



    # binary_is_executable()
    #
    # verify if a specified binary is executable
    #
    # parameter:
    #  - self
    #  - binary name
    # return:
    #  - True/False
    # note:
    #  - does not work on Windows
    def binary_is_executable(self, bin):
        if (os.access(bin, os.X_OK)):
            return True

        return False



    # find_in_path()
    #
    # find a specific binary in $PATH
    #
    # parameter:
    #  - self
    #  - binary name
    # return:
    #  - binary with path, or False
    # note:
    #  - does not work on Windows
    def find_in_path(self, bin):
        # Python 3.3 and newer have shutil.which()
        # Note: this does not work on Windows
        for p in os.environ["PATH"].split(os.pathsep):
            e = os.path.join(p, bin)
            if (self.binary_is_executable(e) is True):
                # found a binary
                return e

        return False



    # cleanup_old_dirs_and_files()
    #
    # cleanup old directories, patches and build support files
    #
    # parameter:
    #  - self
    # return:
    #  none
    def cleanup_old_dirs_and_files(self):
        print("FIXME: cleanup_old_dirs_and_files()")
        sys.exit(1)
        # note: not the best place for this function, but usually the Config module
        # is initialized way before the other modules
        if (self.get('cleanup-builds') is True):
            # cleanup all directories in the 'build' and 'install' directory, which match a certain pattern
            found = []
            for entry in os.listdir(self.get('build-dir')):
                if (os.path.isdir(os.path.join(self.get('build-dir'), entry))):
                    found.append(os.path.join(self.get('build-dir'), entry))
            for entry in os.listdir(self.get('install-dir')):
                if (os.path.isdir(os.path.join(self.get('install-dir'), entry))):
                    found.append(os.path.join(self.get('install-dir'), entry))

            for entry in found:
                entry_match = re.search(r'[\/\\]\d\d\d\d\-\d\d\-\d\d_\d\d\d\d\d\d_', entry)
                if (entry_match):
                    logging.info("remove directory: " + str(entry))
                    shutil.rmtree(entry, ignore_errors=True)
                    if (os.path.isfile(entry + '.diff')):
                        logging.info("remove patch: " + str(entry) + '.diff')
                        os.remove(entry + '.diff')

        if (self.get('cleanup-repository') is True):
            # cleanup all files in the 'cache' directory, which match a certain pattern
            found = []
            for entry in os.listdir(self.get('cache-dir')):
                if (os.path.isfile(os.path.join(self.get('cache-dir'), entry))):
                    found.append(os.path.join(self.get('cache-dir'), entry))

            for entry in found:
                entry_match = re.search(r'[\/\\][a-f0-9]+\.diff$', entry)
                if (entry_match):
                    logging.info("remove patch: " + str(entry))
                    os.remove(entry)
                entry_match = re.search(r'[\/\\][a-f0-9]+\.diff.unpacked$', entry)
                if (entry_match):
                    logging.info("remove patch: " + str(entry))
                    os.remove(entry)



