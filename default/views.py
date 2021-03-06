import json
import os
import shutil
from collections import OrderedDict
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

import flattentool
from django.core.cache import cache
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from jsonref import requests
from libcoveocds.config import LibCoveOCDSConfig
from ocdskit.combine import combine_record_packages, combine_release_packages, merge
from ocdskit.combine import package_releases as package_releases_method
from ocdskit.upgrade import upgrade_10_11
from requests.exceptions import ConnectionError, HTTPError, SSLError

from default.data_file import DataFile
from default.decorators import (clear_drive_session_vars, clear_files, extract_last_result, published_date,
                                require_files, require_get_param, validate_optional_args, validate_split_size)
from default.forms import MappingSheetOptionsForm, UnflattenOptionsForm
from default.google_drive import get_credentials_from_session, google_api_messages, upload_to_drive
from default.mapping_sheet import (get_extended_mapping_sheet, get_mapping_sheet_from_uploaded_file,
                                   get_mapping_sheet_from_url)
from default.util import (flatten, get_cache_name, get_files_from_session, invalid_request_file_message, json_response,
                          make_package, ocds_command, ocds_tags, resolve_schema_refs)


def get_datafile_filename(folder, id, format):
    if format is None:
        prefix = 'result'
        ext = '.zip'
        filename = 'result.zip'
    elif format == 'csv':
        prefix = 'result'
        ext = '.csv'
        filename = 'result.csv'
    elif format == 'csv.zip':
        prefix = 'flatten-csv'
        ext = '.zip'
        filename = 'result.csv.zip'
    elif format == 'xlsx':
        prefix = 'flatten'
        ext = '.xlsx'
        filename = 'result.xlsx'
    else:
        raise Http404('Invalid option')

    return DataFile(prefix, ext, id=str(id), folder=folder), filename


def retrieve_result(request, folder, id, format=None):
    file, filename = get_datafile_filename(folder, id, format)

    return FileResponse(open(file.path, 'rb'), filename=filename, as_attachment=True)


def index(request):
    return render(request, 'default/index.html')


@clear_files
def to_spreadsheet(request):
    context = {
        'form': UnflattenOptionsForm(),
        'performAction': '/to-spreadsheet/go/'
    }
    return render(request, 'default/to-spreadsheet.html', context)


@clear_files
def to_json(request):
    context = {
        'performAction': '/to-json/go/'
    }
    return render(request, 'default/to-json.html', context)


@clear_files
def compile(request):
    return ocds_command(request, 'compile')


@clear_files
def package_releases(request):
    return ocds_command(request, 'package-releases')


@clear_files
def combine_packages(request):
    return ocds_command(request, 'combine-packages')


@clear_files
def split_packages(request):
    return ocds_command(request, 'split-packages')


@clear_files
def upgrade(request):
    return ocds_command(request, 'upgrade')


@require_files
@extract_last_result
@validate_optional_args
def perform_upgrade(request, pretty_json=False, encoding='utf-8', warnings=None):
    data = {}
    for file in get_files_from_session(request):
        data.update({file.name_with_suffix('upgraded'): upgrade_10_11(
            file.json(codec=encoding, object_pairs_hook=OrderedDict))})
    return json_response(request, data, warnings, pretty_json, encoding)


@require_GET
@require_get_param('url')
def get_schema_as_options(request):
    try:
        key = get_cache_name('schema_options', request.GET.get('url'))
        omit_deprecated = request.GET.get('omitDeprecated', 'true')
        schema = cache.get(key)
        if not schema:
            response = requests.get(request.GET.get('url'))
            response.raise_for_status()
            schema = resolve_schema_refs(json.loads(response.text))
            cache.set(key, schema, 60*60*24*2)
        return render(request, 'default/flatten_schema_options.html',
                      {'schema': schema, 'omitDeprecated': omit_deprecated == 'true'})
    except Exception:
        return HttpResponse(_('There was an error retrieving the schema requested'), status=500)


@require_files
@extract_last_result
@published_date
@validate_optional_args
def perform_package_releases(request, pretty_json=False, published_date='', encoding='utf-8', warnings=None):
    method = package_releases_method
    return make_package(request, published_date, method, pretty_json, encoding, warnings)


@require_files
@extract_last_result
@published_date
@validate_optional_args
def perform_combine_packages(request, pretty_json=False, published_date='', encoding='utf-8', warnings=None):
    if request.GET.get('packageType') == 'release':
        method = combine_release_packages
    else:
        method = combine_record_packages
    return make_package(request, published_date, method, pretty_json, encoding, warnings)


@require_files
@extract_last_result
@published_date
@validate_optional_args
@validate_split_size
def perform_split_packages(request, pretty_json=False, published_date='', size=1, encoding='utf-8', warnings=None):
    change_published_date = request.GET.get('changePublishedDate') == 'true'
    packages = [file.json(codec=encoding) for file in get_files_from_session(request)]

    if request.GET.get('packageType') == 'release':
        package_data = 'releases'
    else:
        package_data = 'records'

    if not published_date:
        change_published_date = False

    count = 0
    result = {}

    for package in packages:
        if isinstance(package, list):
            packages.extend(package)
            continue

        context = package[package_data]

        # based on:
        # cdskit/ocdskit/cli/commands/split_record_packages.py
        # cdskit/ocdskit/cli/commands/split_release_packages.py

        # we don't know which packages were used for each record.
        if package_data == 'records' and 'packages' in package:
            del package['packages']

        for i in range(0, len(context), size):
            count += 1
            name = "result{}.json".format(count)
            content = dict(package)
            if change_published_date:
                content['publishedDate'] = published_date
            content[package_data] = context[i:i + size]
            result.update({name: content})

    return json_response(request, result, warnings, pretty_json, encoding)


@require_files
@extract_last_result
@published_date
@validate_optional_args
def perform_compile(request, pretty_json=False, published_date='', encoding='utf-8', warnings=None):
    packages = [file.json(codec=encoding) for file in get_files_from_session(request)]
    return_versioned_release = request.GET.get('includeVersioned') == 'true'

    return json_response(request, {
        'result.json': next(merge(packages, return_package=True, published_date=published_date,
                                  return_versioned_release=return_versioned_release)),
    }, warnings, pretty_json, encoding)


def mapping_sheet(request):
    context = {
        'versionOptions': {
            '1.1': {
                'Release': 'https://standard.open-contracting.org/1.1/en/release-schema.json',
                'Release Package': 'https://standard.open-contracting.org/1.1/en/release-package-schema.json',
                'Record Package': 'https://standard.open-contracting.org/1.1/en/record-package-schema.json',
            },
            '1.1 (Español)': {
                'Release': 'http://standard.open-contracting.org/1.1/es/release-schema.json',
                'Paquete de Release': 'http://standard.open-contracting.org/1.1/es/release-schema.json',
                'Paquete de Record': 'http://standard.open-contracting.org/1.1/es/record-package-schema.json',
            },
            '1.0': {
                'Release': 'https://standard.open-contracting.org/schema/1__0__3/release-schema.json',
                'Release Package': 'https://standard.open-contracting.org/schema/1__0__3/release-package-schema.json',
                'Record Package': 'https://standard.open-contracting.org/schema/1__0__3/record-package-schema.json',
            },
        },
    }

    if request.method == 'POST':
        form = MappingSheetOptionsForm(request.POST, request.FILES)

        if form.is_valid():
            type_selected = form.cleaned_data['type']
            result = None
            if type_selected == 'select':
                result = get_mapping_sheet_from_url(form.cleaned_data['select_url'])
            if type_selected == 'url':
                result = get_mapping_sheet_from_url(form.cleaned_data['custom_url'])
            if type_selected == 'file':
                result = get_mapping_sheet_from_uploaded_file(request.FILES['custom_file'])
            if type_selected == 'extension':
                result = get_extended_mapping_sheet(form.cleaned_data['extension_urls'], form.cleaned_data['version'])

            context['result'] = result or {'error': _('No valid option selected')}

    elif request.method == 'GET':
        if 'source' in request.GET:
            return get_mapping_sheet_from_url(request.GET['source'], as_response=True)
        if 'extension' in request.GET:
            if 'version' in request.GET:
                version = request.GET['version']
            else:
                version = ocds_tags()[-1]
            return get_extended_mapping_sheet(request.GET.getlist('extension'), version, as_response=True)

        form = MappingSheetOptionsForm()

    context['form'] = form
    return render(request, 'default/mapping_sheet.html', context)


@require_files
@extract_last_result
@require_POST
def perform_to_spreadsheet(request):
    input_file = next(get_files_from_session(request))
    output_dir = DataFile('flatten', '', input_file.id, input_file.folder)

    form = UnflattenOptionsForm(request.POST)

    if not form.is_valid():
        return JsonResponse({'form_errors': dict(form.errors)}, status=400)

    flatten(input_file, output_dir, form.non_empty_values())

    response = {}
    if form.cleaned_data['output_format'] == 'all' or form.cleaned_data['output_format'] == 'csv':
        # Create a ZIP file of the CSV files, and delete the output CSV files.
        csv_zip = DataFile('flatten-csv', '.zip', id=input_file.id, folder=input_file.folder)
        with ZipFile(csv_zip.path, 'w', compression=ZIP_DEFLATED) as zipfile:
            for filename in os.listdir(output_dir.path):
                zipfile.write(os.path.join(output_dir.path, filename), filename)
        shutil.rmtree(output_dir.path)

        response['csv'] = {
            'url': input_file.url + 'csv.zip/',
            'size': csv_zip.size,
            'driveUrl': input_file.url.replace('result', 'google-drive-save-start') + 'csv.zip/'
        }

    if form.cleaned_data['output_format'] == 'all' or form.cleaned_data['output_format'] == 'xlsx':
        response['xlsx'] = {
            'url': input_file.url + 'xlsx/',
            'size': os.path.getsize(output_dir.path + '.xlsx'),
            'driveUrl': input_file.url.replace('result', 'google-drive-save-start') + 'xlsx/'
        }

    return JsonResponse(response)


@require_files
@extract_last_result
@validate_optional_args
def perform_to_json(request, pretty_json=False, encoding='utf-8', warnings=None):
    input_file = next(get_files_from_session(request))
    output_dir = DataFile('unflatten', '', input_file.id, input_file.folder)

    output_name = output_dir.path + '.json'
    extension = os.path.splitext(input_file.path)[1]
    if extension == '.xlsx':
        input_file_path = input_file.path
        input_format = 'xlsx'
    else:
        input_file_path = output_dir.path
        input_format = 'csv'
        if extension == '.zip':
            with ZipFile(input_file.path) as zipfile:
                for name in zipfile.namelist():
                    zipfile.extract(name, input_file_path)
        else:
            if extension == '.csv':
                os.mkdir(input_file_path)
                shutil.copy(input_file.path, input_file_path)

    config = LibCoveOCDSConfig().config
    flattentool.unflatten(
        input_file_path,
        input_format=input_format,
        output_name=output_name,
        root_list_path=config['root_list_path'],
        root_id=config['root_id']
    )

    # Delete the input CSV files, if any.
    if extension in ('.csv', '.zip'):
        shutil.rmtree(input_file_path)

    with open(output_name) as json_file:
        return json_response(request, {'result.json': json.load(json_file)}, warnings, pretty_json, encoding)


@require_POST
def upload_url(request):
    request.session['files'] = []
    errors = []
    status = 401  # error 401 for invalid type

    for data in request.POST:
        if 'input_url' in data:
            url = request.POST.get(data)
            basename = data
            file_type = request.POST.get('type', None)
            if file_type == '.csv .xlsx .zip':
                extension = os.path.splitext(urlparse(url).path)[1]
            else:
                extension = ".json"
            folder = 'media'
            data_file = DataFile(basename, extension)

            try:
                os.stat(folder + '/' + data_file.folder)
            except FileNotFoundError:
                os.mkdir(folder + '/' + data_file.folder)

            try:
                urlparse(url)
                with requests.get(url, stream=True) as request_file:
                    request_file.raise_for_status()
                    with open(data_file.path, 'wb+') as f:
                        for chunk in request_file.iter_content(chunk_size=8*1024):
                            if chunk:
                                f.write(chunk)

            except ValueError:
                status = 400
                errors.append({'id': data, 'message': _('Enter a valid URL.')})

            except (HTTPError, ConnectionError, SSLError):
                status = 400
                message = _('There was an error when trying to access this URL. '
                            'Please verify that the URL is correct and the file has the expected format.')
                errors.append({'id': data, 'message': message})

            else:
                with open(data_file.path, 'rb') as f:
                    message = invalid_request_file_message(f, file_type)
                    if message:
                        errors.append({'id': data, 'message': message})
                    else:
                        request.session['files'].append(data_file.as_dict())
                        request.session.modified = True
                        request.session.save()

    if len(errors) > 0:
        return JsonResponse(errors, status=status, safe=False)

    return JsonResponse({
        'files': request.session['files']
    })


@require_GET
def upload_url_status(request):
    return JsonResponse(len(request.session['files']), safe=False)


@require_GET
def validate_send_result(request):
    if 'results' in request.session and request.session['results']:
        file = request.session['results'][0]  # always one result is saved
        return JsonResponse(file['prefix'] + file['ext'], safe=False)
    return HttpResponse(status=400)


@require_POST
def uploadfile(request):
    request_file = request.FILES['file']
    basename, extension = os.path.splitext(request_file.name)

    data_file = DataFile(basename, extension)
    file_type = request.POST.get('type', None)

    message = invalid_request_file_message(request_file, file_type)
    if message:
        return HttpResponse(message, status=401)  # error 401 for invalid type
    else:
        data_file.write(request_file)

    request.session.setdefault('files', []).append(data_file.as_dict())
    # https://docs.djangoproject.com/en/3.2/topics/http/sessions/#when-sessions-are-saved
    request.session.modified = True

    return JsonResponse({
        'files': [{
            'id': data_file.id,
            'name': request_file.name,
            'size': request_file.size,
        }],
    })


@require_GET
def deletefile(request, id):
    if 'files' not in request.session:
        return JsonResponse({'message': _('File not found')}, status=404)

    for fileinfo in request.session['files']:
        if fileinfo['id'] == str(id):
            request.session['files'].remove(fileinfo)
            request.session.modified = True
            return JsonResponse({'message': _('File deleted')})

    return JsonResponse({'message': _('File not found')}, status=404)


@require_GET
def googleapi_auth_callback(request):
    params = {}
    if 'code' in request.GET:
        request.session['auth_status'] = 'success'
        request.session['auth_response'] = request.build_absolute_uri(request.get_full_path())
    else:
        request.session['auth_status'] = 'failed'
        request.session['auth_status_error'] = request.GET.get('error')
        params['status'] = 'failed'
        params['error'] = request.GET.get('error')
    return render(request, 'default/googleapi-auth-finished.html')


@require_GET
@clear_drive_session_vars
def get_google_drive_save_status(request):

    if 'auth_status' not in request.session or \
            request.session['auth_status'] not in ('waiting', 'success', 'failed'):
        return JsonResponse({
            'error': True,
            'message': _('Invalid request, authentication process has not been started.')
        }, status=400)
    if request.session['auth_status'] == 'waiting':
        return JsonResponse({'status': 'waiting'})
    elif request.session['auth_status'] == 'failed':
        message_key = request.session['auth_status_error'] if request.session['auth_status_error'] else '_default'
        return JsonResponse({
            'status': 'failed',
            'message': google_api_messages[message_key]
        }, status=500)
    return upload_to_drive(request)


@require_GET
@clear_drive_session_vars
def google_drive_save_start(request, folder, id, format=None):

    file, filename = get_datafile_filename(folder, id, format)
    request.session['google_drive_file'] = file.as_dict()
    credentials = get_credentials_from_session(request)

    # credentials must be valid
    # in the case there is no refresh_token, we should prompt the user for authentication again
    if credentials and (credentials.valid or credentials.refresh_token):
        request.session['auth_status'] = 'completed'
        return upload_to_drive(request)

    request.session['auth_status'] = 'waiting'
    return JsonResponse({'authenticated': False})
