'''
    gbcommon - Common functions for the Gameboard monitoring applications
        
    Created on 16 September 2024
    
    Dependencies:
    - python3-yaml
    
    @author: Pim van Stam
    @copyright: S3group, 2024
    @version: 1.0
'''

import sys
import signal
import yaml
import os.path
import netrc
import logging, logging.handlers
import time

SIGHUP = signal.SIGHUP
SIGINT = signal.SIGINT
SIGTERM = signal.SIGTERM


def exit_error(msg):
    print("Error: " + msg)
    exit(1)


def read_config(cfgfile):
    '''
        Read config from the yaml file
        Try to open file as-is (current directory, or in absolute or relative path.
        Otherwise check in HOME, /etc/ or /usr/local/etc, in that order
    '''

    try:
        with open(cfgfile, 'r') as fp:
            cfg = yaml.safe_load(fp)
    
    except FileNotFoundError as err:
        if cfgfile[0] == '/': # absolute path
            return((0, f"Can't load config file: {str(err)}"))
        else:
            if os.path.isfile("" + cfgfile):
                fn = "/etc/" + cfgfile
            elif os.path.isfile("/etc/" + cfgfile):
                fn = "/etc/" + cfgfile
            elif os.path.isfile("/usr/local/etc/" + cfgfile):
                fn = "/usr/local/etc/" + cfgfile
            else:
                return((0, f"Can't load config file {cfgfile}. Not useful to run without config."))
                    
            try:
                with open(fn, 'r') as fp:
                    cfg = yaml.safe_load(fp)
    
            except FileNotFoundError as err:
                return((0, f"Can't load config file: {str(err)}"))
            except:
                exctype, excvalue = sys.exc_info()[:2]
                return((0, f"Unknown exception: {exctype} - {excvalue}"))

    except:
        exctype, excvalue = sys.exc_info()[:2]
        return((0, f"Unknown exception: {exctype} - {excvalue}"))

    return ((1, cfg))

'''
    write_config() - Write the configuration in a dictionary to the YAML file
    yaml.dump() deduplicates config items if possible
'''
def write_config(cfgfile, cfg):
    with open(cfgfile, 'w') as fp:
        yaml.dump(cfg, fp)
    return None


'''
    c_signal - signal handler classes
'''
class c_signal():
    def __init__(self, signal_types):
        self.got_signal = False
        self.signal = None
        
        for stype in signal_types:
            signal.signal(stype, self.signal_handler)

    def signal_handler(self, signal, frame):
        print(f'Signal received of type {signal}! Signal will be processed, please wait ...')
        self.signal = signal
        self.got_signal = True


'''
    Sleep for "sleeptime" number of seconds.
    If signal is received, return directly
    Return value: True: signal received, sleep aborted; False: nog signal received
'''
def sleep_signal(sleeptime, sig_handler):
    n = 0
    while n < sleeptime:
        if (sig_handler.got_signal):
            return(True)
        n += 1
        time.sleep(1)


'''
    Wait for pid to stop running. Return True on stopped and False on timeout
'''
def wait_running(pid, timeout=1):
    raise_at = time.time() + timeout
    while time.time() <= raise_at:
        if not pid.is_running():
            # give it one more iteration to allow full initialization
            time.sleep(0.1)
            return True
        time.sleep(0.1)
    return False

'''
    get_credentials() - Get credentials from a .netrc file
'''
def get_credentials(authenticator):
    try:
        credentials = netrc.netrc()
        login, account, password = credentials.authenticators(authenticator)
    except FileNotFoundError:
        exit_error("authentication file .netrc not found")
    except TypeError:
        exit_error("credentials for " + authenticator + " not found in .netrc")
    except:
        raise()
        exit(1)

    return (login, password)

'''
    Functions for process ID handling
'''
def write_pid(filename):
    pid = os.getpid()
    with open(filename, "w") as fpid:
        fpid.write(str(pid))
    return pid

def remove_pid(filename):
    os.unlink(filename)

def get_pid(filename):
    try:
        with open(filename, "r") as fpid:
            retval = fpid.read()
    except FileNotFoundError:
        return(0)

    if (len(retval) == 0):
        retval = 0

    return int(retval)


'''
    set logging with logfile
'''
def set_logging(logfile, level, logcount=0):
    
    logging.getLogger("Rx").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    
    log = logging.getLogger() # get root logger
    if log.hasHandlers(): # cleanup stale/existing handlers
        for loghandler in log.handlers:
            log.removeHandler(loghandler)

    set_loglevel(log, level)

    if logcount > 0:
        loghandler = logging.handlers.TimedRotatingFileHandler(filename=logfile, when='midnight', backupCount=logcount)
    else:
        loghandler = logging.handlers.WatchedFileHandler(filename=logfile)
    frm = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    loghandler.setFormatter(frm)
    log.addHandler(loghandler)

    return log

def set_loglevel(logger, level):
    if level == 'debug':
        loglevel = logging.DEBUG
    elif level == 'warning':
        loglevel = logging.WARNING
    elif level == 'error':
        loglevel = logging.ERROR
    else:
        loglevel = logging.INFO

    logger.setLevel(loglevel)

