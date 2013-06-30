#!/usr/bin/python

import logging
import os
import time

import tornado.ioloop
import tornado.web
import tornado.options
import tornado.httpserver
import tornado.httpclient
import tornado.escape
import tornado.websocket
import tornado.gen

TIMEOUT = 4

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/test", TestHandler),
            (r"/socket_coinbase", SocketCoinbaseHandler),
            (r"/socket_campbx", SocketCampbxHandler),
            (r"/coinbase", CoinbaseHandler),
            (r"/campbx", CampbxHandler),
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


class BaseHandler(tornado.web.RequestHandler):
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
            print "CampBX:", response.body
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
            print "Coinbase:", response.body
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
                print "Coinbase:", response.body
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
                print "CampBX:", response.body
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


def main():
    http_server = tornado.httpserver.HTTPServer(Application(), xheaders=True)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
    logging.info("Web server started successfully")

if __name__ == "__main__":
    tornado.options.parse_command_line()
    logging.info("Starting web server")

    main()
