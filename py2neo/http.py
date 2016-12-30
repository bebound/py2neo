#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2011-2016, Nigel Small
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from py2neo import PRODUCT
from py2neo.addressing import keyring
from py2neo.packages.httpstream import http, ClientError, ServerError, \
    Resource as _Resource, ResourceTemplate as _ResourceTemplate
from py2neo.packages.httpstream.http import JSONResponse, user_agent
from py2neo.packages.httpstream.numbers import UNAUTHORIZED
from py2neo.status import GraphError, Unauthorized
from py2neo.util import raise_from

http.default_encoding = "UTF-8"

_http_headers = {
    (None, None, None): [
        ("User-Agent", user_agent(PRODUCT)),
        ("X-Stream", "true"),
    ],
}


def set_http_header(key, value, scheme=None, host=None, port=None):
    """ Add an HTTP header for all future requests. If a `host_port` is
    specified, this header will only be included in requests to that
    destination.

    :arg key: name of the HTTP header
    :arg value: value of the HTTP header
    :arg scheme:
    :arg host:
    :arg port:
    """
    address_key = (scheme, host, port)
    if address_key in _http_headers:
        _http_headers[address_key].append((key, value))
    else:
        _http_headers[address_key] = [(key, value)]


def get_http_headers(scheme, host, port):
    """Fetch all HTTP headers relevant to the `host_port` provided.

    :arg scheme:
    :arg host:
    :arg port:
    """
    uri_headers = {}
    for (s, h, p), headers in _http_headers.items():
        if (s is None or s == scheme) and (h is None or h == host) and (p is None or p == port):
            uri_headers.update(headers)
    for address, auth in keyring.items():
        if auth and address.host == host and address.http_port == port:
            uri_headers["Authorization"] = auth.http_authorization
    return uri_headers


class Resource(_Resource):
    """ Base class for all local resources mapped to remote counterparts.
    """

    def __init__(self, uri, metadata=None, headers=None):
        self._resource = _Resource.__init__(self, uri)
        self._headers = dict(headers or {})
        self.__base = super(Resource, self)
        if metadata is None:
            self.__initial_metadata = None
        else:
            self.__initial_metadata = dict(metadata)
        self.__last_get_response = None

        dbms_uri = uri[:uri.find("/", uri.find("//") + 2)] + "/"
        if dbms_uri == uri:
            self.__dbms = self
        else:
            from py2neo.database import DBMS
            self.__dbms = DBMS(dbms_uri)
        self.__ref = NotImplemented

    @property
    def graph(self):
        """ The parent graph of this resource.

        :rtype: :class:`.Graph`
        """
        return self.__dbms.graph

    @property
    def headers(self):
        """ The HTTP headers sent with this resource.
        """
        headers = get_http_headers(self.__uri__.scheme, self.__uri__.host, self.__uri__.port)
        headers.update(self._headers)
        return headers

    @property
    def metadata(self):
        """ Metadata received in the last HTTP response.
        """
        if self.__last_get_response is None:
            if self.__initial_metadata is not None:
                return self.__initial_metadata
            self.get()
        return self.__last_get_response.content

    def resolve(self, reference, strict=True):
        """ Resolve a URI reference against the URI for this resource,
        returning a new resource represented by the new target URI.

        :arg reference: Relative URI to resolve.
        :arg strict: Strict mode flag.
        :rtype: :class:`.Resource`
        """
        return Resource(_Resource.resolve(self, reference, strict).uri.string)

    @property
    def dbms(self):
        """ The root service associated with this resource.

        :return: :class:`.DBMS`
        """
        return self.__dbms

    def get(self):
        """ Perform an HTTP GET to this resource.
        """
        try:
            response = self.__base.get(headers=self.headers, cache=True)
        except (ClientError, ServerError) as error:
            if error.status_code == UNAUTHORIZED:
                raise Unauthorized(self.uri.string)
            if isinstance(error, JSONResponse):
                content = dict(error.content, request=error.request, response=error)
            else:
                content = {}
            message = content.pop("message", "HTTP GET returned response %s" % error.status_code)
            raise_from(GraphError(message, **content), error)
        else:
            self.__last_get_response = response
            return response

    def post(self, body=None):
        """ Perform an HTTP POST to this resource.
        """
        try:
            response = self.__base.post(body, self.headers)
        except (ClientError, ServerError) as error:
            if error.status_code == UNAUTHORIZED:
                raise Unauthorized(self.uri.string)
            if isinstance(error, JSONResponse):
                content = dict(error.content, request=error.request, response=error)
            else:
                content = {}
            message = content.pop("message", "HTTP POST returned response %s" % error.status_code)
            raise_from(GraphError(message, **content), error)
        else:
            return response

    def delete(self):
        """ Perform an HTTP DELETE to this resource.
        """
        try:
            response = self.__base.delete(self.headers)
        except (ClientError, ServerError) as error:
            if error.status_code == UNAUTHORIZED:
                raise Unauthorized(self.uri.string)
            if isinstance(error, JSONResponse):
                content = dict(error.content, request=error.request, response=error)
            else:
                content = {}
            message = content.pop("message", "HTTP DELETE returned response %s" % error.status_code)
            raise_from(GraphError(message, **content), error)
        else:
            return response
