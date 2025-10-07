'''
    gbmon-controller - get configuration from gameboard platform and signal gameboard-monitoring
    application on changes.
    
    Read from the Gameboard API and write to the gbmon-config YAML file.
    On changes signal (-SIGHUB) the gbmon process to reload the configuration.

    - interact with the Gameboard API
    - check for active DDoS test and latest changes
    - retrieve configuration from Gameboard API
    - get gbmon process ID
    - SIGHUP gbmon process when config has changed
    
    Future development:
    - start / stop gbmon process if there is an active ddos test or has ended
    - check the gbmon process to be alive and restart on crashes
    - restart gbmon if signalled by the Gameboard application
    
@author: pim
@since: 11-09-2024
@version: 1.1
'''
import sys
import subprocess
import datetime
import time
import json
import glob
import pathlib
from urllib.parse import urlparse
import psutil
import gbapi
import gbcommon
import scamper

CONFIG_YAML = 'gbm-config.yaml'
LOOPWAIT = 10
LOGSTDOUT = 'log/gbmon_stdout.log'
logger = None
cfg = None

'''
    Get all vps nodes registered at the controller.
    Remote processes can connect and create a remote socket on the
    controller of connect to the multiplexed interface. Both methods can be used
    to find the active remote processes. Only one method will used at a time.
    mux_interface has preference over socket_dir.
    
'''
def get_allnodes(socket_dir=None, mux_interface=None):
    nodes = []
    
    if mux_interface == None:
        if socket_dir != None:
            arklist = [file for file in glob.glob(f"{socket_dir}/*.ark-*")]
            for node in arklist:
                subs1 = node[node.rfind("/")+1:] # get past the last "/" as path divider
                subs2 = subs1[:subs1.find("ark-")+3]
                nodes.append(subs2)
    else:
        with scamper.ScamperCtrl(mux=mux_interface) as ctrl:
            vps = ctrl.vps()          # list[ScamperVp] + metadata (name, cc, tags, ASN, etc.)
            for vp in vps:
                print(vp.name, vp.cc, vp.tags)

    return sorted(nodes)


'''
    gbmon_is_running() - Check if gbmon process is running.
    Best to check if main process is running. There could be child processes
    running, while parent process has died.
    1. get process ID
    2. check if main process is still running (by probing /proc)
'''
def gbmon_is_running(pidfile):
    pid = gbcommon.get_pid(pidfile)
    if (not pid):
        return False

    fp = pathlib.Path(f"/proc/{pid}/status")
    return(fp.is_file())


'''
    gbmono_start() - Start gbmon process
'''
def gbmon_start(pidfile):
    logger.info("Start gbmon application")
    if (not gbmon_is_running(pidfile)):
        try:
            with open(LOGSTDOUT, "w+") as fd:
                subprocess.Popen(["/usr/bin/python3", "gbmon.py"], stdout=fd, stderr=fd)
        except KeyboardInterrupt:
            pass
        except:
            exctype, excvalue = sys.exc_info()[:2]
            logger.warning(f"gbmon_start - Unhandled exception {exctype}: {excvalue}")
    time.sleep(10) # Give gbmon the time to start and set the PID
    return None

'''
    gbmon_stop() - Signal gbmon to stop and check if it has stopped.
    Also check for the child processes to be stopped.
    Stop a process by process id. First give a SIGHUP, then a SIGTERM and at last SIGKILL if process
    is still not stopped.
'''
def gbmon_stop(pidfile):
    logger.info("Signal gbmon application to stop")
    pid = gbcommon.get_pid(pidfile)
    try:        
        p = psutil.Process(pid)
        p.send_signal(gbcommon.SIGINT)
        if not gbcommon.wait_running(p, 30):
            p.terminate()
            if not gbcommon.wait_running(p, 10):
                p.kill()
                p.wait()
    except psutil.NoSuchProcess:
        ''' Dot nothing, process could be gone in the mean time '''
    except:
        exctype, excvalue = sys.exc_info()[:2]
        logger.warning("stop_process error: exception: %s - %s" % (exctype, excvalue))
    return True


'''
    gbmon_reload() - Signal gbmon to reload the configuration
'''
def gbmon_reload(pidfile):
    if gbmon_is_running(pidfile):
        logger.info("Signal gbmon application to reload configuration")
        pid = gbcommon.get_pid(pidfile)
        p = psutil.Process(pid)
        p.send_signal(gbcommon.SIGHUP)
    return True


'''
    retrieve_config() - retrieve configuration from Gameboard with API
    - get ddos test: start, end, active
    - get targets: ip/url/domain, measurement_type_id
    - get measurement types: id, name, nodelist_id
    - get nodelists: id, list of nodes
    
    dict for config will be:
    {type : { "targets" : [target1, target2, ...],
                "nodes" : [node1, node2, ...]
            }
     ...
    }
    type is like, "ping", "dns", "httpsget"
'''
def retrieve_config(gbapi):
    '''
        Step 1: Get measurement types. Create dict of: { ID: (name, nodelist), ...}
    '''
    mtypes = {}
    mtypes_id = {}
    mtypes_nodelist = {}
    nodelists = {}
    
    retval = gbapi.get_measurementtypes()
    if (not retval[0]):
        logger.warning("retrieve_config - Unable to retrieve measurement types")
        return False

    for mtype in json.loads(retval[1]):
        mtypes_id[mtype["id"]] = mtype["name"]
        mtypes_nodelist[mtype["name"]] = mtype["nodelist_id"]

    '''
        Step 2: Get targets: elements: ("target", "ipv", "measurement_type_id", "party")
        Create dict of { measurement_type+"4"|"6": { party : [target, target, ...], [...], ...}}
    '''
    retval = gbapi.get_targets()
    if (not retval[0]):
        logger.warning("retrieve_config - Unable to retrieve targets lists")
        return False

    for target in json.loads(retval[1]):
        mtype = f"{mtypes_id[target['measurement_type_id']]}{target['ipv']}"
        if (target["enabled"]):
            try:
                mtypes[mtype][target["party"]].append(target["target"])
            except:
                try:
                    mtypes[mtype][target["party"]] = []
                except:
                    mtypes[mtype] = {}
                    mtypes[mtype][target["party"]] = []
                mtypes[mtype][target["party"]].append(target["target"])
        
    '''
        Step 3: Get nodelist: elements: {'measurement_type"+"4"|"6" : [node, node, ...], ...}
    '''
    retval = gbapi.get_nodelists()
    node_data = json.loads(retval[1])

    if not retval[0]:
        logger.error(f'retrieve_config - Nodelists not available, message: {node_data["error"]}')
        return False

    for nodelist in node_data:
        nodelists[nodelist['id']] = nodelist['list']

    '''
        Step 4: assemble total configuration
    '''
    for mtype in mtypes.keys():
        mtypes[mtype]["nodes"] = nodelists[mtypes_nodelist[mtype[:-1]]]

    return mtypes


def epoch_now():
    return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())


def main():
    global logger
    global cfg
    prev_nodes = []
    prev_updated = 0
    
    handler_quit = gbcommon.c_signal((gbcommon.SIGINT, gbcommon.SIGTERM))

    retval = gbcommon.read_config(CONFIG_YAML)
    if (not retval[0]):
        print(f"Cannot read config, message {retval[1]}")
        return 1
    
    cfg = retval[1]

    logger = gbcommon.set_logging(cfg['controller']['logfile'], cfg['controller']['loglevel'], logcount=5)
    logger.info("main - Start of gameboard-monitoring controller")

    logger.info("Connect to gameboard API")
    try:
        api_domain = urlparse(cfg['general']['gameboard_api']).netloc
        api_login,api_password = gbcommon.get_credentials(f"gbapi-{api_domain}")
    except:
        logger.error("Could not retrieve Gameboard API credentials. Exiting...")
        return 1

    gba = gbapi.GameboardApi(cfg["general"]["gameboard_api"])
    try:
        retval = gba.authenticate(api_login, api_password)
    except:
        logger.error("Not able to connect or authenticate to the Gameboard API")
        return 1
    
    if (not retval[0]):
        logger.error(f"Not able to authenticate. Message: {retval[1]}. Exit!")
        return 1
    else:
        logger.info("API access authenticated")


    try:
        socket_dir = cfg["general"]["socket_dir"]
    except:
        logger.error("Socket directory not in configuration. Cannot continue.")
        return 1

    '''
        Periodic actions are:
        * retrieve nodelist from Ark and check if there are changes. Put list to Gameboard on changes
        * check if ddostest changes. Start/stop gbmon if ddostest is active/inactive 
        * get configuration if ddostest active (is_active and updated_at has changed) changes 
          and store in yaml; reload gbmon
    '''
    while(1):
        if (handler_quit.got_signal):
            logger.error(f'Signal received of type {handler_quit.signal}! Exiting...')
            return(1)

        '''
            Step 1: Get nodelist from Ark and PUT list to gameboard on changes
        '''
        all_nodes = get_allnodes(socket_dir)
        if all_nodes != prev_nodes:
            logger.info("Node list has changed (or first run). Send list to Gameboard.")
            set_now = set(all_nodes)
            set_prev = set(prev_nodes)
            logger.info(f"    Current list ({len(all_nodes)}) has new nodes: {str(set_now - set_prev)}")
            logger.info(f"    Previous list ({len(prev_nodes)}) has removed nodes: {str(set_prev - set_now)}")
            retval = gba.put_nodelist(1, all_nodes)
            if (not retval[0]):
                logger.error(f"Fatal: Not able to get ddos excercise 1. Return message: {retval[1]}.\nExiting ...")
                return 1
            prev_nodes = all_nodes.copy()

        '''
            Step 2: Check if ddostest is in active timeframe and config activated
            Start gbmon if not running. This is a process check at the same time.
            Stop gbmon if it should not run anymore.
        '''
        ts_now = epoch_now()
        try:
            retvalue = gba.get_ddostests(1)
        except:
            exctype, excvalue = sys.exc_info()[:2]
            logger.warning(f"main - problem connection to the API in main loop, exception {exctype}: {excvalue}")
            if (gbcommon.sleep_signal(60, handler_quit)):
                logger.error(f'main - signal received of type {handler_quit.signal}! Exiting...')
                break
            continue

        if (not retvalue[0]):
            logger.error("Fatal: Not able to get ddos excercise 1. Exiting ...")
            return 1
        
        ddostest = json.loads(retvalue[1])

        if int(ddostest["activated"]) and ts_now >= ddostest["start"] and ts_now <= ddostest["end"]:
            if not gbmon_is_running(cfg['general']['pid']):
                logger.info("DDoS test in active timeframe and activated. Start gbmon.")
                gbmon_start(cfg['general']['pid'])
    
        elif gbmon_is_running(cfg['general']['pid']):
            logger.info("DDoS test is not active anymore. Stop gbmon.")
            gbmon_stop(cfg['general']['pid'])
            continue

        '''
            Step 3: IF DDoS test is active then check for last updated if config needs to reload
        '''
        if int(ddostest["activated"]) and ddostest["updated_at"] > prev_updated:
            logger.info("Reload of configuration necessary")
            prev_updated = ddostest["updated_at"]
            apiconf = retrieve_config(gba)
            if (not apiconf):
                logger.warning("main - Not possible to run. Try again in a minute")
                if (gbcommon.sleep_signal(60, handler_quit)):
                    logger.error(f'Signal received of type {handler_quit.signal}! Exiting...')
                    return(1)
                break
                
            cfg["measurements"] = apiconf
            gbcommon.write_config(CONFIG_YAML, cfg)
            gbmon_reload(cfg['general']['pid'])

        if (gbcommon.sleep_signal(LOOPWAIT, handler_quit)):
            logger.error(f'Signal received of type {handler_quit.signal}! Exiting...')
            return(1)

    return 0


if __name__ == '__main__':
    get_allnodes()
    exit()
    main()
    gbmon_stop(cfg['general']['pid'])
    
