'''
    gbmon - Gameboard monitoring application
    
    Use Caida Ark to measure if hosts are reachable and the performance of hosts and websites. This is based on the round trip delay of request.
    Request can be:
    * ping
    * get https request
    * post https request
    * tcp port connect
    * smtp helo / ok
    
    implemented types are:
    - ping
    - https_get
    - smtp
    
    measurements are stored in a timeseries database like influxdb / Amazon Timeseries
    
    This data can be use to graph with Grafana
    
    Created on 7 Aug 2024
    
    @author: Pim van Stam
    @copyright: S3group, 2024
    @version: 1.0
'''
import sys
import multiprocessing
import glob
import time
import gbmeasure
import gbdb
import gbcommon

CONFIG_YAML = 'gbm-config.yaml'
PIDFILE = "gbmon.pid"

# The measurement types we use / support
M_TYPES = ("ping",
           "httpget",
           "dns",
           "ntp",
           "smtp")
#M_TYPES = ("ping4",)
#M_TYPES = ("httpsget4",)
#M_TYPES = ("dns6",)
#M_TYPES = ("smtp4",)

# define which class to use for a specified type of measurement
M_CLASS = { "ping" : gbmeasure.MPing,
            "httpget" : gbmeasure.MHttpGet,
            "smtp" : gbmeasure.MSmtp,
            "dns" : gbmeasure.MDns,
            "ntp" : gbmeasure.MNtp,
            "traceroute" : gbmeasure.MTraceroute }

logger = None

'''
    load_measurement: load the measurement specific class and configuration for this type
    - load class
    - connect the timeseries database to it
    - get the targets from config
    - get the measurement nodes from config
'''
def load_measurement(cfg, m_type, ipversion):

    m_type46 = f"{m_type}{ipversion}"
    
    try:
        mc = M_CLASS[m_type](logger=logger, ipversion=ipversion)
    except KeyError:
        return(None, f"load_measurement - no such measurement type '{m_type46}'" )
    except:
        exctype, excvalue = sys.exc_info()[:2]
        return (None, f"load_measurement - Unhandled exception on measurement types: {exctype}: {excvalue}")
    
    try:
#        targets = cfg["measurements"][m_type46]["targets"]
        targets = cfg["measurements"][m_type46]

    except KeyError:
        return(None, f"load_measurement - no targets in config for type '{m_type46}'")
    except:
        exctype, excvalue = sys.exc_info()[:2]
        return (None, f"load_measurement - Unhandled exception on targets: {exctype}: {excvalue}")
    
    for party in targets.keys():
        if party != "nodes": # keyword for list of nodes to use for measurements
            for target in targets[party]:
                mc.add_target([target, party])

    try:
        mc.set_socket_dir(cfg["general"]["socket_dir"])
    except:
        mc.set_socket_dir("")

    try:
        m_nodes = cfg["measurements"][m_type46]["nodes"]
    except KeyError:
        return(None, f"load_measurement - no nodes in config for type '{m_type46}'")
    except:
        exctype, excvalue = sys.exc_info()[:2]
        return (None, f"load_measurement - Unhandled exception on nodes: {exctype}: {excvalue}")
    
    for n in m_nodes:
        n_path = glob.glob(mc.get_socket_dir() + n + "-*")
        for np in n_path:
            mc.add_node(np)

    nr_nodes = len(mc.get_nodes())
    if not nr_nodes:
        return(None, f"load_measurement - no nodes available for the measurement {m_type46}.")
    
    return (mc, f"load_measurement - measurement {m_type46} will run on {nr_nodes} nodes")

'''
    do_measure() - intermediate function for multiprocessing
    This function is parameter for the subprocess and calls the classes do() function
'''

def do_measure(reload_event, mc_class):
    mc_class.do(reload_event)


def main():
    global logger

    handler_quit = gbcommon.c_signal((gbcommon.SIGINT, gbcommon.SIGTERM))
    reload_event = multiprocessing.Event()
    
    while(1):
        retval = gbcommon.read_config(CONFIG_YAML)
        if (not retval[0]):
            print(f"Cannot read config, message {retval[1]}")
            return 1
        
        cfg = retval[1]

        logger = gbcommon.set_logging(cfg['general']['logfile'], cfg['general']['loglevel'], logcount=5)
        logger.info("main - Run gameboard monitor main loop")
        
        handler_reload = gbcommon.c_signal((gbcommon.SIGHUP,))

        if (handler_quit.got_signal):
            logger.info("main - we got a signal to quit. End now!")
            return 0
        
        # clear reload event in case of previous reload request
        reload_event.clear()

        try:
            pidfile = cfg['general']['pid']
        except KeyError:
            pidfile = PIDFILE
        gbcommon.write_pid(pidfile)

        dbconn = gbdb.MDb()
        dbconn.load_dbconfig(cfg["database"])

        p_mcs = []
        for mt in M_TYPES:
            for ipver in ("4", "6"):
                mc = load_measurement(cfg, mt, ipver)
                logger.info(mc[1])
                if mc[0] != None:
                    mc[0].db = dbconn # make reference to the database connector
    
                    # start each type of measurement in a subprocess, write data in separate threads
                    p_mc = multiprocessing.Process(target = do_measure, args = (reload_event, mc[0], ))
                    p_mc.start()
                    p_mcs.append(p_mc)
                    
        if not len(p_mcs):
            logger.info("main - No measurements with targets and nodes. Wait a minute and try again.")
            if (gbcommon.sleep_signal(60, handler_quit)): # no measurment types with nodes to measure on, so wait a minute
                break
        else:
            logger.info(f"main - Started {len(p_mcs)} subprocesses for measurements")
            waittime = 1
            while(1):
                '''
                   check every second if subprocesses are still running (they should)
                   and the wait time gives the main process the option for signal handling
                '''                    
                if (handler_reload.got_signal or handler_quit.got_signal):
                    logger.info("main - reload (sighup) or terminate (sigint) received. Signal the child processes to quit")
                    waittime = 60
                    reload_event.set() # Notify all subprocesses to quit and run next main loop 
    
                for p_mc in p_mcs:
                    p_mc.join(waittime) # Are there processes already done?
                
                # check if processes have finished, if so go to main loop
                if not any(p_mc.is_alive() for p_mc in p_mcs):
                    logger.info("main - all subprocesses have finished (none alive).")
                    break
    
                # do whatever you like while processes are running                    
    
            # when signal is to exit/quit, stop program now. If it's a signal to reload, just goto next run
            logger.info("main - subprocesses joined in main. Restart loop.")
            # check for signal and reload config and start measurements again
            time.sleep(1)
        gbcommon.remove_pid(pidfile)
    return 0


if __name__ == '__main__':
    main()
    exit(0)
