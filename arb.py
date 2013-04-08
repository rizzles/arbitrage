#!/usr/bin/python

import os
import logging
import datetime
import urlparse
import uuid
import urllib2
import locale
import time

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

        if uname != 'rizzles' or password != 'mondale':
            self.redirect('/login')
            return
        
        user = {'uname':'rizzles', 'uid':'1'}
        self.set_secure_cookie("arb", tornado.escape.json_encode(user))

        self.redirect('/')


class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie('arb')
        self.clear_all_cookies()
        self.redirect('/login')


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
            


        # ARB 1
        if which == 'arb1':
            # BTC to USD price
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
                btc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_usd json")
                self.write_error(500)
                return

            # USD to LTC price
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
                ltc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving usd_ltc json")
                self.write_error(500)
                return

            # LTC to BTC price
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_btc/ticker")
                ltc_btc = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_btc json")
                self.write_error(500)
                return

            # Sell BTC for USD logic
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_usd['ticker']['buy']
                r = t.trade(pair="btc_usd", trade_type="sell", rate=rate, amount=amount )
                total = (amount * rate) * (1-btc_e_fee)
                print "BTC_USD"
                print "price", rate
                print "sell amount", amount
                print "total USD with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # Buy LTC for USD
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_usd['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="ltc_usd", trade_type="buy", rate=rate, amount=buy)
                total = buy * (1-btc_e_fee)
                print ""
                print "LTC_USD"
                print "price", rate
                print "buy amount", buy
                print "total LTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # Sell LTC for BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                sell = total
                rate = ltc_btc['ticker']['buy']
                r = t.trade(pair="ltc_btc", trade_type="sell", rate=rate, amount=sell)
                total = (total * rate) * (1-btc_e_fee)
                print ""
                print "LTC_BTC"
                print "price", rate
                print "sell amount", sell
                print "total BTC with fee", total
                handler.setNextNonce(key, t.next_nonce())



        # ARB 2
        if which == 'arb2':
            # BTC to LTC price
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_btc/ticker")
                ltc_btc = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving ltc_btc json")
                self.write_error(500)
                return

            # LTC to USD price
            try:
                response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
                ltc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving usd_ltc json")
                self.write_error(500)
                return

            # USD to LTC price
            try:
                response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
                btc_usd = tornado.escape.json_decode(response.body)
            except:
                logging.error("Error retreiving btc_usd json")
                self.write_error(500)
                return

            # Buy LTC for BTC
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_btc['ticker']['sell']
                buy = (amount / rate)
                r = t.trade(pair="ltc_btc", trade_type="buy", rate=rate, amount=buy)
                total = (amount / rate) * (1-btc_e_fee)
                print "LTC_BTC"
                print "price", rate
                print "buy amount", amount
                print "total LTC with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # Sell LTC for USD
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = ltc_usd['ticker']['buy']
                r = t.trade(pair="ltc_usd", trade_type="sell", rate=rate, amount=total)
                sell = (total * rate)
                total = (total * rate) * (1-btc_e_fee)
                print ""
                print "LTC_USD"
                print "price", rate
                print "sell amount", sell
                print "total USD with fee", total
                handler.setNextNonce(key, t.next_nonce())

            # Buy BTC for USD logic
            for key, (secret, nonce) in handler.keys.items():
                t = btceapi.TradeAPI(key, secret, nonce)
                rate = btc_usd['ticker']['sell']
                buy = (total / rate)
                r = t.trade(pair="btc_usd", trade_type="buy", rate=rate, amount=buy)
                total = (total / rate) * (1-btc_e_fee)
                print ""
                print "BTC_USD"
                print "price", rate
                print "buy amount", amount
                print "total BTC with fee", total
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


class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        http_client = tornado.httpclient.HTTPClient()
        prices = ''
        try:
            response = http_client.fetch("https://btc-e.com/api/2/btc_usd/ticker")
            btc_usd = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd btc-e json")
            self.write_error(500)
            return

        prices += "<table cellpadding='4'><tr>"
        prices += "<td>btc_usd_buy:</td><td> %s USD</td><td> - btc_usd_sell:</td><td> %s USD </td>"%(btc_usd['ticker']['buy'], btc_usd['ticker']['sell'])
        prices += "</tr>"

        try:
            response = http_client.fetch("https://btc-e.com/api/2/btc_eur/ticker")
            btc_eur = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>btc_eur_buy:</td><td> %s EUR</td><td> - btc_eur_sell:</td><td> %s EUR </td>"%(btc_eur['ticker']['buy'], btc_eur['ticker']['sell'])
        prices += "</tr>"

        try:
            response = http_client.fetch("https://btc-e.com/api/2/btc_rur/ticker")
            btc_rur = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>btc_rur_buy:</td><td> %s RUR</td><td> - btc_rur_sell:</td><td> %s RUR </td>"%(btc_rur['ticker']['buy'], btc_rur['ticker']['sell'])
        prices += "</tr>"

        try:
            response = http_client.fetch("https://btc-e.com/api/2/ltc_btc/ticker")
            ltc_btc = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>ltc_btc_buy:</td><td> %s BTC</td><td> - ltc_btc_sell:</td><td> %s BTC </td>"%(ltc_btc['ticker']['buy'], ltc_btc['ticker']['sell'])
        prices += "</tr>"

        try:
            response = http_client.fetch("https://btc-e.com/api/2/ltc_usd/ticker")
            ltc_usd = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>ltc_usd_buy:</td><td> %s USD</td><td> - ltc_usd_sell:</td><td> %s USD </td>"%(ltc_usd['ticker']['buy'], ltc_usd['ticker']['sell'])
        prices += "</tr>"

        try:
            response = http_client.fetch("https://btc-e.com/api/2/ltc_rur/ticker")
            ltc_rur = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>ltc_rur_buy:</td><td> %s RUR</td><td> - ltc_rur_sell:</td><td> %s RUR </td>"%(ltc_rur['ticker']['buy'], ltc_rur['ticker']['sell'])
        prices += "</tr>"

        try:
            response = http_client.fetch("https://btc-e.com/api/2/eur_usd/ticker")
            eur_usd = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>eur_usd_buy:</td><td> %s USD</td><td> - eur_usd_sell:</td><td> %s USD </td>"%(eur_usd['ticker']['buy'], eur_usd['ticker']['sell'])
        prices += "</tr>"

        try:
            response = http_client.fetch("https://btc-e.com/api/2/usd_rur/ticker")
            usd_rur = tornado.escape.json_decode(response.body)
        except:
            logging.error("Error retreiving usd btc-e json")
            self.write_error(500)
            return
        prices += "<tr>"
        prices += "<td>usd_rur_buy:</td><td> %s RUR</td><td> - usd_rur_sell:</td><td> %s RUR </td>"%(usd_rur['ticker']['buy'], usd_rur['ticker']['sell'])
        prices += "</tr></table>"


        # [ARB1] BTC 2 USD 2 LTC 2 BTC

        btc2usd= (amount * btc_usd['ticker']['buy'])* (1-btc_e_fee) # sell BTC for USD
        usd2ltc= (btc2usd / ltc_usd['ticker']['sell'])* (1-btc_e_fee) # sell USD for LTC
        ltc2btc= (usd2ltc * ltc_btc['ticker']['buy'])* (1-btc_e_fee) # sell LTC for BTC
        arb = '<table cellpadding="4">'
        arb += "<tr><td colspan='2'>[ARB 1] BTC 2 USD 2 LTC 2 BTC <a href='/trade?which=arb1' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell BTC for USD</td><td>Buy LTC for USD</td><td>Sell LTC for BTC</td></tr>"
        arb += "<tr><td>%s BTC = $%.8f</td><td> USD = %.8f</td><td> LTC = %.8f BTC</td></tr>"%(amount, btc2usd, usd2ltc, ltc2btc)
        arb += '</table>'


        # [ARB2] BTC 2 LTC 2 USD 2 BTC

        btc2ltc= (amount / ltc_btc['ticker']['sell'])* (1-btc_e_fee) # sell BTC for LTC 
        ltc2usd= (btc2ltc * ltc_usd['ticker']['buy'])* (1-btc_e_fee) # sell LTC for USD
        usd2btc= (ltc2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # sell USD for BTC
        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += "<tr><td colspan='2'>[ARB 2] BTC 2 LTC 2 USD 2 BTC <a href='/trade?which=arb2' class='btn btn-small btn-primary'>Execute</a></td></tr>"
        arb += "<tr><td>Sell BTC for LTC</td><td>Sell LTC for USD</td><td>Sell USD for BTC</td></tr>"
        arb += "<tr><td>%s BTC = %.8f</td><td> LTC = $%.8f</td><td> USD = %.8f BTC</td></tr>"%(amount, btc2ltc, ltc2usd, usd2btc)
        arb += '</table>'


        
        # [ARB3] BTC 2 EUR 2 USD 2 BTC

        btc2eur= (amount * btc_eur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for EUR
        eur2usd= (btc2eur * eur_usd['ticker']['buy'])* (1-btc_e_fee) # buy USD with EUR
        usd2btc= (eur2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # buy BTC with USD
        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += '<tr><td colspan="2">[ARB 3] BTC 2 EUR 2 USD 2 BTC </td></tr>'
        arb += "<tr><td>Sell BTC for EUR</td><td>Buy USD with EUR</td><td>Buy BTC with USD</td></tr>"
        arb += "<tr><td>%s BTC = %.8f</td><td> EUR = $%.8f</td><td> USD = %.8f BTC</td></tr>"%(amount, btc2eur, eur2usd, usd2btc)
        arb += '</table>'



        # BTC 2 RUR 2 USD 2 BTC

        btc2rur= (amount * btc_rur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for RUR 
        rur2usd= (btc2rur / usd_rur['ticker']['sell'])* (1-btc_e_fee2) # sell RUR for USD 
        usd2btc= (rur2usd / btc_usd['ticker']['sell'])* (1-btc_e_fee) # sell USD for BTC
        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += '<tr><td colspan="2">[ARB 4] BTC 2 RUR 2 USD 2 BTC</td></tr>'
        arb += "<tr><td>Sell BTC for RUR</td><td>Sell RUR for USD</td><td>sell USD for BTC</td></tr>"

        arb += "<tr><td>%s BTC = %.8f</td><td> RUR = %.8f</td><td> USD = %.8f BTC</td></tr>"%(amount, btc2rur, rur2usd, usd2btc)        
        arb += '</table>'


        # BTC 2 RUR 2 LTC 2 BTC
        
        btc2rur= (amount * btc_rur['ticker']['sell'])* (1-btc_e_fee) # sell BTC for RUR
        rur2ltc= (btc2rur / ltc_rur['ticker']['sell'])* (1-btc_e_fee) # sell RUR for LTC
        ltc2btc= (rur2ltc * ltc_btc['ticker']['buy'])* (1-btc_e_fee) # sell LTC for BTC
        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += '<tr><td colspan="2">[ARB 5] BTC 2 RUR 2 LTC 2 BTC</td></tr>'
        arb += "<tr><td>Sell BTC for RUR</td><td>Sell RUR for LTC</td><td>Sell LTC for BTC</td></tr>"

        arb += "<tr><td>%s BTC = %.8f</td><td>RUR = %.8f</td><td> LTC = %.8f BTC</td></tr>"%(amount, btc2rur, rur2ltc, ltc2btc)        
        arb += '</table>'


        # LTC 2 RUR 2 USD 2 LTC

        ltc2rur= (amount * ltc_rur['ticker']['buy'])* (1-btc_e_fee) # sell LTC for RUR
        rur2usd= (ltc2rur / usd_rur['ticker']['sell'])* (1-btc_e_fee2) # sell RUR for USD
        usd2ltc= (rur2usd / ltc_usd['ticker']['sell'])* (1-btc_e_fee) # sell USD for LTC
        arb += '<table cellpadding="4" style="margin-top: 40px;">'
        arb += '<tr><td colspan="2">[ARB 6] LTC 2 RUR 2 USD 2 LTC</td></tr>'
        arb += "<tr><td>Sell LTC for RUR</td><td>Sell RUR for USD</td><td>Sell USD for LTC</td></tr>"

        arb += "<tr><td>%s LTC = %.8f</td><td> RUR = $%.8f</td><td> USD = %.8f LTC</td></tr>"%(amount, ltc2rur, rur2usd, usd2ltc)        
        arb += '</table>'


        # LTC 2 USD 2 RUR 2 LTC

        ltc2usd= (amount * ltc_usd['ticker']['buy'])* (1-btc_e_fee) # sell LTC for USD
        usd2rur= (ltc2usd * usd_rur['ticker']['buy'])* (1-btc_e_fee2) # sell USD for RUR
        rur2ltc= (usd2rur / ltc_rur['ticker']['sell'])* (1-btc_e_fee) # sell RUR for LTC
        arb += '<table cellpadding="4" style="margin: 40px 0;">'
        arb += '<tr><td colspan="2">[ARB 7] LTC 2 USD 2 RUR 2 LTC</td></tr>'
        arb += "<tr><td>Sell LTC for USD</td><td>Sell USD for RUR</td><td>Sell RUR for LTC</td></tr>"

        arb += "<tr><td>%s LTC = $%.8f</td><td>USD = %.8f</td><td>RUR = %.8f LTC</td></tr>"%(amount, ltc2usd, usd2rur, rur2ltc)
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
