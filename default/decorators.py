import os
from functools import wraps
from zipfile import ZipFile

from dateutil import parser
from django.http import HttpResponse, JsonResponse
from django.utils.translation import gettext as _

from default.data_file import DataFile
from default.util import invalid_request_file_message


def clear_files(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        request.session['files'] = []
        return function(request, *args, **kwargs)

    return wrap


def require_files(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if 'files' not in request.session:
            return JsonResponse({'error': 'No files uploaded'}, status=400, reason='No files available for operation')
        return function(request, *args, **kwargs)

    return wrap


def extract_last_result(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        request_object = getattr(request, request.method)
        send_result = request_object.get('sendResult')
        if 'files' in request.session and send_result:
            # Set files session to the last generated results
            for file in request.session['results']:
                data_file = DataFile(**file)
                # All json results are compressed in a zip file
                if data_file.ext == '.zip':
                    with ZipFile(data_file.path) as zipfile:
                        for f in zipfile.infolist():
                            prefix, ext = os.path.splitext(f.filename)
                            new_file = DataFile(prefix, ext)
                            path, f.filename = os.path.split(new_file.path)
                            zipfile.extract(f, path)
                            # Open the file to check if it is the correct type
                            with open(new_file.path, 'rb') as h:
                                file_type = request_object.get('type', None)
                                message = invalid_request_file_message(h, file_type)
                                if message:
                                    return HttpResponse(message, status=401)  # error 401 for invalid type
                                else:
                                    request.session['files'].append(new_file.as_dict())
            request.session.modified = True
        return function(request, *args, **kwargs)

    return wrap


def published_date(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        published_date = request.GET.get('publishedDate', '')
        if published_date:
            try:
                parser.parse(published_date)
            except ValueError:
                kwargs['warnings'] = [
                    _('An invalid published date was submitted, and therefore ignored: %(date)s') % {
                        'date': published_date,
                    },
                ]
            else:
                kwargs['published_date'] = published_date
        return function(request, *args, **kwargs)

    return wrap


def validate_split_size(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        split_size = request.GET.get('splitSize')
        if split_size.isdecimal():
            kwargs['size'] = int(split_size)
        else:
            msg = _('An invalid split size was submitted, and therefore ignored. Default value is used, split size: 1')
            if 'warnings' in kwargs:
                kwargs['warnings'].append(msg)
            else:
                kwargs['warnings'] = [msg]
        return function(request, *args, **kwargs)

    return wrap


def validate_optional_args(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        encoding = request.GET.get('encoding', 'utf-8')
        try:
            test_str = "test"
            test_str.encode(encoding)
            kwargs['encoding'] = encoding
        except LookupError:
            msg = _('Encoding %(encoding)s ... is not recognized. The default value \'utf-8\' was used.') % {
                        'encoding': encoding,
                    }
            if 'warnings' in kwargs:
                kwargs['warnings'].append(msg)
            else:
                kwargs['warnings'] = [msg]
        kwargs['pretty_json'] = request.GET.get('pretty-json') == 'true'
        return function(request, *args, **kwargs)

    return wrap


def clear_drive_session_vars(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        val = function(request, *args, **kwargs)
        if 'auth_status' in request.session and request.session['auth_status'] in ('completed', 'success', 'failed'):
            for key in ('auth_status', 'auth_response', 'auth_status_error', 'google_drive_file'):
                request.session.pop(key, None)
        return val
    return wrap


def require_get_param(param_name):
    def decorator(function):
        @wraps(function)
        def wrap(request, *args, **kwargs):
            if param_name not in request.GET:
                return JsonResponse({'error': _('The {} parameter is required'.format(param_name))}, status=400)
            return function(request, *args, **kwargs)
        return wrap
    return decorator
