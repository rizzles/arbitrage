#!/usr/bin/python

import logging
import os
import time
import datetime
import pymongo
import sys

import tornado.ioloop
import tornado.web
import tornado.options
import tornado.httpserver
import tornado.httpclient
import tornado.escape
import tornado.websocket
import tornado.gen

TIMEOUT = 120
months = {1:'Jan',2:'Feb',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'Sept',10:'Oct',11:'Nov',12:'Dec'}
days = {1:'1st', 2:'2nd', 3:'3rd', 4:'4th', 5:'5th', 6:'6th', 7:'7th', 8:'8th', 9:'9th', 10:'10th', 11:'11th', 12:'12th', 13:'13th', 14:'14th', 15:'15th', 16:'16th', 17:'17th', 18:'18th', 19:'19th', 20:'20th', 21:'21st', 22:'22nd', 23:'23rd', 24:'24th', 25:'25th', 26:'26th', 27:'27th', 28:'28th', 29:'29th', 30:'30th', 31:'31st'}

#mongoconnection = pymongo.Connection('54.227.251.253', 27017)
mongoconnection = pymongo.Connection('ec2-54-227-251-253.compute-1.amazonaws.com', 27017)
mongodb = mongoconnection.arb
collection = mongodb.price

coinbase_url = 'https://coinbase.com/api/v1/prices/sell'
campbx_url = 'http://CampBX.com/api/xticker.php'

campbx_price = 0.00
coinbase_price = 0.00
difference = 0.00


def find_diff():
    print "Finding price difference..."
    hourdiff = {}
    daydiff = {}
    prices = collection.find().sort('_id',1)
    for price in prices:

        hourstamp = "%s %s %s:00"%(months[price['time'].month], days[price['time'].day], price['time'].hour)
        if not hourdiff.has_key(hourstamp):
            hourdiff[hourstamp] = {'diff': 0.00, 'campbx':price['campbx'], 'coinbase':price['coinbase'], 'stamp':hourstamp}
            mongodb.hourly.update({'hourstamp':hourstamp}, hourdiff[hourstamp], False)

        daystamp = "%s %s"%(months[price['time'].month], days[price['time'].day])
        if not daydiff.has_key(daystamp):
            daydiff[daystamp] = {'diff': 0.00, 'campbx':price['campbx'], 'coinbase':price['coinbase'], 'stamp':daystamp}
            mongodb.daily.update({'daystamp':daystamp}, daydiff[daystamp], False)


        if price['diff'] > hourdiff[hourstamp]['diff']:
            hourdiff[hourstamp] = {'diff': price['diff'], 'campbx':price['campbx'], 'coinbase':price['coinbase'], 'stamp':hourstamp}
            mongodb.hourly.update({'stamp':hourstamp}, hourdiff[hourstamp], True)

        if price['diff'] > daydiff[daystamp]['diff']:
            daydiff[daystamp] = {'diff': price['diff'], 'campbx':price['campbx'], 'coinbase':price['coinbase'], 'stamp':daystamp}
            mongodb.daily.update({'stamp':daystamp}, daydiff[daystamp], True)


while True:
    #find_diff()
    #sys.exit()

    print "Sleeping... "
    print ""
    time.sleep(TIMEOUT)

    find_diff()

    coinbase_http_client = tornado.httpclient.HTTPClient()
    campbx_http_client = tornado.httpclient.HTTPClient()    

    # coinbase price
    try:
        coinbase_response = coinbase_http_client.fetch(coinbase_url)
        print "Coinbase:", coinbase_response.body
        coinbase_price = tornado.escape.json_decode(coinbase_response.body)
        coinbase_price = float(coinbase_price['amount'])
    except Exception as e:
        logging.error("Error encountered when getting coinbase price:", e)
        continue
    finally:
        coinbase_http_client.close()

    # campbx price
    try:
        campbx_response = campbx_http_client.fetch(campbx_url)
        print "Campbx:", campbx_response.body
        campbx_price = tornado.escape.json_decode(campbx_response.body)
        campbx_price = float(campbx_price['Last Trade'])
    except Exception as e:
        logging.error("Error encountered when getting campbx price:", e)
        continue
    finally:
        campbx_http_client.close()

    difference = coinbase_price - campbx_price

    price_data = {'coinbase':coinbase_price, 'campbx':campbx_price, 'diff':difference, 'time':datetime.datetime.now()}
    print price_data
    collection.insert(price_data)
        
