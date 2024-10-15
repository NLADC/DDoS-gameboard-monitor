'''

    gbmdb - Gameboard monitoring database classes

   
    @author: Pim van Stam
    @copyright: S3group, 2024
    @since: 10-09-2024
    @version: 1.0
    
    database classes defined are:
    m_db() - influxdb class
    
    methods of databases classes are:
    - __repr__ and __str__: representation of the class
    - load_dbconfig() : get configuraton for the database connection in a dictionary
    - connect() : connect to the database server
    - write() : write measurement data to the database   
'''

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS


class MDb():
    def __init__(self, dbtype="influxdb2", url=None, api_token=None, org=None, bucket=None):
        self.dbtype = dbtype
        self.url = url
        self.api_token = api_token
        self.org = org
        self.bucket = bucket
        self.client = None
        self.client_write = None
    
    def __repr__(self):
        return(f"Database configuration:\n  type = {self.dbtype}\n"
               f"  url = {self.url}\n"
               f"  api_token = {self.api_token}\n"
               f"  org = {self.org}\n"
               f"  bucket = {self.bucket}\n"
              )

    def _str__(self):
        return(self.__repr__())


    def load_dbconfig(self, cfg):
        '''
            Load properties from the "database" part of the config dictionary
        '''
        try:
            self.url = cfg["url"]
        except:
            self.url = None

        try:
            self.api_token = cfg["token"]
        except:
            self.api_token = None
            
        try:
            self.org = cfg["org"]
        except:
            self.org = None

        try:
            self.bucket = cfg["bucket"]
        except:
            self.bucket = None
            

    def connect(self):
        self.client = influxdb_client.InfluxDBClient(url=self.url, token=self.api_token, org=self.org)
        self.client_write = self.client.write_api(write_options=SYNCHRONOUS)
        return self.client.ping()

    
    def write(self, m_type, ts, m_target, m_party, m_node, m_nrnodes, m_rtt):
        record_data = [{"measurement": m_type, 
                          "tags": {"target": m_target, "node": m_node, "party": m_party},
                          "fields": {"rtt": m_rtt, "node_count": m_nrnodes},
                          "time": ts}]
        self.client_write = self.client.write_api()
        retval = self.client_write.write(bucket=self.bucket, org=self.org,
                        record=record_data, write_precision=influxdb_client.WritePrecision.S)
        return retval
        