import json
from unittest.mock import patch

import pytest

from django.test import override_settings
from django.utils.translation import override

import requests

from rdmo_gnd.providers import GNDProvider

ERROR_RESPONSE = {
    'error': 'Internal Server Error',
    'message': 'finishConnect(..) failed with error(-111): Connection refused: quaoar13/10.9.0.18:7100',
    'requestId': '12bc3ab5-5073828',
    'status': 500,
    'timestamp': '2026-10-26T08:18:27.562+00:00',
}


@pytest.fixture
def provider():
    return GNDProvider('gnd', 'GND Provider', 'rdmo_gnd.providers.GNDProvider')


@pytest.fixture
def get():
    with patch('rdmo_gnd.providers.requests.get') as mocked_get:
        yield mocked_get


def response(data, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    result.url = 'https://lobid.org/gnd/search'
    return result


def assert_error_options(options):
    assert options == [
        {
            'id': '__gnd_request_error__',
            'text': 'The GND service is currently unavailable. Please try again later.',
            'isDisabled': True,
        }
    ]


@pytest.mark.parametrize('status', [400, 429, 500, 502, 503])
def test_http_error(provider, get, status, caplog):
    get.return_value = response(ERROR_RESPONSE, status)

    assert_error_options(provider.get_options(None, search='Einstein'))
    assert 'GND search failed' in caplog.text


@pytest.mark.parametrize('error', [requests.exceptions.ConnectionError, requests.exceptions.Timeout])
def test_request_error(provider, get, error):
    get.side_effect = error('Service unavailable')

    assert_error_options(provider.get_options(None, search='Einstein'))


@pytest.mark.parametrize(
    ('language', 'message'),
    [
        ('en', 'The GND service is currently unavailable. Please try again later.'),
        ('de', 'Der GND-Dienst ist derzeit nicht verfügbar. Bitte versuchen Sie es später erneut.'),
    ],
)
def test_translated_error(provider, get, language, message):
    get.return_value = response(ERROR_RESPONSE, 500)

    with override(language):
        options = provider.get_options(None, search='Einstein')

    assert options[0]['text'] == message
    assert options[0]['isDisabled'] is True


def test_invalid_json(provider, get):
    get.return_value = response(None)
    get.return_value._content = b'<html>Service unavailable</html>'

    assert_error_options(provider.get_options(None, search='Einstein'))


@pytest.mark.parametrize(
    'data',
    [
        ERROR_RESPONSE,
        {},
        None,
        [],
        {'totalItems': 1},
        {'totalItems': 1, 'member': None},
        {'totalItems': 1, 'member': [{}]},
    ],
)
def test_unexpected_response(provider, get, data):
    get.return_value = response(data)

    assert_error_options(provider.get_options(None, search='Einstein'))


@pytest.mark.parametrize('search', [None, ''])
def test_no_search(provider, get, search):
    assert provider.get_options(None, search=search) == []
    get.assert_not_called()


def test_no_results(provider, get):
    get.return_value = response({'totalItems': 0, 'member': []})

    assert provider.get_options(None, search='Einstein') == []


@pytest.mark.parametrize('profession', [None, [], [{'label': 'Physicist'}]])
def test_search_results(provider, get, profession):
    item = {
        'id': 'https://d-nb.info/gnd/118529579',
        'gndIdentifier': '118529579',
        'preferredName': 'Einstein, Albert',
    }
    if profession is not None:
        item['professionOrOccupation'] = profession
    get.return_value = response({'totalItems': 1, 'member': [item]})
    text = 'Einstein, Albert'
    if profession:
        text += ' | Physicist'
    text += ' [<a href="https://d-nb.info/gnd/118529579">118529579</a>]'

    assert provider.get_options(None, search='Einstein') == [{'id': '118529579', 'text': text}]
    get.assert_called_once_with(
        'https://lobid.org/gnd/search',
        params={'q': 'Einstein', 'format': 'json'},
        headers={},
        timeout=10,
    )


@override_settings(
    GND_PROVIDER_URL='https://example.org/gnd/',
    GND_PROVIDER_HEADERS={'User-Agent': 'NFDI4Ing RDMO GND integration; mailto:rdmo@nfdi4ing.de'},
    GND_PARAMS={'filter': '+(type:Person)'},
    GND_PROVIDER_TIMEOUT=3,
)
def test_search_settings(provider, get):
    get.return_value = response({'totalItems': 0, 'member': []})

    assert provider.get_options(None, search='Einstein | Physicist [118529579]') == []
    get.assert_called_once_with(
        'https://example.org/gnd/search',
        params={'q': 'Einstein', 'format': 'json', 'filter': '+(type:Person)'},
        headers={'User-Agent': 'NFDI4Ing RDMO GND integration; mailto:rdmo@nfdi4ing.de'},
        timeout=3,
    )
