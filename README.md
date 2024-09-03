# gameboard-monitoring



## Getting started

Gemaboard monitoring is the monitoring application coming along with the Gameboard logging application.

The Gameboard is the application to support the yearly DDoS exercise in The Netherlands with the government and other critical infrastructures, like banks.

The monitoring application is currently based on Caida Ark for measurements. In the past Ripe Atlas was used, but didn't exactly fit in the need for the gameboard monitoring.


## Components

* Caida Ark network
* Scamper application, running on Ark nodes
* Amazon Timeseries for storing measurement data
* Grafana for graphs of the output

Gameboard-monitoring is using Caida Ark for measurements from over the whole world to the defined targets. Data from the measurements is storing in a timeseries database, like influxdb. Amazon Timeseries is used for this purpose. Display graphs is done with Grafana on a monitoring server.

## monitoring application

The application will run on Ark nodes, with scamper.

Elements of the application are

* configuration
    * target hosts (IP and url's)
    * type of measurements (ping, weburl, tcp port)
    * database configuration
* measurements
* storing output in timeseries database

Grafana runs on a separate host and is not using caida Ark. Elements are:
* retrieve data from timeseries database
* graph the data
* retrieve log items from the Gameboard logging
* plot log lines on the graphs

With plotting the log lines on the graphs you can see what effect a ddos att5ack has or the other way round, from peeks or drops in the graphs you can relate any action to this.
