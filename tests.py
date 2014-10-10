from __future__ import print_function
import atexit
import logging
import urllib
import uuid

from pika import exceptions
from tornado import testing
import requests

from magician import rabbit


logging.getLogger('pika').setLevel(logging.DEBUG)
logging.getLogger('requests').setLevel(logging.DEBUG)


def amqp_control(method, *path, **kwargs):
    target = 'http://localhost:15672/api/{0}'.format(
        '/'.join(urllib.quote(segment, safe='') for segment in path))
    headers = kwargs.get('headers', {})
    headers['Content-Type'] = 'application/json'
    kwargs['headers'] = headers
    if 'auth' not in kwargs:
        kwargs['auth'] = ('guest', 'guest')
    response = requests.request(method, target, **kwargs)
    response.raise_for_status()
    return response


class RabbitConnectionConnectTests(testing.AsyncTestCase):

    @classmethod
    def setUpClass(cls):
        cls.virtual_host = '/' + uuid.uuid4().hex
        amqp_control('PUT', 'vhosts', cls.virtual_host)
        atexit.register(amqp_control, 'DELETE', 'vhosts', cls.virtual_host)

        amqp_control('PUT', 'permissions', cls.virtual_host, 'guest',
                     data='{"configure":".*","write":".*","read":".*"}')

    def setUp(self):
        super(RabbitConnectionConnectTests, self).setUp()
        amqp_url = 'amqp://guest:guest@localhost:5672/{0}'.format(
            urllib.quote(self.virtual_host, safe=''))
        self.rabbit_connection = rabbit.RabbitConnection(
            amqp_url, custom_ioloop=self.io_loop)

    @testing.gen_test
    def test_connection_blocks_until_connected(self):
        channel = yield self.rabbit_connection.connect()
        self.assertTrue(channel.is_open)

    @testing.gen_test
    def test_returned_channel_is_reused(self):
        channel = yield self.rabbit_connection.connect()
        first_channel_number = channel.channel_number
        self.rabbit_connection.return_channel(channel)

        channel = yield self.rabbit_connection.connect()
        self.assertEqual(channel.channel_number, first_channel_number)

    @testing.gen_test
    def test_closed_channel_is_not_reused(self):
        channel = yield self.rabbit_connection.connect()
        first_channel = channel
        self.rabbit_connection.return_channel(channel)
        first_channel.close()

        channel = yield self.rabbit_connection.connect()
        self.assertTrue(channel is not first_channel)

    @testing.gen_test
    def test_connection_failures_are_reported(self):
        new_connection = rabbit.RabbitConnection(
            'amqp://guest:guest@example.com:5672/%2F{0}?{1}'.format(
                uuid.uuid4().hex,
                urllib.urlencode({
                    'connection_attempts': 1,
                    'retry_delay': 0.001,
                    'socket_timeout': 0.001,
                }),
            ),
            custom_ioloop=self.io_loop,
        )
        try:
            yield new_connection.connect()
        except exceptions.AMQPError:
            return
        self.fail('Expected exception to be raised')

    @testing.gen_test
    def test_connecting_on_closed_connection(self):
        def print_message(msg):
            def printer(*args):
                logging.debug(msg + ': %s', args)
            return printer

        first_channel = yield self.rabbit_connection.connect()
        self.rabbit_connection._connection.add_on_close_callback(
            print_message('CONNECTION CLOSED'))
        first_channel.add_on_close_callback(
            print_message('FIRST CHANNEL CLOSED'))
        logging.debug('CLOSING CONNECTION')

        self.io_loop.run_sync(self.rabbit_connection._connection.close)

        logging.debug('ATTEMPTING SECOND OPEN')
        second_channel = yield self.rabbit_connection.connect()
        self.assertEqual(first_channel, second_channel)
