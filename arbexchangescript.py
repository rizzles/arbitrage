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
mtgox_url = 'https://data.mtgox.com/api/1/BTCUSD/ticker'

campbx_price = 0.00
coinbase_price = 0.00
mtgox_price = 0.00
difference = 0.00
difference2 = 0.00


def find_diff():
    print "Finding price difference..."
    minutediff = {}
    hourdiff = {}
    daydiff = {}
    prices = collection.find().sort('_id',1)

    minuteprices = mongodb.minute.find().sort('_id',1)
    minutecheck = {}
    for m in minuteprices:
        minutecheck[m['stamp']] = m['diff']

    hourprices = mongodb.coinbasehourly.find().sort('_id',1)
    hour2prices = mongodb.mtgoxhourly.find().sort('_id',1)
    hourcheck = {}
    hour2check = {}
    for m in hourprices:
        hourcheck[m['stamp']] = m['diff']
    for m in hour2prices:
        hour2check[m['stamp']] = m['diff2']

    dailyprices = mongodb.coinbasedaily.find().sort('_id',1)
    daily2prices = mongodb.mtgoxdaily.find().sort('_id',1)
    dailycheck = {}
    daily2check = {}
    for m in dailyprices:
        dailycheck[m['stamp']] = m['diff']
    for m in daily2prices:
        daily2check[m['stamp']] = m['diff2']

    hourhigh = {}
    dayhigh = {}
    hour2high = {}
    day2high = {}

    for price in prices:
        if not price.has_key('diff2'):
            continue

        if not price.has_key('mtgox'):
            price['mtgox'] = 0.00

        if price['time'].minute < 10:
            minute = "0%s"%price['time'].minute
        else:
            minute = "%s"%price['time'].minute


        # minute data
        minutestamp = "%s %s %s:%s"%(months[price['time'].month], days[price['time'].day], price['time'].hour, minute)
        minutediff[minutestamp] = {'diff': price['diff'], 'campbx':price['campbx'], 'coinbase':price['coinbase'], 'stamp':minutestamp, 'diff2':price['diff2'], 'mtgox':price['mtgox']}
        if not minutecheck.has_key(minutestamp):
            mongodb.minute.update({'stamp':minutestamp}, minutediff[minutestamp], True)



        # hourly data
        hourstamp = "%s %s %s:00"%(months[price['time'].month], days[price['time'].day], price['time'].hour)
        if not hourhigh.has_key(hourstamp):
            hourhigh[hourstamp] = price['diff']
        if not hour2high.has_key(hourstamp):
            hour2high[hourstamp] = price['diff2']
        hourdiff[hourstamp] = {'diff': price['diff'], 'campbx':price['campbx'], 'coinbase':price['coinbase'], 'stamp':hourstamp, 'diff2':price['diff2'], 'mtgox':price['mtgox']}

        # hourly high for campbx-coinbase
        if not hourcheck.has_key(hourstamp):
            mongodb.coinbasehourly.update({'stamp':hourstamp}, hourdiff[hourstamp], True)
            hourhigh[hourstamp] = price['diff']
        else:
            if price['diff'] > hourhigh[hourstamp]:
                hourhigh[hourstamp] = price['diff']
                mongodb.coinbasehourly.update({'stamp':hourstamp}, hourdiff[hourstamp], True)

        # hourly high for campbx-mtgox
        if not hour2check.has_key(hourstamp):
            mongodb.mtgoxhourly.update({'stamp':hourstamp}, hourdiff[hourstamp], True)
            hour2high[hourstamp] = price['diff2']
        else:
            if price['diff2'] > hour2high[hourstamp]:
                hour2high[hourstamp] = price['diff2']
                mongodb.mtgoxhourly.update({'stamp':hourstamp}, hourdiff[hourstamp], True)



        # daily data
        daystamp = "%s %s"%(months[price['time'].month], days[price['time'].day])
        if not dayhigh.has_key(daystamp):
            dayhigh[daystamp] = price['diff']
        if not day2high.has_key(daystamp):
            day2high[daystamp] = price['diff2']
        daydiff[daystamp] = {'diff': price['diff'], 'campbx':price['campbx'], 'coinbase':price['coinbase'], 'stamp':daystamp, 'diff2':price['diff2'], 'mtgox':price['mtgox']}
        
        if not dailycheck.has_key(daystamp):
            mongodb.coinbasedaily.update({'stamp':daystamp}, daydiff[daystamp], True)
            dayhigh[daystamp] = price['diff']
        else:
            if price['diff'] > dayhigh[daystamp]:
                dayhigh[daystamp] = price['diff']
                mongodb.coinbasedaily.update({'stamp':daystamp}, daydiff[daystamp], True)

        if not daily2check.has_key(daystamp):
            mongodb.mtgoxdaily.update({'stamp':daystamp}, daydiff[daystamp], True)
            day2high[daystamp] = price['diff2']
        else:
            if price['diff2'] > day2high[daystamp]:
                day2high[daystamp] = price['diff2']
                mongodb.mtgoxdaily.update({'stamp':daystamp}, daydiff[daystamp], True)



while True:
    #find_diff()
    #sys.exit()

    print "Sleeping... "
    print ""
    time.sleep(TIMEOUT)

    coinbase_http_client = tornado.httpclient.HTTPClient()
    campbx_http_client = tornado.httpclient.HTTPClient()    
    mtgox_http_client = tornado.httpclient.HTTPClient()    


    # campbx price
    try:
        campbx_response = campbx_http_client.fetch(campbx_url)
        print "Campbx:", campbx_response.body
        campbx_price = tornado.escape.json_decode(campbx_response.body)
        campbx_price = float(campbx_price['Best Ask'])
    except Exception as e:
        logging.error("Error encountered when getting campbx price:", e)
        continue
    finally:
        campbx_http_client.close()

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


    # mtgox price
    try:
        mtgox_response = mtgox_http_client.fetch(mtgox_url)
        mtgox_price = tornado.escape.json_decode(mtgox_response.body)
        print "MtGox:", mtgox_price['return']
        mtgox_price = float(mtgox_price['return']['buy']['value'])
    except Exception as e:
        logging.error("Error encountered getting mtgox price:", e)
        continue
    finally:
        mtgox_http_client.close()

    difference = coinbase_price - campbx_price
    difference2 = mtgox_price - campbx_price

    price_data = {'coinbase':coinbase_price, 'campbx':campbx_price, 'diff':difference, 'time':datetime.datetime.now(), 'mtgox':mtgox_price, 'diff2':difference2}
    print "Data: ",price_data
    collection.insert(price_data)
        
    find_diff()
