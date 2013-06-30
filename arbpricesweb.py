#!/usr/bin/python

import os
import logging
import datetime
import urlparse
import uuid
import urllib2
import locale
import time
from urllib import urlencode
from hashlib import sha512
from hmac import HMAC
import base64
import json

import tornado.httpserver
import tornado.httpclient
import tornado.ioloop
import tornado.web
import tornado.escape
import tornado.options
import tornado.locale

import btceapi

btc_e_fee = 0.002
btc_e_fee2 = 0.005
amount = 1.0
ltcamount = amount * 40
executetrade = 1.020

gox_fee = 0.002
gox_key = "b6f72cf9-7d7e-40bc-a1c2-dd19aaf638bd"
gox_secret = "hKpdzLT8mZww1nWos3oze0pAtZRcsI8F0edOvUDbStK/3D4BU2WU3ggeFmxR/Jkysyyn23KjtjV4gDFGadlHaA=="

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            
            (r"/cancel_order", CancelOrderHandler),
            (r"/trade", TradeHandler),
            (r"/info", InfoHandler),
            (r"/order_history", OrderHistoryHandler),
            (r"/trade_history", TradeHistoryHandler),
            (r"/history", HistoryHandler),
            (r"/total", TotalHandler),            

            (r"/gox", GoxHandler),
        ]
        settings = dict(
            login_url="/login",
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdoP12/Vo=",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            site_name='arb',
            xsrf_cookies=True,
            autoescape=None,
            debug=True,
            gzip=True
        )
        tornado.web.Application.__init__(self, handlers, **settings)


def get_nonce():
    return int(time.time()*100000)

def sign_data(secret, data):
    return base64.b64encode(str(HMAC(secret, data, sha512).digest()))

def build_query(req={}):
    req['nonce'] = get_nonce()
    post_data = urlencode(req)
    headers = {}
    headers['User-Agent'] = "GoxApi"
    headers['Rest-Key'] = gox_key
    headers['Rest-Sign'] = sign_data(gox_secret, post_data)
    return (post_data, headers)


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("arb")
        if not user_json: 
            return None
        return tornado.escape.json_decode(user_json)


class LoginHandler(BaseHandler):
    def get(self):
        self.render('login.html')

    def post(self):
        uname = self.get_argument('uname', None)
        password = self.get_argument('password', None)

        if not uname or not password:
            self.redirect('/login')
            return

        if uname != 'kevin' or password != 'reilly':
            self.redirect('/login')
            return

        
        user = {'uname':'kevin', 'uid':'1'}
        self.set_secure_cookie("arb", tornado.escape.json_encode(user))

        self.redirect('/')


class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie('arb')
        self.clear_all_cookies()
        self.redirect('/login')


class GoxHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        http_client = tornado.httpclient.HTTPClient()
        data, headers = build_query()
        response = http_client.fetch("http://data.mtgox.com/api/1/BTCUSD/ticker")
        btc_usd = tornado.escape.json_decode(response.body)
        values = btc_usd['return']
        btc_usd = {}
        #for k,v in values.iteritems():
        #    print k,v
        btc_usd['buy'] = float(values['buy']['value'])
        btc_usd['sell'] = float(values['sell']['value'])
        total = (amount * btc_usd['buy']) * (1-gox_fee)
        
        print "BTC_USD"
        print "price", btc_usd['buy']
        print "total USD with fee", total
        self.write("BTC_USD<br>price %s<br>total USD with fee %s"%(btc_usd['buy'], total))


class HistoryHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        history = btceapi.getTradeHistory('btc_usd')
        labels = []
        data = []
        datestring = "%H:%M"
        for t in reversed(history[:20]):
            labels.append(t.date.strftime(datestring))
            print t.price
            data.append(t.price)

        self.render('history.html', history=history, labels=labels, data=data)


class InfoHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        handler = btceapi.KeyHandler('key_file')
        for key, (secret, nonce) in handler.keys.items():
            t = btceapi.TradeAPI(key, secret, nonce)
            # Balance, etc
            r = t.getInfo()
            for d in dir(r):
                if d.startswith('__'):
                    continue
                print "    %s: %r" % (d, getattr(r, d))
            handler.setNextNonce(key, t.next_nonce())
        handler.save('key_file')


class OrderHistoryHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        handler = btceapi.KeyHandler('key_file')
        for key, (secret, nonce) in handler.keys.items():
            t = btceapi.TradeAPI(key, secret, nonce)
            # Balance, etc
            try:
                orders = t.orderList()
            except:
                logging.error('No orders')
                orders = None
            handler.setNextNonce(key, t.next_nonce())
        handler.save('key_file')
        for order in orders:
            print order.pair, order.type, order.timestamp_created, order.status, order.order_id
            if (datetime.datetime.now() - order.timestamp_created) > datetime.timedelta(minutes=120):
                print "old"
        self.render('orderhistory.html', orders=orders)


class CancelOrderHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        order_id = self.get_argument('order_id')
        handler = btceapi.KeyHandler('key_file')
        for key, (secret, nonce) in handler.keys.items():
            t = btceapi.TradeAPI(key, secret, nonce)
            orders = t.cancelOrder(order_id)
            handler.setNextNonce(key, t.next_nonce())
        handler.save('key_file')

        self.redirect('/order_history')


class TradeHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        http_client = tornado.httpclient.HTTPClient()
        which = self.get_argument('which', None)
        handler = btceapi.KeyHandler('key_file')

        # ARB1
        if which == 'arb1':
            # btc_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
                btc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_usd json")
                self.write_error(500)
                return

            # ltc_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
                ltc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_usd json")
                self.write_error(500)
                return

            # ltc_btc
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_btc/ticker")
                ltc_btc = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_btc json")
                self.write_error(500)
                return

            # sell BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_usd['ticker']['buy']
                r = t.trade(pair="btc_usd", trade_type="sell", rate=rate, amount=amount)
                total = (amount * rate) * (1-btc_e_fee)
                print "BTC_USD"
                print "price", rate
                print "total USD with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_usd['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="ltc_usd", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "LTC_USD"
                print "price", rate
                print "total LTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # sell LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_btc['ticker']['buy']
                r = t.trade(pair="ltc_btc", trade_type="sell", rate=rate, amount=total)
                total = (total * rate) * (1-btc_e_fee)
                print ""
                print "LTC_BTC"
                print "price", rate
                print "total BTC with fee", total
                handler.setNextNonce(key, t.next_nonce())


        # ARB2
        if which == 'arb2':
            # ltc_btc
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_btc/ticker")
                ltc_btc = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_btc json")
                self.write_error(500)
                return

            # ltc_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
                ltc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_usd json")
                self.write_error(500)
                return

            # btc_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
                btc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_usd json")
                self.write_error(500)
                return

            # buy LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_btc['ticker']['sell']
                buy = (amount / rate)
                r = t.trade(pair="ltc_btc", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print "LTC_BTC"
                print "price", rate
                print "total LTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # sell LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_usd['ticker']['buy']
                r = t.trade(pair="ltc_usd", trade_type="sell", rate=rate, amount=total)
                total = (total * rate) * (1-btc_e_fee)
                print ""
                print "LTC_USD"
                print "price", rate
                print "total USD with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_usd['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="btc_usd", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "BTC_USD"
                print "price", rate
                print "total BTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

        # ARB3
        if which == 'arb3':
            # btc_eur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_eur/ticker")
                btc_eur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_eur btc-e json")
                self.write_error(500)
                return
            # eur_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/eur_usd/ticker")
                eur_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving eur_usd btc-e json")
                self.write_error(500)
                return
            # btc_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
                btc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_usd json")
                self.write_error(500)
                return

            # sell BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_eur['ticker']['buy']
                r = t.trade(pair="btc_eur", trade_type="sell", rate=rate, amount=amount)
                total = (amount * rate) * (1-btc_e_fee)
                print "BTC_EUR"
                print "price", rate
                print "total EUR with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # sell EUR
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = eur_usd['ticker']['buy']
                r = t.trade(pair="eur_usd", trade_type="sell", rate=rate, amount=total)
                total = (total * rate) * (1-btc_e_fee)
                print ""
                print "EUR_USD"
                print "price", rate
                print "total USD with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_usd['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="btc_usd", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "BTC_USD"
                print "price", rate
                print "total BTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

        # ARB4
        if which == 'arb4':
            # btc_rur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_rur/ticker")
                btc_rur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_rur btc-e json")
                self.write_error(500)
                return

            # usd_rur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/usd_rur/ticker")
                usd_rur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving usd_rur btc-e json")
                self.write_error(500)
                return

            # btc_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
                btc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_usd json")
                self.write_error(500)
                return

            # sell BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_rur['ticker']['buy']
                r = t.trade(pair="btc_rur", trade_type="sell", rate=rate, amount=amount)
                total = (amount * rate) * (1-btc_e_fee)
                print "BTC_RUR"
                print "price", rate
                print "total RUR with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy USD
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = usd_rur['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="usd_rur", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "USD_RUR"
                print "price", rate
                print "total USD with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_usd['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="btc_usd", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "BTC_USD"
                print "price", rate
                print "total BTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

        # ARB5
        if which == 'arb5':
            # btc_rur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_rur/ticker")
                btc_rur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_rur btc-e json")
                self.write_error(500)
                return

            # ltc_rur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_rur/ticker")
                ltc_rur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_rur btc-e json")
                self.write_error(500)
                return

            # ltc_btc
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_btc/ticker")
                ltc_btc = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_btc json")
                self.write_error(500)
                return

            # sell BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_rur['ticker']['buy']
                r = t.trade(pair="btc_rur", trade_type="sell", rate=rate, amount=amount)
                total = (amount * rate) * (1-btc_e_fee)
                print "BTC_RUR"
                print "price", rate
                print "total RUR with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_rur['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="ltc_rur", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "LTC_RUR"
                print "price", rate
                print "total LTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # sell LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_btc['ticker']['buy']
                r = t.trade(pair="ltc_btc", trade_type="sell", rate=rate, amount=total)
                total = (total * rate) * (1-btc_e_fee)
                print ""
                print "LTC_BTC"
                print "price", rate
                print "total BTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

        # ARB6
        if which == 'arb6':
            # ltc_rur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_rur/ticker")
                ltc_rur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_rur btc-e json")
                self.write_error(500)
                return

            # usd_rur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/usd_rur/ticker")
                usd_rur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving usd_rur btc-e json")
                self.write_error(500)
                return

            # ltc_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
                ltc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_usd json")
                self.write_error(500)
                return

            # sell LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_rur['ticker']['buy']
                r = t.trade(pair="ltc_rur", trade_type="sell", rate=rate, amount=ltcamount)
                total = (ltcamount * rate) * (1-btc_e_fee)
                print "LTC_RUR"
                print "price", rate
                print "total RUR with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy USD
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = usd_rur['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="usd_rur", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "USD_RUR"
                print "price", rate
                print "total USD with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_usd['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="ltc_usd", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "LTC_USD"
                print "price", rate
                print "total LTC with fee", total
                handler.setNextNonce(key, t.next_nonce())
            
        # ARB7
        if which == 'arb7':
            # ltc_usd
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
                ltc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_usd json")
                self.write_error(500)
                return

            # usd_rur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/usd_rur/ticker")
                usd_rur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving usd_rur btc-e json")
                self.write_error(500)
                return

            # ltc_rur
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_rur/ticker")
                ltc_rur = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_rur btc-e json")
                self.write_error(500)
                return

            # sell LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_usd['ticker']['buy']
                r = t.trade(pair="ltc_usd", trade_type="sell", rate=rate, amount=amount)
                total = (amount * rate) * (1-btc_e_fee)
                print ""
                print "LTC_USD"
                print "price", rate
                print "total USD with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # sell USD
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = usd_rur['ticker']['buy']
                r = t.trade(pair="usd_rur", trade_type="sell", rate=rate, amount=total)
                total = (total * rate) * (1-btc_e_fee)
                print ""
                print "USD_RUR"
                print "price", rate
                print "total RUR with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # buy LTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_rur['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="ltc_rur", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "LTC_RUR"
                print "price", rate
                print "total LTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

        handler.save('key_file')
        self.redirect("/")


class TradeHistoryHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        trades = []
        handler = btceapi.KeyHandler('key_file')
        for key, (secret, nonce) in handler.keys.items():
            t = btceapi.TradeAPI(key, secret, nonce)
            r = t.tradeHistory()
            for d in r:
                trades.append("%s - %s - %s"%(d.pair, d.type, d.amount))
            handler.setNextNonce(key, t.next_nonce())
        handler.save('key_file')

        self.render('tradehistory.html', trades=trades)


class TotalHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        http_client = tornado.httpclient.HTTPClient()
        # btc_usd
        try:
            response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
            btc_usd = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving btc_usd btc-e json")
            self.write_error(500)
            return

        #ltc_usd
        try:
            response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
            ltc_usd = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving ltc_usd btc-e json")
            self.write_error(500)
            return

        handler = btceapi.KeyHandler('key_file')
        for key, (secret, nonce) in handler.keys.items():
            t = btceapi.TradeAPI(key, secret, nonce)
            # Balance, etc
            r = t.getInfo()
            for d in dir(r):
                if d == 'balance_btc':
                    balance_btc = float(getattr(r, d))
                elif d == 'balance_ltc':
                    balance_ltc = float(getattr(r, d))
                elif d == 'balance_usd':
                    balance_usd = float(getattr(r, d))
            handler.setNextNonce(key, t.next_nonce())
        handler.save('key_file')

        total_btc = balance_btc * btc_usd['ticker']['sell']
        total_ltc = balance_ltc * ltc_usd['ticker']['sell']
        total = total_btc + total_ltc + balance_usd
        print total

        handler = btceapi.KeyHandler('key_file')
        for key, (secret, nonce) in handler.keys.items():
            t = btceapi.TradeAPI(key, secret, nonce)
            # Balance, etc
            try:
                orders = t.orderList()
            except:
                logging.error('No orders')
                orders = None
            handler.setNextNonce(key, t.next_nonce())
        handler.save('key_file')
        if orders:
            for order in orders:
                print order.pair, order.type, order.amount


class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        http_client = tornado.httpclient.HTTPClient()
        prices = ''

        # btc_usd
        try:
            response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
            btc_usd = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving btc_usd btc-e json")
            self.write_error(500)
            return

        prices += "<table cellpadding='4'><tr>"
        prices += "<td>btc_usd_buy:</td><td> %s USD</td><td> - btc_usd_sell:</td><td> %s USD </td>"%(btc_usd['ticker']['buy'], btc_usd['ticker']['sell'])
        prices += "</tr>"

        # btc_eur
        try:
            response = http_client.fetch("https://btc-e.com/api/2/btc_eur/ticker")
            btc_eur = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving btc_eur btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>btc_eur_buy:</td><td> %s EUR</td><td> - btc_eur_sell:</td><td> %s EUR </td>"%(btc_eur['ticker']['buy'], btc_eur['ticker']['sell'])
        prices += "</tr>"

        # btc_rur
        try:
            response = http_client.fetch("https://btc-e.com/api/2/btc_rur/ticker")
            btc_rur = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving btc_rur btc-e json")
            self.write_error(500)
            return

        prices += "<tr>"
        prices += "<td>btc_rur_buy:</td><td> %s RUR</td><td> - btc_rur_sell:</td><td> %s RUR </td>"%(btc_rur['ticker']['buy'], btc_rur['ticker']['sell'])
        prices += "</tr>"

        # ltc_btc
        try:
            response = http_client.fetch("https://btc-e.com/api/2/ltc_btc/ticker")
            ltc_btc = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving ltc_btc btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>ltc_btc_buy:</td><td> %s BTC</td><td> - ltc_btc_sell:</td><td> %s BTC </td>"%(ltc_btc['ticker']['buy'], ltc_btc['ticker']['sell'])
        prices += "</tr>"

        #ltc_usd
        try:
            response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
            ltc_usd = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving ltc_usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>ltc_usd_buy:</td><td> %s USD</td><td> - ltc_usd_sell:</td><td> %s USD </td>"%(ltc_usd['ticker']['buy'], ltc_usd['ticker']['sell'])
        prices += "</tr>"

        # ltc_rur
        try:
            response = http_client.fetch("https://btc-e.com/api/2/ltc_rur/ticker")
            ltc_rur = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving ltc_rur btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>ltc_rur_buy:</td><td> %s RUR</td><td> - ltc_rur_sell:</td><td> %s RUR </td>"%(ltc_rur['ticker']['buy'], ltc_rur['ticker']['sell'])
        prices += "</tr>"

        # eur_usd
        try:
            response = http_client.fetch("https://btc-e.com/api/2/eur_usd/ticker")
            eur_usd = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving eur_usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>eur_usd_buy:</td><td> %s USD</td><td> - eur_usd_sell:</td><td> %s USD </td>"%(eur_usd['ticker']['buy'], eur_usd['ticker']['sell'])
        prices += "</tr>"

        # usd_rur
        try:
            response = http_client.fetch("https://btc-e.com/api/2/usd_rur/ticker")
            usd_rur = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd_rur btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>usd_rur_buy:</td><td> %s RUR</td><td> - usd_rur_sell:</td><td> %s RUR </td>"%(usd_rur['ticker']['buy'], usd_rur['ticker']['sell'])
        prices += "</tr>"

        # ftc_btc
        try:
            response = http_client.fetch("https://btc-e.com/api/2/ftc_btc/ticker")
            ftc_btc = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving ftc_btc btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>ftc_btc_buy:</td><td> %s BTC</td><td> - ftc_btc_sell:</td><td> %s BTC </td>"%(ftc_btc['ticker']['buy'], ftc_btc['ticker']['sell'])
        prices += "</tr></table>"


        # [ARB1] BTC 2 USD 2 LTC 2 BTC
        btc2usd= (amount * btc_usd['ticker']['buy'])* (1-btc_e_fee) # sell BTC for USD
        usd2ltc= (btc2usd / ltc_usd['ticker']['sell'])* (1-btc_e_fee) # buy LTC for USD
        ltc2btc= (usd2ltc * ltc_btc['ticker']['buy'])* (1-btc_e_fee) # sell LTC for BTC

        if ltc2btc > executetrade:
            print "Executing ARB1 trade"

        arb = '<table cellpadding="4">'
        arb += "<tr><td colspan='2'>[ARB 1] BTC 2 USD 2 LTC 2 BTC <a href='/trade?which=arb1' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell BTC for USD</td><td>Buy LTC for USD</td><td>Sell LTC for BTC</td></tr>"
        arb += "<tr><td>%s BTC = $%.8f</td><td> USD = %.8f</td><td> LTC = %.8f BTC</td></tr>"%(amount, btc2usd, usd2ltc, ltc2btc)
        arb += '</table>'


        # [ARB2] BTC 2 LTC 2 USD 2 BTC
        btc2ltc= (amount / ltc_btc['ticker']['sell'])* (1-btc_e_fee) # buy LTC for BTC
        ltc2usd= (btc2ltc * ltc_usd['ticker']['buy'])* (1-btc_e_fee) # sell LTC for USD
        usd2btc= (ltc2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # buy BTC for USD

        if usd2btc > executetrade:
            print "Executing ARB2 trade"

        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += "<tr><td colspan='2'>[ARB 2] BTC 2 LTC 2 USD 2 BTC <a href='/trade?which=arb2' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell BTC for LTC</td><td>Sell LTC for USD</td><td>Sell USD for BTC</td></tr>"
        arb += "<tr><td>%s BTC = %.8f</td><td> LTC = $%.8f</td><td> USD = %.8f BTC</td></tr>"%(amount, btc2ltc, ltc2usd, usd2btc)
        arb += '</table>'


        
        # [ARB3] BTC 2 EUR 2 USD 2 BTC
        btc2eur= (amount * btc_eur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for EUR
        eur2usd= (btc2eur * eur_usd['ticker']['buy'])* (1-btc_e_fee) # buy USD with EUR
        usd2btc= (eur2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # buy BTC with USD

        if usd2btc > executetrade:
            print "Executing ARB3 trade"

        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += "<tr><td colspan='2'>[ARB 3] BTC 2 EUR 2 USD 2 BTC  <a href='/trade?which=arb3' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell BTC for EUR</td><td>Buy USD with EUR</td><td>Buy BTC with USD</td></tr>"
        arb += "<tr><td>%s BTC = %.8f</td><td> EUR = $%.8f</td><td> USD = %.8f BTC</td></tr>"%(amount, btc2eur, eur2usd, usd2btc)
        arb += '</table>'



        # [ATB4] BTC 2 RUR 2 USD 2 BTC
        btc2rur= (amount * btc_rur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for RUR 
        rur2usd= (btc2rur / usd_rur['ticker']['sell'])* (1-btc_e_fee2) # sell RUR for USD 
        usd2btc= (rur2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # sell USD for BTC

        if usd2btc > executetrade:
            print "Executing ARB4 trade"

        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += "<tr><td colspan='2'>[ARB 4] BTC 2 RUR 2 USD 2 BTC <a href='/trade?which=arb4' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell BTC for RUR</td><td>Sell RUR for USD</td><td>sell USD for BTC</td></tr>"
        arb += "<tr><td>%s BTC = %.8f</td><td> RUR = %.8f</td><td> USD = %.8f BTC</td></tr>"%(amount, btc2rur, rur2usd, usd2btc)        
        arb += '</table>'



        # [ARB5] BTC 2 RUR 2 LTC 2 BTC
        btc2rur= (amount * btc_rur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for RUR
        rur2ltc= (btc2rur / ltc_rur['ticker']['sell'])* (1-btc_e_fee) # sell RUR for LTC
        ltc2btc= (rur2ltc * ltc_btc['ticker']['buy'])* (1-btc_e_fee) # sell LTC for BTC

        if ltc2btc > executetrade:
            print "Executing ARB5 trade"

        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += "<tr><td colspan='2'>[ARB 5] BTC 2 RUR 2 LTC 2 BTC <a href='/trade?which=arb5' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell BTC for RUR</td><td>Sell RUR for LTC</td><td>Sell LTC for BTC</td></tr>"
        arb += "<tr><td>%s BTC = %.8f</td><td>RUR = %.8f</td><td> LTC = %.8f BTC</td></tr>"%(amount, btc2rur, rur2ltc, ltc2btc)        
        arb += '</table>'


        # [ARB6] LTC 2 RUR 2 USD 2 LTC
        ltc2rur= (ltcamount * ltc_rur['ticker']['buy'])* (1-btc_e_fee) # sell LTC for RUR
        rur2usd= (ltc2rur / usd_rur['ticker']['sell'])* (1-btc_e_fee2) # sell RUR for USD
        usd2ltc= (rur2usd / ltc_usd['ticker']['sell'])* (1-btc_e_fee) # sell USD for LTC

        if usd2ltc > executetrade:
            print "Executing ARB6 trade"

        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += "<tr><td colspan='2'>[ARB 6] LTC 2 RUR 2 USD 2 LTC <a href='/trade?which=arb6' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell LTC for RUR</td><td>Sell RUR for USD</td><td>Sell USD for LTC</td></tr>"
        arb += "<tr><td>%s LTC = %.8f</td><td> RUR = $%.8f</td><td> USD = %.8f LTC</td></tr>"%(ltcamount, ltc2rur, rur2usd, usd2ltc)        
        arb += '</table>'


        # [ARB7] LTC 2 USD 2 RUR 2 LTC
        ltc2usd= (ltcamount * ltc_usd['ticker']['buy'])* (1-btc_e_fee) # sell LTC for USD
        usd2rur= (ltc2usd * usd_rur['ticker']['buy'])* (1-btc_e_fee2) # sell USD for RUR
        rur2ltc= (usd2rur / ltc_rur['ticker']['sell'])* (1-btc_e_fee) # sell RUR for LTC

        if rur2ltc > executetrade:
            print "Executing ARB7 trade"

        arb += '<table cellpadding="4" style="margin: 40px 0;">'
        arb += "<tr><td colspan='2'>[ARB 7] LTC 2 USD 2 RUR 2 LTC <a href='/trade?which=arb7' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell LTC for USD</td><td>Sell USD for RUR</td><td>Sell RUR for LTC</td></tr>"
        arb += "<tr><td>%s LTC = $%.8f</td><td>USD = %.8f</td><td>RUR = %.8f LTC</td></tr>"%(ltcamount, ltc2usd, usd2rur, rur2ltc)
        arb += '</table>'

        self.render('index.html', prices=prices, arb=arb)


def main():

    http_server = tornado.httpserver.HTTPServer(Application(), xheaders=True)
    http_server.listen(80)
    tornado.ioloop.IOLoop.instance().start()
    logging.info("arb web server started successfully")

if __name__ == "__main__":
    tornado.options.parse_command_line()
    logging.info("Starting arb web server")

    main()
