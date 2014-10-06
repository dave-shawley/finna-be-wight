import json

from tornado import web


_DEFAULT_ARGUMENT = object()


class MissingParameter(web.HTTPError):

    def __init__(self, name):
        super(MissingParameter, self).__init__(
            status_code=400,
            log_message='Missing parameter {0}'.format(name),
        )
        self.parameter_name = name


class InvalidParameter(web.HTTPError):

    def __init__(self, name, value):
        super(InvalidParameter, self).__init__(
            status_code=400,
            log_message='"{0}" is not a valid value for {1}'.format(
                str(value), name),
        )
        self.parameter_name = name
        self.parameter_value = value


def extract_parameter(name, params, default, factory):
    try:
        value = params[name]
        if factory is not None:
            value = factory(value)
    except ValueError:
        raise InvalidParameter(name, value)
    except KeyError:
        if default is _DEFAULT_ARGUMENT:
            raise MissingParameter(name)
        value = default
    return value


class ParameterMixin(object):

    def prepare(self):
        super(ParameterMixin, self).prepare()
        self._json = None

    def path_parameter(self, name, default=_DEFAULT_ARGUMENT, factory=None):
        return extract_parameter(name, self.path_kwargs, default, factory)

    def json_parameter(self, name, default=_DEFAULT_ARGUMENT, factory=None):
        if self._json is None:
            self._json = json.loads(self.request.body)
        return extract_parameter(name, self._json, default, factory)
