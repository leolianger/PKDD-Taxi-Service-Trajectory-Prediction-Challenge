# -*- coding: utf-8 -*-
"""
Created on May 7 2018
Revised on May 12 2018
@author: Vivek M Agrawal

This module converts the csv formatted Taxi Service Trajectory data from ECML 
PKDD 2015 Prediction Challenge to format suitable for ElasticSearch ingestion.

Link to source data: www.ecmlpkdd2015.org/ 

Given large volume of data, chunking option in pandas is utilized while reading
the csv file to reduce memory load. Polyline trajectory in the input data (list 
of lists of point in time coordinates) stacked into individual location vectors
and written out to JSON format for bulk ingestion into ElasticSearch. 
"""

#!/usr/bin/env python

__author__ = "Vivek M Agrawal"
__version__ = "1.0"

import sys
import json
import pandas as pd
import numpy as np
from pprint import pprint

# define data column names to use as json tags
colNames = ["trip_id", "call_type", "customer_id", "taxi_stand_id", "taxi_id", \
"trip_start_time", "surge_rate", "partial_location_flag", "trip_location", ]

# enforce column data types
# note: np.str allows "NA" value to be read as NaN, using np.uint8 results in 
# exception for such values
# http://pandas.pydata.org/pandas-docs/stable/io.html#io-navaluesconst
colDtype = {"trip_id": np.str, "call_type": np.str, "customer_id": np.str, \
"taxi_stand_id": np.str, "taxi_id": np.str, "trip_start_time":np.uint64, \
"surge_rate": np.str, "partial_location_flag": np.bool, "trip_location":np.object}

# set file chunkCounter to store individual chunks as json formatted output
chunkCounter = 0
SKIPROWS = 0 # use this if restarting after failure
CHUNKSIZE = 1000

# http://pandas.pydata.org/pandas-docs/stable/io.html#io-chunking
# process the data file in chunks of 5000 records at a time to avoid memory issues
chunkReader = pd.read_table(".//csvData//train.csv", sep=',', header=0, \
names=colNames, dtype=colDtype, error_bad_lines=False, chunksize=CHUNKSIZE, \
skiprows=SKIPROWS)

for chunk in chunkReader:
    # # review data in the source chunk
    # pprint(chunk)
    # input()
    try:
        # convert epoch to epch_millis expected at ES
        chunk["trip_start_time"] *= 1000
    
        # split the list of geo tags for each trip from polyline map trace [list] 
        # to individual row items for each location co-ordinate
        # https://stackoverflow.com/questions/27263805/pandas-when-cell-contents-are-lists-create-a-row-for-each-element-in-the-list
        rowChunk = chunk.set_index(["trip_id", "call_type", "customer_id", \
        "taxi_stand_id", "taxi_id", "trip_start_time", "surge_rate", \
        "partial_location_flag"])["trip_location"]
    
        # convert the ingested string object in the polyplot "trip_location" to 
        # python list proper for stacking the series
        for i in range(0, len(rowChunk.values)):
            #pprint(type(rowChunk.values[i]))
            rowChunk.values[i] = json.loads(rowChunk.values[i])
            #pprint(type(rowChunk.values[i]))
            #pprint(rowChunk.values[i])
    
        # split the list of lists containing polyplot "trip_location" to individual
        # location items (by applying pd.Series operation to the rowChunk items)
        # and then stack those horizontally to create new column with chunkCounter for
        # values corresponding to the different trip locations (using the .stack()
        # method) and then reset indexes to update names for the two newly created
        # columns (using .reset_index() method)
        rowChunk = rowChunk.apply(pd.Series).stack().reset_index()
    
        # add column names back as the final step
        rowChunk.columns = ["trip_id", "call_type", "customer_id", "taxi_stand_id", \
        "taxi_id", "trip_start_time", "surge_rate", "partial_location_flag", \
        "trip_instance_id", "trip_instance_location"]
        
        # write the updated data frame to json object after orienting by records to
        # get output formatted list like [{column -> value}, ... , {column -> value}]
        with open(str(".//jsonData//rowChunk_"+str(chunkCounter)+".json"), 'w') as f:
            f.write(rowChunk.to_json(orient='records'))
        # to view contents of the output file, use: 
        # cat rowChunk_0.json | python -m json.tool > rowChunk_0-pretty.json
    
        # increment chunk chunkCounter and continue until end of file
        chunkCounter += 1
        
        if (chunkCounter%100) == 0:
            print("Processed chunk # {}...\n".format(chunkCounter))
            
    except Exception as e:
        print("\n\nTerminated after processing chunk # {}...".format(chunkCounter))
        sys.exit()
