#!/usr/bin/python

import os
import sys
import logging
import datetime
import urlparse
import uuid
import urllib2
import locale
import time

import tornado.escape
import tornado.httpclient

import btceapi

btc_e_fee = 0.002
btc_e_fee2 = 0.005
amount = 1.0
executetrade = 1.015

logging.basicConfig(level=logging.INFO)
http_client = tornado.httpclient.HTTPClient()


while (True):
    logging.info("Sleeping 5 seconds")
    time.sleep(5)


    # Branch to check if current orders are too old
    handler = btceapi.KeyHandler('key_file')

    for key in handler.getKeys():
        t = btceapi.TradeAPI(key, handler=handler)
        # Balance, etc
        try:
            orders = t.orderList()
        except:
            logging.error('No orders')
            orders = []
        handler.setNextNonce(key, handler.getNextNonce(key))
    handler.save('key_file')

    if orders:
        for order in orders:
            if (datetime.datetime.now() - order.timestamp_created) > datetime.timedelta(minutes=120):
                # orders are old and not getting filled. Canceling orders
                print "old order. Canceling"
                handler = btceapi.KeyHandler('key_file')
                for key in handler.getKeys():
                    t = btceapi.TradeAPI(key, handler=handler)
                    t.cancelOrder(order.order_id)
                    handler.setNextNonce(key, handler.getNextNonce(key))
                handler.save('key_file')


    # Check if to many open orders
    if len(orders) > 19:
        print "Way too many open orders. Continuing."
        continue


    # btc_usd
    try:
        response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
        btc_usd = tornado.escape.json_decode(response.body)
    except:
        logging.error("Error retreiving btc_usd btc-e json")
        continue

    """
    # btc_eur
    try:
        response = http_client.fetch("https://btc-e.com/api/2/btc_eur/ticker")
        btc_eur = tornado.escape.json_decode(response.body)
    except:
        logging.error("Error retreiving btc_eur btc-e json")
        continue

    # btc_rur
    try:
        response = http_client.fetch("https://btc-e.com/api/2/btc_rur/ticker")
        btc_rur = tornado.escape.json_decode(response.body)
    except:
        logging.error("Error retreiving btc_rur btc-e json")
        continue
    """
    # ltc_btc
    try:
        response = http_client.fetch("https://btc-e.com/api/2/ltc_btc/ticker")
        ltc_btc = tornado.escape.json_decode(response.body)
    except:
        logging.error("Error retreiving ltc_btc btc-e json")
        continue

    # ltc_usd
    try:
        response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
        ltc_usd = tornado.escape.json_decode(response.body)
    except:
        logging.error("Error retreiving ltc_usd btc-e json")
        continue
    """
    # ltc_rur
    try:
        response = http_client.fetch("https://btc-e.com/api/2/ltc_rur/ticker")
        ltc_rur = tornado.escape.json_decode(response.body)
    except:
        logging.error("Error retreiving ltc_rur btc-e json")
        continue


    # eur_usd
    try:
        response = http_client.fetch("https://btc-e.com/api/2/eur_usd/ticker")
        eur_usd = tornado.escape.json_decode(response.body)
    except:
        logging.error("Error retreiving eur_usd btc-e json")


    # usd_rur
    try:
        response = http_client.fetch("https://btc-e.com/api/2/usd_rur/ticker")
        usd_rur = tornado.escape.json_decode(response.body)
    except:
        logging.error("Error retreiving usd_rur btc-e json")
        continue
    """

    # [ARB1] BTC 2 USD 2 LTC 2 BTC
    btc2usd= (amount * btc_usd['ticker']['buy'])* (1-btc_e_fee) # sell BTC for USD
    usd2ltc= (btc2usd / ltc_usd['ticker']['sell'])* (1-btc_e_fee) # buy LTC for USD
    ltc2btc= (usd2ltc * ltc_btc['ticker']['buy'])* (1-btc_e_fee) # sell LTC for BTC

    if ltc2btc > executetrade:
        print "Executing ARB1 trade"
        handler = btceapi.KeyHandler('key_file')

        # sell BTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = btc_usd['ticker']['buy']
            r = t.trade(pair="btc_usd", trade_type="sell", rate=rate, amount=amount)
            total = (amount * rate) * (1-btc_e_fee)
            print "BTC_USD"
            print "price", rate
            print "total USD with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # buy LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_usd['ticker']['sell']
            buy = (total / rate)
            r = t.trade(pair="ltc_usd", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print ""
            print "LTC_USD"
            print "price", rate
            print "total LTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # sell LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_btc['ticker']['buy']
            r = t.trade(pair="ltc_btc", trade_type="sell", rate=rate, amount=total)
            total = (total * rate) * (1-btc_e_fee)
            print ""
            print "LTC_BTC"
            print "price", rate
            print "total BTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))
            
        handler.save('key_file')
        #sys.exit()


    # [ARB2] BTC 2 LTC 2 USD 2 BTC
    btc2ltc= (amount / ltc_btc['ticker']['sell'])* (1-btc_e_fee) # buy LTC for BTC
    ltc2usd= (btc2ltc * ltc_usd['ticker']['buy'])* (1-btc_e_fee) # sell LTC for USD
    usd2btc= (ltc2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # buy LTC for USD

    if usd2btc > executetrade:
        print "Executing ARB2 trade"
        handler = btceapi.KeyHandler('key_file')
        # buy LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_btc['ticker']['sell']
            buy = (amount / rate)
            r = t.trade(pair="ltc_btc", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print "LTC_BTC"
            print "price", rate
            print "total LTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # sell LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_usd['ticker']['buy']
            r = t.trade(pair="ltc_usd", trade_type="sell", rate=rate, amount=total)
            total = (total * rate) * (1-btc_e_fee)
            print ""
            print "LTC_USD"
            print "price", rate
            print "total USD with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # buy BTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = btc_usd['ticker']['sell']
            buy = (total / rate)
            r = t.trade(pair="btc_usd", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print ""
            print "BTC_USD"
            print "price", rate
            print "total BTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        handler.save('key_file')
        #sys.exit()

    continue
    """
    # [ARB3] BTC 2 EUR 2 USD 2 BTC
    btc2eur= (amount * btc_eur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for EUR
    eur2usd= (btc2eur * eur_usd['ticker']['buy'])* (1-btc_e_fee) # buy USD with EUR
    usd2btc= (eur2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # buy BTC with USD

    if usd2btc > executetrade:
        print "Executing ARB3 trade"
    """


    # [ARB4] BTC 2 RUR 2 USD 2 BTC
    btc2rur= (amount * btc_rur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for RUR 
    rur2usd= (btc2rur / usd_rur['ticker']['sell'])* (1-btc_e_fee2) # sell RUR for USD 
    usd2btc= (rur2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # sell USD for BTC

    if usd2btc > executetrade:
        print "Executing ARB4 trade"
        handler = btceapi.KeyHandler('key_file')

        # sell BTC
        for key in handler.keys.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = btc_rur['ticker']['buy']
            r = t.trade(pair="btc_rur", trade_type="sell", rate=rate, amount=amount)
            total = (amount * rate) * (1-btc_e_fee)
            print "BTC_RUR"
            print "price", rate
            print "total RUR with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # buy USD
        for key in handler.keys.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = usd_rur['ticker']['sell']
            buy = (total / rate)
            r = t.trade(pair="usd_rur", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print ""
            print "USD_RUR"
            print "price", rate
            print "total USD with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # buy BTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = btc_usd['ticker']['sell']
            buy = (total / rate)
            r = t.trade(pair="btc_usd", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print ""
            print "BTC_USD"
            print "price", rate
            print "total BTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        handler.save('key_file')
        #sys.exit()


    # [ARB5] BTC 2 RUR 2 LTC 2 BTC
    btc2rur= (amount * btc_rur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for RUR
    rur2ltc= (btc2rur / ltc_rur['ticker']['sell'])* (1-btc_e_fee) # sell RUR for LTC
    ltc2btc= (rur2ltc * ltc_btc['ticker']['buy'])* (1-btc_e_fee) # sell LTC for BTC

    if ltc2btc > executetrade:
        print "Executing ARB5 trade"
        handler = btceapi.KeyHandler('key_file')

        # sell BTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = btc_rur['ticker']['buy']
            r = t.trade(pair="btc_rur", trade_type="sell", rate=rate, amount=amount)
            total = (amount * rate) * (1-btc_e_fee)
            print "BTC_RUR"
            print "price", rate
            print "total RUR with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))
            
        # buy LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_rur['ticker']['sell']
            buy = (total / rate)
            r = t.trade(pair="ltc_rur", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print ""
            print "LTC_RUR"
            print "price", rate
            print "total LTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # sell LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_btc['ticker']['buy']
            r = t.trade(pair="ltc_btc", trade_type="sell", rate=rate, amount=total)
            total = (total * rate) * (1-btc_e_fee)
            print ""
            print "LTC_BTC"
            print "price", rate
            print "total BTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        handler.save('key_file')
        #sys.exit()

    # [ARB6] LTC 2 RUR 2 USD 2 LTC
    ltc2rur= (amount * ltc_rur['ticker']['buy'])* (1-btc_e_fee) # sell LTC for RUR
    rur2usd= (ltc2rur / usd_rur['ticker']['sell'])* (1-btc_e_fee2) # sell RUR for USD
    usd2ltc= (rur2usd / ltc_usd['ticker']['sell'])* (1-btc_e_fee) # sell USD for LTC

    if usd2ltc > executetrade:
        print "Executing ARB6 trade"
        handler = btceapi.KeyHandler('key_file')

        # sell LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_rur['ticker']['buy']
            r = t.trade(pair="ltc_rur", trade_type="sell", rate=rate, amount=amount)
            total = (amount * rate) * (1-btc_e_fee)
            print "LTC_RUR"
            print "price", rate
            print "total RUR with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # buy USD
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = usd_rur['ticker']['sell']
            buy = (total / rate)
            r = t.trade(pair="usd_rur", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print ""
            print "USD_RUR"
            print "price", rate
            print "total USD with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # buy LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_usd['ticker']['sell']
            buy = (total / rate)
            r = t.trade(pair="ltc_usd", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print ""
            print "LTC_USD"
            print "price", rate
            print "total LTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        handler.save('key_file')
        #sys.exit()

    # [ARB 7] LTC 2 USD 2 RUR 2 LTC
    ltc2usd= (amount * ltc_usd['ticker']['buy'])* (1-btc_e_fee) # sell LTC for USD
    usd2rur= (ltc2usd * usd_rur['ticker']['buy'])* (1-btc_e_fee2) # sell USD for RUR
    rur2ltc= (usd2rur / ltc_rur['ticker']['sell'])* (1-btc_e_fee) # sell RUR for LTC

    if rur2ltc > executetrade:
        print "Executing ARB7 trade"
        handler = btceapi.KeyHandler('key_file')

        # sell LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_usd['ticker']['buy']
            r = t.trade(pair="ltc_usd", trade_type="sell", rate=rate, amount=amount)
            total = (amount * rate) * (1-btc_e_fee)
            print ""
            print "LTC_USD"
            print "price", rate
            print "total USD with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # sell USD
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = usd_rur['ticker']['buy']
            r = t.trade(pair="usd_rur", trade_type="sell", rate=rate, amount=total)
            total = (total * rate) * (1-btc_e_fee)
            print ""
            print "USD_RUR"
            print "price", rate
            print "total RUR with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        # buy LTC
        for key in handler.getKeys():
            t = btceapi.TradeAPI(key, handler=handler)
            rate = ltc_rur['ticker']['sell']
            buy = (total / rate)
            r = t.trade(pair="ltc_rur", trade_type="buy", rate=rate, amount=buy)
            total = buy * (1-btc_e_fee)
            print ""
            print "LTC_RUR"
            print "price", rate
            print "total LTC with fee", total
            handler.setNextNonce(key, handler.getNextNonce(key))

        handler.save('key_file')
        #sys.exit()
