'''
Created on 27 Sept 2024

@author: pim
'''
import gbcommon
import gbapi
from urllib.parse import urlparse
import http.client
import logging

GBCONF = "gbm-config.yaml"
testcount=1

def run_test(msg, func, args):
    global testcount
    
    print(f"Test {testcount}: {msg}")
    testcount += 1
    retval = func(*args)
    print(retval)
    print()
    return retval


if __name__ == '__main__':
    
    '''
    http.client.HTTPConnection.debuglevel = 1
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
    '''
    
    retval = gbcommon.read_config(GBCONF)
    if (not retval[0]):
        print(f"Cannot read config, message {retval[1]}")
        exit(1)

    cfg = retval[1]
    api_domain = urlparse(cfg['general']['gameboard_api']).netloc
    api_login,api_password = gbcommon.get_credentials(f"gbapi-{api_domain}")

    gba = gbapi.GameboardApi(cfg["general"]["gameboard_api"])
    retval = gba.authenticate(api_login, api_password)
    if (not retval[0]):
        print("Not able to get data. Exit!")
        exit(1)
    else:
        print("API access authenticated")

    testcount = 1
    run_test("Retrieve DDoS tests:", gba.get_ddostests, ())
    run_test("Retrieve DDoS test 1:", gba.get_ddostests, (1,))
    run_test("Retrieve Targets of DDoS test 1:", gba.get_ddostests_targets, (1,))
    run_test("Retrieve Targets lists:", gba.get_targets, ())
    run_test("Retrieve Target 1:", gba.get_targets, (1,))
    run_test("Retrieve Measurement type of Target 1:", gba.get_targets_measurementtype, (1,))
    run_test("Retrieve Measurement types:", gba.get_measurementtypes, ())
    run_test("Retrieve Measurement type 1:", gba.get_measurementtypes, (1,))
    run_test("Retrieve Nodelist of Measurement type 1:", gba.get_measurementtypes_nodelist, (1,))
    retval = run_test("Retrieve Node lists:", gba.get_nodelists, ())
    run_test("Retrieve Node list 1:", gba.get_nodelists, (1,))
    run_test("Set status target 1 down:", gba.post_target_state, (1, 0))
    run_test("Refresh nodelist 1 with nodes", gba.put_nodelist,(1, ["nr1-nl.ark", "ams4-nl.ark", "ens5-nl.ark"]))
