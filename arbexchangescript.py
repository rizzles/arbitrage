#!/usr/bin/python

import logging
import os
import time
import datetime
import pymongo

import tornado.ioloop
import tornado.web
import tornado.options
import tornado.httpserver
import tornado.httpclient
import tornado.escape
import tornado.websocket
import tornado.gen

TIMEOUT = 15

mongoconnection = pymongo.Connection('54.227.251.253', 27017)
mongodb = mongoconnection.arb
collection = mongodb.price

coinbase_url = 'https://coinbase.com/api/v1/prices/sell'
campbx_url = 'http://CampBX.com/api/xticker.php'

campbx_price = 0.00
coinbase_price = 0.00
difference = 0.00

while True:
    coinbase_http_client = tornado.httpclient.HTTPClient()
    campbx_http_client = tornado.httpclient.HTTPClient()    

    # coinbase price
    try:
        coinbase_response = coinbase_http_client.fetch(coinbase_url)
        print "Coinbase:", coinbase_response.body
        coinbase_price = tornado.escape.json_decode(coinbase_response.body)
    except tornado.httpclient.HTTPError as e:
        logging.error("Error encountered when getting coinbase price:", e)
    finally:
        coinbase_http_client.close()

    # campbx price
    try:
        campbx_response = campbx_http_client.fetch(campbx_url)
        print "Campbx:", campbx_response.body
        campbx_price = tornado.escape.json_decode(campbx_response.body)
    except tornado.httpclient.HTTPError as e:
        logging.error("Error encountered when getting campbx price:", e)
    finally:
        campbx_http_client.close()


    coinbase_price = float(coinbase_price['amount'])
    campbx_price = float(campbx_price['Last Trade'])
    difference = coinbase_price - campbx_price

    price_data = {'coinbase':coinbase_price, 'campbx':campbx_price, 'diff':difference, 'time':datetime.datetime.now()}
    print price_data
    collection.insert(price_data)
        
    print "Sleeping... "
    print ""
    time.sleep(TIMEOUT)
