#!/usr/bin/env python
#-*- coding : utf-8 -*-
import os,re, sys
import os.path
import sqlite3
import multiprocessing
from multiprocessing import Pool
import json
import time
import socket
import urlparse
import BaseHTTPServer
import threading
import signal
from optparse import OptionParser
from twisted.python import log
from twisted.application.service import Service
import pexpect

DISTANCE_PROC = './word2vec/distance data'
#DISTANCE_CHILD = None
DISTANCE_EXPECT = 'Enter word or sentence \(EXIT to break\): '

WORD_ANALOGY_PROC = './word2vec/word-analogy data'
#WORD_ANALOGY_CHILD = None
WORD_ANALOGY_EXPECT = 'Enter three words \(EXIT to break\): '

class Word2Vec():
    def __init__(self):
        #self.pool = Pool(1, initializer=self.init)
        self.init()

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['pool']
        return self_dict

    def __setstate__(self, state):
        self.__dict__.update(state)

    def init(self):
        self.distance_child = pexpect.spawn(DISTANCE_PROC)
        self.distance_child.expect([DISTANCE_EXPECT, pexpect.EOF], timeout=60)
        self.word_analogy_child = pexpect.spawn(WORD_ANALOGY_PROC)
        self.word_analogy_child.expect([WORD_ANALOGY_EXPECT, pexpect.EOF], timeout=60)

    def distance(self, environ):
        params = urlparse.parse_qs(environ['QUERY_STRING'])
        query = params.get('q', [''])[0]
        log.msg('distance - ' + query)
        result = 'query is null'
        if query:
            '''
            r = self.pool.apply_async(self.run_distance, [query])
            try:
                result = r.get(timeout=10)
            except multiprocessing.TimeoutError:
                result = 'TimeoutError'
            '''
            result = self.run_distance(query)
        form = {
            'result': result
        }
        return json.dumps(form)

    def word_analogy(self, environ):
        params = urlparse.parse_qs(environ['QUERY_STRING'])
        q1 = params.get('q1', [''])[0]
        q2 = params.get('q2', [''])[0]
        q3 = params.get('q3', [''])[0]
        result = 'query is null'
        if q1 and q2 and q3:
            '''
            r = self.pool.apply_async(self.run_word_analogy, [q1, q2, q3])
            try:
                result = r.get(timeout=10)
            except multiprocessing.TimeoutError:
                result = 'TimeoutError'
            '''
            result = self.run_word_analogy(q1, q2, q3)
        form = {
            'result': result
        }
        return json.dumps(form)

    def run_distance(self, query):
        log.msg('distance : ' + query)
        self.distance_child.sendline(query)
        self.distance_child.expect([DISTANCE_EXPECT, pexpect.EOF], timeout=10)
        log.msg(self.distance_child.before)
        log.msg(self.distance_child.after)
        return self.distance_child.before

    def run_word_analogy(self, q1, q2, q3):
        log.msg('%s %s %s' % (q1, q2, q3))
        self.word_analogy_child.sendline('%s %s %s' %(q1, q2, q3))
        self.word_analogy_child.expect([WORD_ANALOGY_EXPECT, pexpect.EOF], timeout=10)
        log.msg(self.word_analogy_child.before)
        log.msg(self.word_analogy_child.after)
        return self.word_analogy_child.before


def index(environ):
    r = open('index.html')
    index = r.read()
    r.close()
    return index

def application(environ, start_response):
    URI_MAP = {
        '/': (index, [('Content-type', 'text/html')]),
        '/distance': (word2vec.distance, [('Content-type', 'json')]),
        '/word-analogy': (word2vec.word_analogy, [('Content-type', 'json')]),
    }

    # get uri and query parsing
    uri = environ['PATH_INFO']

    # uri checker and switching
    process, header = URI_MAP.get(uri, URI_MAP.get('/'))

    # result
    result = process(environ)

    # output
    start_response('200 OK', header)
    return [result]

shutdown_event = threading.Event()

def CTRL_C_HANLER(signal, frame):
    shutdown_event.set()

signal.signal(signal.SIGINT, CTRL_C_HANLER)


word2vec = Word2Vec()

class ProcessHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def lookup(self):
        table = {
            '/': (self.index, 'text/html'),
            '/distance': (self.distance, 'json'),
            '/word-analogy': (self.word_analogy, 'json'),
            '/shutdown': (self.shutdown, 'json'),
        }

        log.msg(self.path)
        if self.path.find('distance') != -1:
            return table['/distance']
        if self.path.find('word-analogy') != -1:
            return table['/word-analogy']
        return table.get(self.path, table['/'])

    def header(self, http_status, content_type):
        self.send_response(http_status)
        self.send_header("Content-type", content_type)
        self.end_headers()

    def do_GET(self):
        handler, content_type = self.lookup()
        environ = { 'QUERY_STRING': urlparse.urlparse(self.path).query }
        http_status, response = handler(environ)
        self.header(http_status, content_type)
        self.wfile.write(response)

    def index(self, environ):
        return 200, index(environ)

    def shutdown(self, environ):
        shutdown_event.set()
        return 200, { 'code' : 200, 'result' : 'shutdown' }

    def distance(self, environ):
        return 200, word2vec.distance(environ)

    def word_analogy(self, environ):
        return 200, word2vec.word_analogy(environ)

def main(argv=None):
    PORT_NUMBER = 9999

    if argv is None:
        argv = sys.argv[1:]

    parser = OptionParser()
    parser.add_option("-p", "--port", dest="port", help="port", default=PORT_NUMBER)
    (opts, args) = parser.parse_args(argv)

    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class(("", opts.port), ProcessHandler)
    print time.asctime(), "Server Starts - %s" % (opts.port)
    httpd.serve_forever()

    shutdown_event.wait()
    httpd.shutdown()
    print time.asctime(), "Server Stops - %s" % (opts.port)
    return 0

if __name__ == '__main__':
    sys.exit(main())
