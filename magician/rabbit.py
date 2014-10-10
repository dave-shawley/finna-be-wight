from __future__ import print_function

import json
import logging
import time

from tornado import concurrent, gen
import pika
import pika.adapters
import pika.exceptions
import pika.spec


class RabbitConnection(object):

    def __init__(self, amqp_url, custom_ioloop=None):
        super(RabbitConnection, self).__init__()
        self.amqp_url = amqp_url
        self._connection = None
        self._future = None
        self._channels = []
        self._custom_io_loop = custom_ioloop
        self._logger = logging.getLogger('RabbitConnection')
        self._logger.debug('connection created for %s', self.amqp_url)

    @gen.coroutine
    def connect(self):
        """
        Asynchronously connect to rabbit.

        :return: a :class:`pika.Channel` instance
        :raises pika.exceptions.AMQPError:
            if a protocol error occurs when connecting to the
            AMQP broker

        """
        self._future = concurrent.Future()
        if self._connection is None:
            self._logger.debug('connecting to %s', self.amqp_url)

            def on_connection_failure(*args):
                self._logger.error('connection failure - %s', args)
                self._future.set_exception(pika.exceptions.AMQPConnectionError)

            pika.adapters.TornadoConnection(
                pika.URLParameters(self.amqp_url),
                on_open_callback=self.open_channel,
                on_open_error_callback=on_connection_failure,
                custom_ioloop=self._custom_io_loop,
            )
        else:
            self._logger.debug('already connected, scanning channel cache')
            while self._channels:
                channel = self._channels.pop()
                if channel.is_open:
                    self._logger.debug('returning cached channel %s (%d)',
                                       channel, channel.channel_number)
                    raise gen.Return(channel)

            self._logger.debug('generating channel')
            self._connection.channel(
                on_open_callback=self.handle_channel_opened)

        self._logger.debug('waiting on connection')
        channel = yield gen.YieldFuture(self._future)
        self._logger.debug('received channel %s (%d)',
                           channel, channel.channel_number)
        raise gen.Return(channel)

    def open_channel(self, connection):
        self._logger.debug('connected to %s, asking for channel', connection)
        self._connection = connection
        connection.add_on_close_callback(self.handle_connection_closed)
        connection.channel(on_open_callback=self.handle_channel_opened)

    def handle_connection_closed(self, *args):
        self._logger.info('connection closed - %s', args)
        self._connection = None
        self._channels = []

    def handle_channel_opened(self, channel):
        self._logger.debug('channel opened: %s (%d)',
                           channel, channel.channel_number)
        channel.add_on_close_callback(self.handle_channel_closed)
        self._future.set_result(channel)
        self._future = None

    def handle_channel_closed(self, dead_channel, *args):
        self._logger.debug('channel %s (%d) closed - %s',
                           dead_channel, dead_channel.channel_number, args)
        for index, channel in self._channels:
            if channel.channel_number == dead_channel.channel_number:
                self._logger.debug('removing channel %d from internal list',
                                   channel.channel_number)
                del self._channels[index]
                break

    def return_channel(self, channel):
        if channel is not None:
            if channel.is_open:
                self._logger.debug('channel %d returned',
                                   channel.channel_number)
                self._channels.append(channel)
            else:
                self._logger.debug('closed channel %d returned, discarding',
                                   channel.channel_number)


class PublisherMixin(object):

    def __init__(self, *args, **kwargs):
        super(PublisherMixin, self).__init__(*args, **kwargs)
        self.channel = None
        self.connection = None

    @gen.coroutine
    def prepare(self):
        super(PublisherMixin, self).prepare()
        self.rabbit_url = 'amqp://guest:guest@localhost:5672/%2F'
        rabbit_holes = getattr(self.application, '_rabbit_holes', None)
        if rabbit_holes is None:
            rabbit_holes = self.application._rabbit_holes = {}

        try:
            self.connection = rabbit_holes[self.rabbit_url]
        except KeyError:
            self.connection = RabbitConnection(self.rabbit_url)
            rabbit_holes[self.rabbit_url] = self.connection

        self.channel = yield self.connection.connect()

    def on_finish(self):
        if self.channel is not None:
            self.connection.return_channel(self.channel)

    @gen.coroutine
    def publish(self, exchange, routing_key, body, **properties):

        amqp_properties = pika.BasicProperties(
            content_type=properties.get('content_type', None),
            content_encoding=properties.get('content_encoding', None),
            headers=properties.get('headers', None),
            delivery_mode=properties.get('delivery_mode', None),
            priority=properties.get('priority', None),
            correlation_id=properties.get('correlation_id', None),
            reply_to=properties.get('reply_to', None),
            expiration=properties.get('expiration', None),
            message_id=properties.get('message_id', None),
            timestamp=properties.get('timestamp', time.time()),
            type=properties.get('type', None),
            user_id=properties.get('user_id', None),
            app_id=properties.get('app_id', None),
            cluster_id=properties.get('cluster_id', None),
        )

        if amqp_properties.content_type is not None:
            content_type = amqp_properties.content_type
            if ';' in content_type:
                content_type = content_type[:content_type.index(';')].strip()
            if content_type.endswith('json'):
                body = json.dumps(body).encode('utf-8')

        future = concurrent.Future()

        def channel_closed(*args):
            print('CLOSED', args)
            future.set_result(500)

        def delivery_callback(*args):
            print('CONFIRMED', args)
            future.set_result(200)

        # self.channel.add_on_close_callback(channel_closed)
        self.channel.callbacks.add(
            prefix=self.channel.channel_number,
            key='_on_channel_close',
            callback=channel_closed,
            one_shot=True,
            only_caller=self.channel,
        )

        # self.channel.confirm_delivery(delivery_callback)
        self.channel.callbacks.add(
            self.channel.channel_number,
            pika.spec.Basic.Ack,
            delivery_callback,
            one_shot=True,
        )
        self.channel.callbacks.add(
            self.channel.channel_number,
            pika.spec.Basic.Nack,
            delivery_callback,
            one_shot=True,
        )
        self.channel.confirm_delivery()

        print('PUBLISHING F`REAL')
        self.channel.basic_publish(
            exchange, routing_key, body,
            mandatory=properties.get('mandatory', False),
            properties=amqp_properties,
        )

        status_code = yield gen.YieldFuture(future)
        raise gen.Return(status_code)
