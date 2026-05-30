**Iteration one: May 16th**

- For sample data, I tried to find the overlap in records (dates specifically) with trip data (under open source), operator trips (sample data), operator trips (sample data), and station stats (sample data). The only date that's possible would be April 27th because the open source trip data is only up to april 2026. 
- use all-shortages to double check if calculations are correct (there's more than one entries of 04-27 in the file)
- initial thoughts on rough calculations would be:
        
        ORIGINAL (Station Sample Data\STATION_STATS_EXPORT-1676.csv)
            - STATION CAPACITY - Total Docks Installed
            - INITIAL BIKES - careful about data since it's a string with two types of bikes: fit vs efit, ie in the form of "fit: 6, efit: 11" for column Total Bikes At Station Per Model
        TRIPS 
            - CUSTOMER TRIPS (Open Source Scraped Data\Trip Data April 2026 WRPC.csv) Start Date or End Date match (issue - don't have vehicle type - ie EFIT or FIT)
            - OPERATOR TRIPS (Station Sample Data\data-specialist-all-operator-trips.csv) Start Date or End Date match
<!-- 
        Build a CSV file that combine the customer + operators trips on the date 04-27-2026 into one table: make sure that all trip information is aligned and in the end they are all organized by chronological order. ignore the field for bike model under operator trips, assume all bikes are the same. other than that, make sure to retain the rider type ie. member or tech to differentiate the two, long lat information is in the station_locations_0516.json file, match it with the stations, - on the new table, it should have the startstation lon, start station lat, end has the same fields
-->

        
        Build a CSV file that calculates the "real time" amount of bikes at a given station. assume that we start with the given amount of bikes (INITIAL BIKES) (add all of this to the new table form the stations stats), then looking at all of the customer trips and operator trips on the date 04-27-2026, with each trip