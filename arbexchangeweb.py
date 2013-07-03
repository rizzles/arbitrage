#!/usr/bin/python

import logging
import os
import time
import pymongo

import tornado.ioloop
import tornado.web
import tornado.options
import tornado.httpserver
import tornado.httpclient
import tornado.escape
import tornado.websocket
import tornado.gen

from variables import *

TIMEOUT = 20

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/test", TestHandler),
            (r"/socket_coinbase", SocketCoinbaseHandler),
            (r"/socket_campbx", SocketCampbxHandler),
            (r"/socket_mongo", SocketMongoHandler),
            (r"/coinbase", CoinbaseHandler),
            (r"/campbx", CampbxHandler),
            (r"/graph_data", GraphHandler),
        ]
        settings = dict(
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            site_name='school',
            xsrf_cookies=False,
            autoescape=None,
            debug=True,
            gzip=True
        )

        tornado.web.Application.__init__(self, handlers, **settings)
        self.mongodb = mongodb


class BaseHandler(tornado.web.RequestHandler):
    @property
    def mongodb(self):
        return self.application.mongodb

    def get_current_user(self):
        """
        user_json = self.get_secure_cookie("arbexchange")
        if not user_json:
            return None
        return tornado.escape.json_decode(user_json)
        """
        return None


class MainHandler(BaseHandler):
    def get(self):
        self.render("arbexchange.html")


class TestHandler(BaseHandler):
    def get(self):
        self.render("test.html")


class CampbxHandler(BaseHandler):
    @tornado.gen.coroutine
    @tornado.web.asynchronous
    def get(self):
        url = 'http://CampBX.com/api/xticker.php'

        self.http_client = tornado.httpclient.AsyncHTTPClient()
        response = None         
        try:
            response = yield self.http_client.fetch(url)
            json_data = tornado.escape.json_decode(response.body)
        except tornado.httpclient.HTTPError as e:
            logging.error("CampBX error. HTTP timeout", e)
        finally:
            self.http_client.close()

        self.render("campbx.html", price=json_data['Last Trade'])


class CoinbaseHandler(BaseHandler):
    @tornado.gen.coroutine    
    @tornado.web.asynchronous 
    def get(self):
        #url = 'https://coinbase.com/api/v1/account/balance?api_key=dbe08b82a2450217443a5aa6a4cb0e1b493bac5bd81b2f7d5ad566b33da73b5d'
        url = 'https://coinbase.com/api/v1/prices/sell'

        self.http_client = tornado.httpclient.AsyncHTTPClient()
        try:
            response = yield self.http_client.fetch(url)
            json_data = tornado.escape.json_decode(response.body)
        except tornado.httpclient.HTTPError as e:
            logging.error("Error encountered when getting coinbase price:", e)
        finally:
            self.http_client.close()

        self.render("coinbase.html", price=json_data)


class SocketCoinbaseHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        logging.info("Coinbase WebSocket opened")

    @tornado.gen.coroutine
    @tornado.web.asynchronous
    def on_message(self, message):
        #url = 'https://coinbase.com/api/v1/account/balance?api_key=dbe08b82a2450217443a5aa6a4cb0e1b493bac5bd81b2f7d5ad566b33da73b5d'
        url = 'https://coinbase.com/api/v1/prices/sell'

        while True:
            self.http_client = tornado.httpclient.AsyncHTTPClient()
            try:
                response = yield self.http_client.fetch(url)
                #json_data = tornado.escape.json_decode(response.body)
            except tornado.httpclient.HTTPError as e:
                logging.error("Error encountered when getting coinbase price:", e)
            finally:
                self.http_client.close()
                if response:
                    self.write_message(response.body)
                yield tornado.gen.Task(tornado.ioloop.IOLoop.instance().add_timeout, time.time() + TIMEOUT)

    def on_close(self):
        self.http_client.close()
        logging.info("Coinbase WebSocket closed")


class SocketCampbxHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        logging.info("Campbx WebSocket opened")

    @tornado.gen.coroutine
    @tornado.web.asynchronous
    def on_message(self, message):
        url = 'http://CampBX.com/api/xticker.php'

        while True:
            self.http_client = tornado.httpclient.AsyncHTTPClient()
            response = None         
            try:
                response = yield self.http_client.fetch(url)
                #json_data = tornado.escape.json_decode(response.body)
            except tornado.httpclient.HTTPError as e:
                logging.error("CampBX error. HTTP timeout", e)
            finally:
                self.http_client.close()
                if response:
                    self.write_message(response.body)
                yield tornado.gen.Task(tornado.ioloop.IOLoop.instance().add_timeout, time.time() + TIMEOUT)

    def on_close(self):
        self.http_client.close()
        logging.info("CampBX WebSocket closed")


class SocketMongoHandler(tornado.websocket.WebSocketHandler, BaseHandler):
    def open(self):
        logging.info("Socket Connection for Mongo DB opened")

    @tornado.gen.coroutine
    @tornado.web.asynchronous
    def on_message(self, message):
        coll = self.mongodb.price
        while True:
            price = coll.find().sort('_id',-1).limit(1)
            for p in price:
                del(p['_id'])
                del(p['time'])
                self.write_message(tornado.escape.json_encode(p))

            yield tornado.gen.Task(tornado.ioloop.IOLoop.instance().add_timeout, time.time() + TIMEOUT)

    def on_close(self):
        logging.info("Mongo WebSocket closed")


class GraphHandler(BaseHandler):
    def get(self):
        amount = self.get_argument('amount', None)
        unittime = self.get_argument('unittime', None)
        amount = int(amount)

        labels = []
        diffdata = []
        coinbasedata = []
        campbxdata = []

        if unittime == 'hourly':
            coll = self.mongodb.hourly
        elif unittime == 'daily':
            coll = self.mongodb.daily
        else:
            coll = self.mongodb.weekly

        prices = coll.find().sort('_id',1)
        for price in prices:
            labels.append(price['stamp'])
            diffdata.append(price['diff'])
            coinbasedata.append(price['coinbase'])
            campbxdata.append(price['campbx'])

        if amount == 0:
            labels = labels[-24:]
            diffdata = diffdata[-24:]
            coinbasedata = coinbasedata[-24:]
            campbxdata = campbxdata[-24:]
        else:
            if amount*24*2 < -len(labels):
                labels = labels[-len(labels):-len(labels)+24]
                diffdata = diffdata[-len(diffdata):-len(diffdata)+24]
                coinbasedata = coinbasedata[-len(coinbasedata):-len(coinbasedata)+24]                
                campbxdata = campbxdata[-len(campbxdata):-len(campbxdata)+24]                                
                amount += 1                
            else:
                labels = labels[amount*24*2:amount*24]
                diffdata = diffdata[amount*24*2:amount*24]
                coinbasedata = coinbasedata[amount*24*2:amount*24]
                campbxdata = campbxdata[amount*24*2:amount*24]                

        diff =  {
        "labels" : labels,
        "datasets": [{
            "fillColor" : "rgba(151,187,205,0.5)",
            "strokeColor" : "rgba(151,187,205,1)",
            "pointColor" : "rgba(151,187,205,1)",
            "pointStrokeColor" : "#fff",
            "data" : diffdata  
        }]
        }

        prices =  {
        "labels" : labels,
        "datasets": [{
            "fillColor" : "rgba(151,187,205,0.5)",
            "strokeColor" : "rgba(151,187,205,1)",
            "pointColor" : "rgba(151,187,205,1)",
            "pointStrokeColor" : "#fff",
            "data" : coinbasedata  
        },
        {
            "fillColor" : "rgba(220,220,220,0.5)",
            "strokeColor" : "rgba(220,220,220,1)",
            "pointColor" : "rgba(220,220,220,1)",
            "pointStrokeColor" : "#fff",
            "data" : campbxdata
        }]
        }

        data = {'diff':diff, 'prices':prices, 'amount':amount}
        self.write(tornado.escape.json_encode(data))


def main():
    http_server = tornado.httpserver.HTTPServer(Application(), xheaders=True)
    http_server.listen(80)
    tornado.ioloop.IOLoop.instance().start()
    logging.info("Web server started successfully")

if __name__ == "__main__":
    tornado.options.parse_command_line()
    logging.info("Starting web server")

    main()
