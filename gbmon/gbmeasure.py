'''

    gbmon_measurement - Gameboard monitoring application measurement classes

   
    @author: Pim van Stam
    @copyright: S3group, 2024
    @since: 10-09-2024
    @modified: 19-09-2024
    @version: 1.0

    Measurement classes
    - Measurement() - skeleton
    - MPing() - ping measurement
    - MHhttpsGet()
    - MHttpGet()
    - MDns()
    - MSmtp()
    
    methods are:
    - __repr__ and __str__ for representation of the class
    - add_target()  : add a target for this measurement type
    - get_targets() : get list of all defined targets
    - add_node()    : add measurement node
    - get_nodes()   : get list of all nodes for this measurement
    - do()          - execute the measurement
    
    do() must be supplied with an event to signal to let it stop for reloading config.
    
'''
#import binascii
import sys
import time
from datetime import timedelta, datetime, timezone
import scamper
import socket
from urllib.parse import urlparse

INTERVAL=20

lookup_nameserver = [] # ['ns1.example.com', ...]
lookup_httpserver = [] # ['ns1.example.com', ...]
lookup_targets = {} # {'name': {'ipaddress': ipaddress, 'index': list_index}, 'name' : {}, ...}
list_targets = []   # ['name', 'name', ...]

tasks = []

class Measurement():
    def __init__(self, m_type=None, logger=None, ipversion=4):
        '''
            General type of measurement. Typical measurements inherit this general measurement
        '''
        self.m_targets = [] # targets are a list of primary and secundary element, like (ip, ) and (url, ip)
        self.m_nodes = []
        self.m_type = m_type
        self.ipversion = ipversion
        self.m_timeout = 10
        self.m_count = 3
        self.s_path = "/var/run/remote-controller"
        self.logger = logger
        self.db = None
#TODO: initialize empty logging for logger==None

    def __repr__(self):
        return(f"Measurement type {self.m_type} has {len(self.m_targets)} targets")

    def __str__(self):
        return(self.__repr__())
    
    def set_socket_dir(self, socket_dir):
        self.s_path = socket_dir

    def get_socket_dir(self):
        return (self.s_path)
    
    '''
        Add a target to the list of measurement targets.
        Target must be specified as a list: (domainname, partyid)
        By default add the IP address of the domainname and indexid of lookup list.
        Target becomes: (domainname, partyid, ipaddress, indexid)
    '''
    def add_target(self, target):
        retval = add_ip_on_domain(target, self.m_targets, self.ipversion)
        if (not retval[0]):
            self.logger.info(retval[1])

        self.m_targets.append(retval[1])
        
    def get_targets(self):
        return(self.m_targets)
        
    def add_node(self, node):
        self.m_nodes.append(node)

    def get_nodes(self):
        return(self.m_nodes)
    
    def do(self, event_quit):
        return None
    
    def do2(self, event_quit, cb_func, result_func, dbtable):
        self.logger.info(f"do2 - execute measurement of type {self.m_type}{self.ipversion} for targets {str(self.m_targets)} on nodes {str(self.m_nodes)}")
        if not self.db.connect():
            self.logger.info("do2 - connection to the database failed!")
            return(None)

#        while(1):
        ts = int(datetime.now(tz=timezone.utc).timestamp())
        # get measurements
        results = do_measure(self.logger, event_quit, cb_func, result_func, self.ipversion, self.m_targets, self.m_nodes)

#TODO: write to database in a thread
        try:
            for target in results.keys():
                for item in self.m_targets:
                    if item[0] == target:
                        party = item[1]
                        break
                for measurement in results[target]:
                    self.logger.info(f"do2 - result measurement is {str(measurement)}")
                    self.logger.info("do2 - write to database")
                    retval = self.db.write(dbtable, ts, target, party, measurement[0], measurement[1], measurement[2])
                    self.logger.info("do2 - data written to database")

        except AttributeError: # no results received
            self.logger.info("do2 - no results received. Try next measurement")
#            if (event_quit.is_set()):
#                break
#            continue
            return None
        except:
            self.logger.warning("do2 - something went wrong seriously")
#            if (event_quit.is_set()):
#                break
            raise()

#        if (event_quit.is_set()):
#            break

        self.logger.info("do2 - start wait loop")
        n=0
        while (n < INTERVAL):
            n += 1
            if (event_quit.is_set()):
                break
            time.sleep(1)
        self.logger.info("do2 - out of wait loop")

        return None



class MPing(Measurement):
    def __init__(self, logger=None, ipversion=4):
        '''
            Measurement with ping on targets
        '''
        Measurement.__init__(self, "ping", logger, ipversion)
        
    def do(self, event_quit):
        Measurement.do2(self, event_quit, _cbmore_ping, result_ping, f"ping{self.ipversion}")


        
class MHttpGet(Measurement):
    def __init__(self, logger=None, ipversion=4):
        '''
            Measurement with HTTP(s) on targets
        '''
        Measurement.__init__(self, "http_get", logger, ipversion)

    '''
        get IP address from domain in web url. This is necessary for the do_http() method.
        Add this to the target list
    '''
    def add_target(self, target):
#        global lookup_httpserver

        retval = target[0].split('!')
        if len(retval) == 2:
            target[0] = retval[0]
            target.append(retval[1])
#            lookup_httpserver.append(target[0])            # add nameserver to lookup list
#            target.append(len(lookup_httpserver)-1)        # append indexnumber of nameserver to target list
            self.m_targets.append(target)
        else:        
            domain = urlparse(target[0]).netloc
            domain = ''.join( c for c in domain if  c not in '[]' ) # remove brackets with IPv6 URL's
            try:
                if self.ipversion == "6":
                    target.append(socket.getaddrinfo(domain, None, socket.AF_INET6)[0][4][0])
                else:
                    target.append(socket.getaddrinfo(domain, None, socket.AF_INET)[0][4][0])
            except socket.gaierror:
                self.logger.info(f"Http add_target - target {target[0]} has no IPv{self.ipversion} address. Skipping this one")
            except:
                exctype, excvalue = sys.exc_info()[:2]
                self.logger.warning(f"Http add_target - Unknown exception on resolving host name {target[0]}: {exctype}: {excvalue}")
            else:
#                lookup_httpserver.append(target[0])            # add nameserver to lookup list
#                target.append(len(lookup_httpserver)-1)        # append indexnumber of nameserver to target list
                self.m_targets.append(target)


    def do(self, event_quit):
        Measurement.do2(self, event_quit, _cbmore_http, result_http, f"http(s)get{self.ipversion}")



class MSmtp(Measurement):
    def __init__(self, logger=None, ipversion=4):
        '''
            Measurement with smtp on targets
        '''
        Measurement.__init__(self, "smtp", logger, ipversion)
        
    def do(self, event_quit):
        Measurement.do2(self, event_quit, _cbmore_smtp, result_smtp, f"smtp{self.ipversion}")



class MDns(Measurement):
    def __init__(self, logger=None, ipversion=4):
        '''
            Measurement with dns A request on targets
        '''
        Measurement.__init__(self, "dns", logger, ipversion)

    '''
        get domain from the nameservers FQDN.
        This is used to query the nameservers (NS) of this domain.
        Add this to the target list
        list is going to be: ['ns1.example.com', '1.2.3.4', 1, 'example.com']
        
        index in lookup list can be supplied with do_dns command in userid, which is integer
    '''
    def add_target(self, target):
        global lookup_nameserver
        try:
            if self.ipversion == "6":
                target.append(socket.getaddrinfo(target[0], None, socket.AF_INET6)[0][4][0])
            else:
                target.append(socket.getaddrinfo(target[0], None, socket.AF_INET)[0][4][0]) # append IP address of nameserver to list
        except socket.gaierror:
            self.logger.info(f"Target {target[0]} has no IPv{self.ipversion} address. Skipping this one")
        except:
            self.logger.warning(f"do2 - unknown exception on resolving host name {target[0]}.")
#TODO: get exception and log it and skip over
            raise(0)
        else:
            lookup_nameserver.append(target[0])            # add nameserver to lookup list
            target.append(len(lookup_nameserver)-1)        # append indexnumber of nameserver to target list
            self.m_targets.append(add_domain_from_url(target)) # append the domain to query to the list


    def do(self, event_quit):
        Measurement.do2(self, event_quit, _cbmore_dns, result_dns, f"dns{self.ipversion}")


class MNtp(Measurement):
    def __init__(self, logger=None, ipversion=4):
        '''
            Measurement with NTP on targets
        '''
        Measurement.__init__(self, "ntp", logger, ipversion)
        
    def do(self, event_quit):
        Measurement.do2(self, event_quit, _cbmore_ntp, result_ntp, f"ntp{self.ipversion}")


class MTraceroute(Measurement):
    def __init__(self, logger=None, ipversion=4):
        '''
            Measurement with traceroute on targets
        '''
        Measurement.__init__(self, "traceroute", logger, ipversion)

'''
    helper functions for the classes
'''
'''
    add_domain_from_url: get first level domain from FQDN of target
    input: target as a list with one element
    Domain name will be added as second element in the list
    input: ['www.example.com',]
    output: ['www.example.com', 'example.com']
'''
def add_domain_from_url(target_list):
    domain = target_list[0].split('.')
    target_list.append(f"{domain[-2]}.{domain[-1]}")
    return (target_list)

'''
    add IP address for a target = (domain, party) and add it to the lookup list
    return a target list with: [domain, party, ipaddress, listindex]
    return (1, target) or (0, "error message")
    
    lookup_targets = {'name-4|6': {'ipaddress': ipaddress,
                               'index': list_index},
                      'name-4|6' : {},
                      ...}
    list_targets = ['name', 'name', ...]

'''
def add_ip_on_domain(target, targets, ipversion):
    global lookup_targets
    global list_targets

    try:
        t_name = f"{target[0]}#{ipversion}"
        rec = lookup_targets[t_name]
    except KeyError: # IP address not looked up yet
        dname = target[0].split(':')[0] # strip port number if it's there
            
        try:
            if ipversion == "6":
                ipaddr = (socket.getaddrinfo(dname, None, socket.AF_INET6)[0][4][0])
            else:
                ipaddr = (socket.getaddrinfo(dname, None, socket.AF_INET)[0][4][0])

        except socket.gaierror:
            return (0, f"Add ip for target {dname} has no IPv{ipversion} address. Skipping this one")
        except:
            exctype, excvalue = sys.exc_info()[:2]
            return (0, f"Add IP for target {dname} - Unknown exception on resolving host name : {exctype}: {excvalue}")
        else:
            list_targets.append(t_name)
            indexnr = len(list_targets)-1
            rec = {'ipaddress': ipaddr, "index": indexnr}
            lookup_targets[t_name] = rec

    target.append(rec['ipaddress'])
    target.append(rec['index'])
    return (1, target)


'''
    callback methods for the measurement classes
    Results of a callback method need to be decoded by a
    corresponding result method.
'''
@staticmethod
def _cbmore_ping(ctrl, inst, i_targets):
    global tasks
    if len(i_targets[inst]) == 0:
        inst.done()
    else:
        target = i_targets[inst].pop(0)
        i_targets['tasks'].append(ctrl.do_ping(target[2], userid=target[3], inst=inst, wait_timeout=10))


@staticmethod
def _cbmore_http(ctrl, inst, i_targets):
    global tasks
    if len(i_targets[inst]) == 0:
        inst.done()
    else:
        target = i_targets[inst].pop(0)
        i_targets['tasks'].append(ctrl.do_http(target[2], target[0], inst=inst, limit_time=10))

@staticmethod
def _cbmore_http_alt(ctrl, inst, i_targets):
    global tasks
    dstport = 443
    if len(i_targets[inst]) == 0:
        inst.done()
    else:
        target = i_targets[inst].pop(0)
        i_targets['tasks'].append(ctrl.do_ping(target[2], dport=dstport, method='tcp-syn' , userid=target[3], inst=inst, wait_timeout=10))


@staticmethod
def _cbmore_dns(ctrl, inst, i_targets):
    global tasks
    if len(i_targets[inst]) == 0:
        inst.done()
    else:
        target = i_targets[inst].pop(0)
        ''' for indexing to the database we need to supply the nameserver
            So, we put target[0] in the userid, so it will pass with the dns query results
        '''
        i_targets['tasks'].append(ctrl.do_dns(target[4], server=target[2], qtype='ns', userid=target[3], inst=inst, wait_timeout=5))


@staticmethod
def _cbmore_smtp(ctrl, inst, i_targets):
    global tasks
    dstport = 25
    if len(i_targets[inst]) == 0:
        inst.done()
    else:
        target = i_targets[inst].pop(0)
        try: # Check if specific port is given
            dstport = target[0].split(':')[1]
        except IndexError:
            pass
        except:
            raise()
        i_targets['tasks'].append(ctrl.do_ping(target[2], dport=dstport, method='tcp-syn' , userid=target[3], inst=inst, wait_timeout=10))


@staticmethod
def _cbmore_ntp(ctrl, inst, i_targets):
    global tasks
    if len(i_targets[inst]) == 0:
        inst.done()
    else:
        '''
            Make NTP payload
        '''
        dt_now = datetime.now().timestamp()
        now_1900 = int(dt_now + 2208988800) # convert from 1970 (epoch) to 1900
        now_1900_rem = int((dt_now - int(dt_now)) * 100000000) # remainder in 8 decimals

        ntpdata = bytearray(b'\xE3\x00\x03\xFA') # flags
        ntpdata += bytearray(b'\x00\x01\x00\x00\x00\x01\x00\x00') # Root delay and dispersian
        ntpdata += bytearray(b'\x00\x00\x00\x00')                 # Reference ID
        ntpdata += bytearray(b'\x00\x00\x00\x00\x00\x00\x00\x00') # Reference timestamp
        ntpdata += bytearray(b'\x00\x00\x00\x00\x00\x00\x00\x00') # Origin timestamp
        ntpdata += bytearray(b'\x00\x00\x00\x00\x00\x00\x00\x00') # Receive timestamp
        ntpdata += now_1900.to_bytes(4, byteorder='big', signed=False)
        ntpdata += now_1900_rem.to_bytes(4, byteorder='big', signed=False)
        
        target = i_targets[inst].pop(0)
        i_targets['tasks'].append(ctrl.do_udpprobe(target[2], dport=123, payload=ntpdata, userid=target[3], inst=inst))


'''
   result methods decode input from do_measure into values for writing to the database
   input: list with timestart start and return values from callback method
      ((timestamp_start, cbvalue), )

   output: dictionary list 
   ({"target1" : ( node, node_count, mean_rtt)}, {...}, {"target1" : ("mean", node_count, mean_rtt)})
   
   special case: node = "mean" is mean value of all round trip values for this target   
'''

def result_ping(ts_start, results):
    retvalues = {}
    
    for result in results:

#        dst=str(result[1].dst)
        dst = list_targets[result[1].userid].split('#')[0]

        try:
            ms = round(result[1].min_rtt.total_seconds()*1000)
            node_cnt = 1
        except AttributeError:
            ms = 0
            node_cnt = 0
        except:
            raise()
        
        try:
            retvalues[dst].append((result[1].inst.name, node_cnt, ms))
        except KeyError:
            retvalues[dst] = []
            retvalues[dst].append((result[1].inst.name, node_cnt, ms))
        except:
            raise()

    return (add_mean_values(retvalues))


def result_http(ts_start, results):
    retvalues = {}

    for result in results:

        dst = result[1].url
#        dst=lookup_httpserver[result[1].userid]

        try:
            ts_diff = round(1000*(result[0]-result[1].start).total_seconds())
            node_cnt = 1
        except AttributeError:
            ts_diff = 0
            node_cnt = 0
        except:
            raise()

        try:
            retvalues[dst].append((result[1].inst.name, node_cnt, ts_diff))
        except KeyError:
            retvalues[dst] = []
            retvalues[dst].append((result[1].inst.name, node_cnt, ts_diff))
        except:
            raise()

    return (add_mean_values(retvalues))


def result_dns(ts_start, results):
    retvalues = {}

    for result in results:
        dst=lookup_nameserver[result[1].userid]

        try:
            rtt = round(1000*result[1].rtt.total_seconds())
            node_cnt = 1
        except AttributeError:
            rtt = 0
            node_cnt = 0
        except:
            raise()

        try:
            retvalues[dst].append((result[1].inst.name, node_cnt, rtt))
        except KeyError:
            retvalues[dst] = []
            retvalues[dst].append((result[1].inst.name, node_cnt, rtt))
        except:
            raise()
        
    return (add_mean_values(retvalues))


def result_smtp(ts_start, results):
    retvalues = {}

    for result in results:
        dst = list_targets[result[1].userid].split('#')[0]

        try:
            rtt = round(result[1].min_rtt.total_seconds()*1000)
            node_cnt = 1
        except AttributeError:
            rtt = 0
            node_cnt = 0
        except:
            raise()
        
        try:
            retvalues[dst].append((result[1].inst.name, node_cnt, rtt))
        except KeyError:
            retvalues[dst] = []
            retvalues[dst].append((result[1].inst.name, node_cnt, rtt))
        except:
            raise()

    return (add_mean_values(retvalues))


def result_ntp(ts_start, results):
    retvalues = {}

    for result in results:
        dst = list_targets[result[1].userid].split('#')[0]

        try:
            ts_diff = round(1000*(result[0]-result[1].start).total_seconds())
            node_cnt = 1
        except AttributeError:
            ts_diff = 0
            node_cnt = 0
        except:
            raise()

        try:
            retvalues[dst].append((result[1].inst.name, node_cnt, ts_diff))
        except KeyError:
            retvalues[dst] = []
            retvalues[dst].append((result[1].inst.name, node_cnt, ts_diff))
        except:
            raise()
        
    return (add_mean_values(retvalues))


def add_mean_values(m_values):
    for dst in m_values.keys():
        node_cnt = len(m_values[dst])
        r_sum = 0
        for row in m_values[dst]:
            if row[1] == 1: # node has a value
                r_sum += row[2]
            else:
                node_cnt -= 1                
        if node_cnt > 0:
            m_values[dst].append(("mean", node_cnt, round(r_sum/node_cnt)))
        else:
            m_values[dst].append(("mean", 0, 0))
    return(m_values)


'''
    do_measure - do the measurement for different types of tests
    cb_method: the call back function for this specific test type
    result_method: based on the measurement type the results need to be decoded
    targets: primary targets of the measurements
    targets_ip: IP address of targets if m_targets is _not_ ip address, but url's
    
    do_measure calls the callback method for retrieving the measurement data.
    with the measurement data it's calling the result_method for converting the results 
    into the final return values.
    
    result_method function must be able to interpret data from the callback method.
    These two functions are tight together.
    The results from callback method are stored in a list with the current timestamp and the results, like:
    ((timestamp, resultObject), )
    This list is input for the result_method.
    
    return values, list of:
    (('target', 'node count', 'mean rtt'), )
    i.e.: (('1.2.3.4', 50, 3), ('www.example.com', 10, 4))
        
'''            
def do_measure(logger, event_quit, cb_method, result_method, ipversion, targets, nodes):
    retvalues = []
    i_targets = {}
    
    ctrl = scamper.ScamperCtrl(morecb=cb_method, param=i_targets)
    timestamp_start = datetime.now(tz=timezone.utc).timestamp()
    i_targets['tasks'] = [] # ScamperTask objects of this measurement method
    for node in nodes:
        try:
            inst = ctrl.add_remote(node)
        except:
            logger.warning(f"do_measure - cannot add node {node}, perhaps it's lost in the mean time")
        i_targets[inst] = targets.copy()


    while not ctrl.is_done():
        if (event_quit.is_set()):
            break

        retval = None
        try:
            retval = ctrl.poll(timeout=timedelta(seconds=15))
        except Exception as e:
            exctype, excvalue = sys.exc_info()[:2]
            logger.warning(f"do_measure - got exception on {cb_method.__name__}{ipversion}): {e} ({exctype}: {excvalue})")
            continue
                
        # if ctrl.poll() returns None, either all measurements are
        # complete, or we timed out.  say what happened.
        if retval is None:
            if not ctrl.is_done():
                logger.warning(f"do_measure - timed out on measurement occurred (callback {cb_method.__name__} for IPv{ipversion})")
                logger.info(f"do_measure - there are {ctrl.instc} instances in the list and {ctrl.taskc} tasks.")
                logger.info(f"do_measure - there are now {len(i_targets['tasks'])} tasks left for {cb_method.__name__}{ipversion}")
                ctrl.done()
                loopcnt = 0
                while(ctrl.instc):
                    if (event_quit.is_set()):
                        logger.info("do_measure - event Quit received in timeout loop. Break out!")
                        break
                    if loopcnt >= 10:
                        logger.warning("do-measure - tried to stop timed out tasks, but failed. Quit and restart all over.")
                        for tsk in i_targets['tasks']:
                            logger.warning("do_measure - halt task")
                            tsk.halt()
                        time.sleep(2)
                        event_quit.set()
                        break
                    loopcnt += 1
                    for instc in ctrl.instances():
                        logger.info(f"do_measure - instance {instc.name} has {instc.taskc} task(s) active ({loopcnt})")
                        instc.done()
                    time.sleep(1)
            break
        
        retvalues.append((datetime.now(tz=timezone.utc), retval))
        
    return(result_method(timestamp_start, retvalues))
