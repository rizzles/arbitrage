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
            (r"/coinbase", CoinbaseHandler),
            (r"/test", TestHandler),
            (r"/socket_coinbase", SocketCoinbaseHandler),
            (r"/socket_campbx", SocketCampbxHandler),
            (r"/socket_mongo", SocketMongoHandler),
            (r"/mongo", MongoHandler),
            (r"/coinbase2", Coinbase2Handler),
            (r"/campbx", CampbxHandler),
            (r"/graph_data", MtgoxGraphHandler),
            (r"/coinbase_graph_data", CoinbaseGraphHandler),
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


class CoinbaseHandler(BaseHandler):
    def get(self):
        self.render("coinbase.html")


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


class Coinbase2Handler(BaseHandler):
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


class MongoHandler(BaseHandler):
    def get(self):
        coll = self.mongodb.price
        price = coll.find().sort('_id',-1).limit(1)
        for p in price:
            del(p['_id'])
            del(p['time'])
            self.write(tornado.escape.json_encode(p))
            return


class MtgoxGraphHandler(BaseHandler):
    def get(self):
        amount = self.get_argument('amount', None)
        unittime = self.get_argument('unittime', None)
        plots = self.get_argument('plots', None)
        plots = int(plots)
        amount = int(amount)
        end = False

        labels = []
        diffdata = []
        diff2data = []
        coinbasedata = []
        campbxdata = []
        mtgoxdata = []

        if unittime == 'minute':
            coll = self.mongodb.minute
        elif unittime == 'hourly':
            coll = self.mongodb.mtgoxhourly
        elif unittime == 'daily':
            coll = self.mongodb.mtgoxdaily
        else:
            coll = self.mongodb.weekly

        prices = coll.find().sort('_id',1)
        for price in prices:
            labels.append(price['stamp'])
            diffdata.append(price['diff'])
            diff2data.append(price['diff2'])
            coinbasedata.append(price['coinbase'])
            campbxdata.append(price['campbx'])
            if price['mtgox'] == 0:
                mtgoxdata.append(price['coinbase'])
            else:
                mtgoxdata.append(price['mtgox'])


        # first chart
        if amount == 0:
            labels = labels[-plots:]
            diffdata = diffdata[-plots:]
            diff2data = diff2data[-plots:]
            coinbasedata = coinbasedata[-plots:]
            campbxdata = campbxdata[-plots:]
            mtgoxdata = mtgoxdata[-plots:]
        else:
            # longer than the length of array
            if amount*plots-plots < -len(labels):
                labels = labels[-len(labels):-len(labels)+plots]
                diffdata = diffdata[-len(diffdata):-len(diffdata)+plots]
                diff2data = diff2data[-len(diff2data):-len(diff2data)+plots]
                coinbasedata = coinbasedata[-len(coinbasedata):-len(coinbasedata)+plots]
                campbxdata = campbxdata[-len(campbxdata):-len(campbxdata)+plots]
                mtgoxdata = mtgoxdata[-len(mtgoxdata):-len(mtgoxdata)+plots]
                end = True
            else:
                labels = labels[amount*plots-plots:amount*plots]
                diffdata = diffdata[amount*plots-plots:amount*plots]
                diff2data = diff2data[amount*plots-plots:amount*plots]
                coinbasedata = coinbasedata[amount*plots-plots:amount*plots]
                campbxdata = campbxdata[amount*plots-plots:amount*plots]
                mtgoxdata = mtgoxdata[amount*plots-plots:amount*plots]
    
        diff =  {
        "labels" : labels,
        "datasets": [{
            "fillColor" : "rgba(151,187,205,0.5)",
            "strokeColor" : "rgba(151,187,205,1)",
            "pointColor" : "rgba(151,187,205,1)",
            "pointStrokeColor" : "#fff",
            "data" : diff2data  
        }]
        }

        prices =  {
        "labels" : labels,
        "datasets": [{
            "fillColor" : "rgba(151,187,205,0.5)",
            "strokeColor" : "rgba(151,187,205,1)",
            "pointColor" : "rgba(151,187,205,1)",
            "pointStrokeColor" : "#fff",
            "data" : mtgoxdata  
        },
        {

            "fillColor" : "rgba(220,220,220,0.5)",
            "strokeColor" : "rgba(220,220,220,1)",
            "pointColor" : "rgba(220,220,220,1)",
            "pointStrokeColor" : "#fff",
            "data" : campbxdata
        }]
        }

        data = {'diff':diff, 'prices':prices, 'amount':amount, 'end':end}
        self.write(tornado.escape.json_encode(data))


class CoinbaseGraphHandler(BaseHandler):
    def get(self):
        amount = self.get_argument('amount', None)
        unittime = self.get_argument('unittime', None)
        plots = self.get_argument('plots', None)
        plots = int(plots)
        amount = int(amount)
        end = False

        labels = []
        diffdata = []
        diff2data = []
        coinbasedata = []
        campbxdata = []
        mtgoxdata = []

        if unittime == 'minute':
            coll = self.mongodb.minute
        elif unittime == 'hourly':
            coll = self.mongodb.coinbasehourly
        elif unittime == 'daily':
            coll = self.mongodb.coinbasedaily
        else:
            coll = self.mongodb.weekly

        prices = coll.find().sort('_id',1)
        for price in prices:
            labels.append(price['stamp'])
            diffdata.append(price['diff'])
            diff2data.append(price['diff2'])
            coinbasedata.append(price['coinbase'])
            campbxdata.append(price['campbx'])
            if price['mtgox'] == 0:
                mtgoxdata.append(price['coinbase'])
            else:
                mtgoxdata.append(price['mtgox'])


        # first chart
        if amount == 0:
            labels = labels[-plots:]
            diffdata = diffdata[-plots:]
            diff2data = diff2data[-plots:]
            coinbasedata = coinbasedata[-plots:]
            campbxdata = campbxdata[-plots:]
            mtgoxdata = mtgoxdata[-plots:]
        else:
            # longer than the length of array
            if amount*plots-plots < -len(labels):
                labels = labels[-len(labels):-len(labels)+plots]
                diffdata = diffdata[-len(diffdata):-len(diffdata)+plots]
                diff2data = diff2data[-len(diff2data):-len(diff2data)+plots]
                coinbasedata = coinbasedata[-len(coinbasedata):-len(coinbasedata)+plots]
                campbxdata = campbxdata[-len(campbxdata):-len(campbxdata)+plots]
                mtgoxdata = mtgoxdata[-len(mtgoxdata):-len(mtgoxdata)+plots]
                end = True
            else:
                labels = labels[amount*plots-plots:amount*plots]
                diffdata = diffdata[amount*plots-plots:amount*plots]
                diff2data = diff2data[amount*plots-plots:amount*plots]
                coinbasedata = coinbasedata[amount*plots-plots:amount*plots]
                campbxdata = campbxdata[amount*plots-plots:amount*plots]
                mtgoxdata = mtgoxdata[amount*plots-plots:amount*plots]
    
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

        data = {'diff':diff, 'prices':prices, 'amount':amount, 'end':end}
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
