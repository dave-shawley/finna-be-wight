from __future__ import print_function
import json
try:
    from urllib import parse
except ImportError:
    import urllib as parse

from pika import exceptions
from tornado import gen, httpclient, ioloop, web

from magician import parameters, rabbit


def to_bool(value):
    if value.lower() == 'false':
        return False
    if value.lower() == 'true':
        return True
    try:
        return bool(int(value))
    except ValueError:
        pass
    raise ValueError(value)


class RabbitCreator(parameters.ParameterMixin, web.RequestHandler):

    def prepare(self):
        super(RabbitCreator, self).prepare()
        self.client = httpclient.AsyncHTTPClient(defaults={
            'auth_username': 'guest', 'auth_password': 'guest',
        })

    def _call_api(self, method, *path, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['Content-Type'] = 'application/json'

        body = kwargs.get('body', None)
        if body is not None:
            kwargs['body'] = json.dumps(body)

        request = httpclient.HTTPRequest(
            self._rabbit_url(*path), method=method,
            headers=headers, **kwargs)
        print('REQUEST', request, request.url, request.headers)
        return self.client.fetch(request)

    @staticmethod
    def _rabbit_url(*path):
        url = 'http://localhost:15672/api/{0}'.format('/'.join(
            parse.quote(segment, safe='') for segment in path))
        return url

    @gen.coroutine
    def post(self, **_):
        response = None
        item_type = self.path_parameter('itemtype')
        if item_type in ('binding', 'queue'):
            response = yield self._call_api(
                'PUT',
                'queues',
                self.json_parameter('virtual_host', default='/'),
                self.json_parameter('queue_name'),
                body={
                    'auto_delete': False,
                    'durable': self.json_parameter('durable',
                                                   default=False,
                                                   factory=to_bool),
                },
            )
            if response.code >= 400:
                raise web.HTTPError(response.code)

        if item_type in ('binding', 'exchange'):
            response = yield self._call_api(
                'PUT',
                'exchanges',
                self.json_parameter('virtual_host', default='/'),
                self.json_parameter('exchange_name'),
                body={
                    'type': self.json_parameter('exchange_type',
                                                default='topic'),
                    'durable': self.json_parameter('durable',
                                                   default=False,
                                                   factory=to_bool),
                },
            )
            if response.code >= 400:
                raise web.HTTPError(response.code)

        if item_type == 'binding':
            response = yield self._call_api(
                'POST',
                'bindings',
                self.json_parameter('virtual_host', default='/'),
                'e', self.json_parameter('exchange_name'),
                'q', self.json_parameter('queue_name'),
                body={
                    'routing_key': self.json_parameter('routing_key'),
                },
            )
            if response.code >= 400:
                raise web.HTTPError(response.code)

        if response is None:
            raise web.HTTPError(500)

        self.set_status(200)


class RabbitPublisher(
        rabbit.PublisherMixin, parameters.ParameterMixin, web.RequestHandler):

    @gen.coroutine
    def get(self, *args, **kwargs):
        try:
            print('PUBLISHING')
            result = yield self.publish('po', 'foo.mail', '{"name":"blah"}')
            print('RETURNING IT ALL')
            self.set_status(result)
        except exceptions.AMQPError:
            self.set_status(500)


application = web.Application(
    [
        (r'/(?P<itemtype>queue)', RabbitCreator),
        (r'/(?P<itemtype>exchange)', RabbitCreator),
        (r'/(?P<itemtype>binding)', RabbitCreator),
        (r'/publish', RabbitPublisher),
    ],
    debug=True,
)


if __name__ == '__main__':
    application.listen(8000)
    ioloop.IOLoop.instance().start()
