import atexit
import logging
import urllib
import uuid

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
        virtual_host = '/' + uuid.uuid4().hex
        amqp_control('PUT', 'vhosts', virtual_host)
        atexit.register(amqp_control, 'DELETE', 'vhosts', virtual_host)

        amqp_control('PUT', 'permissions', virtual_host, 'guest',
                     data='{"configure":".*","write":".*","read":".*"}')
        cls.amqp_url = 'amqp://guest:guest@localhost:5672/{0}'.format(
            urllib.quote(virtual_host, safe=''))

    @testing.gen_test
    def test_connection_blocks_until_connected(self):
        connection = rabbit.RabbitConnection(
            self.amqp_url, custom_ioloop=self.io_loop)
        channel = yield connection.connect()
        self.assertTrue(channel.is_open)
