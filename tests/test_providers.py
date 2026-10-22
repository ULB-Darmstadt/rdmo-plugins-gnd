from xml.etree import ElementTree

import pytest

from django.core.cache import caches
from django.test import override_settings
from django.utils.translation import override

import requests

from rdmo_gnd.config import DEFAULT_USER_AGENT

from .helpers import record, response

ERROR_RESPONSE = {
    'error': 'Internal Server Error',
    'message': 'finishConnect(..) failed with error(-111): Connection refused: quaoar13/10.9.0.18:7100',
    'requestId': '12bc3ab5-5073828',
    'status': 500,
    'timestamp': '2026-10-26T08:18:27.562+00:00',
}


@pytest.fixture
def get(http_get):
    return http_get


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
    assert 'GND search request failed' in caplog.text


@pytest.mark.parametrize('error', [requests.exceptions.ConnectionError, requests.exceptions.Timeout])
def test_request_error(provider, get, error):
    get.side_effect = error('Service unavailable')

    assert_error_options(provider.get_options(None, search='Einstein'))


@pytest.mark.parametrize(
    'language,message',
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
    text += ' [<a href="https://d-nb.info/gnd/118529579" target="_blank" rel="noopener noreferrer">118529579</a>]'

    assert provider.get_options(None, search='Einstein') == [{'id': '118529579', 'text': text}]
    get.assert_called_once_with(
        'https://lobid.org/gnd/search',
        params={'q': 'Einstein', 'format': 'json'},
        headers={'User-Agent': DEFAULT_USER_AGENT},
        timeout=(3, 10),
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


@override_settings(
    GND_PARAMS={
        'filter': 'type:SubjectHeading',
        'q': 'preferredName:{search} OR variantName:{search}',
    },
)
@pytest.mark.parametrize(
    'search,literal',
    [
        ('Brennstoff', '"Brennstoff"'),
        ('  erneuerbare Energie  ', '"erneuerbare Energie"'),
        ('Brennstoff [<a href="https://d-nb.info/gnd/4008155-6">4008155-6</a>]', '"Brennstoff"'),
        (r'"Energie" \\ Wärme', r'"\"Energie\" \\\\ Wärme"'),
        ('Brennstoff" OR type:Person OR "', '"Brennstoff\\" OR type:Person OR \\""'),
        ('{search}', '"{search}"'),
    ],
)
def test_keyword_query_template(provider, get, search, literal):
    get.return_value = response({'totalItems': 0, 'member': []})

    assert provider.get_options(None, search=search) == []
    assert get.call_args.kwargs['params'] == {
        'q': f'preferredName:{literal} OR variantName:{literal}',
        'format': 'json',
        'filter': 'type:SubjectHeading',
    }

    # Building one query must not change the configured template for subsequent requests.
    provider.get_options(None, search='Wärme')
    assert get.call_args.kwargs['params']['q'] == 'preferredName:"Wärme" OR variantName:"Wärme"'


@override_settings(GND_PARAMS={'filter': 'type:SubjectHeading'})
def test_keyword_filter_without_template(provider, get):
    get.return_value = response({'totalItems': 0, 'member': []})

    assert provider.get_options(None, search='Brennstoff') == []
    assert get.call_args.kwargs['params'] == {
        'q': 'Brennstoff',
        'format': 'json',
        'filter': 'type:SubjectHeading',
    }


@override_settings(GND_PARAMS={'q': 'type:SubjectHeading'})
def test_static_query(provider, get):
    get.return_value = response({'totalItems': 0, 'member': []})

    assert provider.get_options(None, search='Brennstoff') == []
    assert get.call_args.kwargs['params']['q'] == 'type:SubjectHeading'


def test_placeholder_in_default_search(provider, get):
    get.return_value = response({'totalItems': 0, 'member': []})

    assert provider.get_options(None, search='{search}') == []
    assert get.call_args.kwargs['params']['q'] == '{search}'


@pytest.mark.parametrize('search', [None, '', '  ', 'm', ' mo ', 'mo [<a href="example">id</a>]'])
def test_short_and_blank_searches_do_not_access_cache_or_lobid(settings, mocker, provider, search, http_get):
    settings.GND_SEARCH_MIN_LEN = 3
    get = mocker.patch.object(caches['default'], 'get')
    assert provider.get_options(None, search=search) == []
    get.assert_not_called()
    http_get.assert_not_called()


def test_default_minimum_preserves_one_character_searches(provider, http_get):
    assert provider.get_options(None, search='m')
    http_get.assert_called_once()


def test_saved_label_is_normalized_without_changing_query_syntax(provider, http_get):
    search = provider.get_text(record())
    options = provider.get_options(None, search=search)
    assert options == [{'id': '2129905-5', 'text': search}]
    assert http_get.call_args.kwargs['params']['q'] == record()['preferredName']


@pytest.mark.parametrize(
    'preferred_name',
    [
        'Research & Development',
        '<b>Example label</b>',
        'Literal &amp; expression',
        'L\'étude "example"',
        'x &lt; y',
    ],
)
def test_label_text_is_escaped_and_restored_for_search(provider, preferred_name, http_get):
    occupation = '<i>Chemistry & "physics"</i>'
    item = {
        **record(),
        'preferredName': preferred_name,
        'professionOrOccupation': [{'label': occupation}],
    }
    http_get.return_value = response({'totalItems': 1, 'member': [item]})
    options = provider.get_options(None, search='example')
    text = options[0]['text']
    label = ElementTree.fromstring(f'<span>{text}</span>')
    assert [element.tag for element in label.iter()] == ['span', 'a']
    assert ''.join(label.itertext()) == f'{preferred_name} | {occupation} [{item["gndIdentifier"]}]'
    assert provider.get_search(text) == preferred_name

    provider.get_options(None, search=text)
    assert http_get.call_args.kwargs['params']['q'] == preferred_name


@pytest.mark.parametrize(
    'search',
    [
        'Research & Development',
        'Research &amp; Development',
        'x &lt; y',
        'Literal &#39; expression',
    ],
)
def test_typed_search_preserves_literal_entities(provider, search, http_get):
    provider.get_options(None, search=search)
    assert http_get.call_args.kwargs['params']['q'] == search


@pytest.mark.parametrize('search', ['Zeolite', '2129905-5'])
def test_link_target_is_rendered_from_settings_without_changing_cached_results(settings, provider, search, http_get):
    if search == '2129905-5':
        http_get.return_value = response(record())

    first = provider.get_options(None, search=search)
    first_link = ElementTree.fromstring(f'<span>{first[0]["text"]}</span>').find('a')
    assert first_link.attrib == {
        'href': record()['id'],
        'target': '_blank',
        'rel': 'noopener noreferrer',
    }
    assert first_link.text == record()['gndIdentifier']

    settings.GND_PROVIDER_LINK_TARGET = '_self'
    second = provider.get_options(None, search=search)
    second_link = ElementTree.fromstring(f'<span>{second[0]["text"]}</span>').find('a')
    assert second_link.get('target') == '_self'

    settings.GND_PROVIDER_LINK_TARGET = None
    third = provider.get_options(None, search=search)
    third_link = ElementTree.fromstring(f'<span>{third[0]["text"]}</span>').find('a')
    assert third_link.attrib == {'href': record()['id']}
    assert first[0]['id'] == second[0]['id'] == third[0]['id'] == record()['gndIdentifier']
    assert provider.get_search(first[0]['text']) == provider.get_search(third[0]['text']) == record()['preferredName']
    http_get.assert_called_once()


@pytest.mark.parametrize(
    'occupations',
    [
        None,
        [],
        [{}],
        [None],
        {'label': 'occupation'},
        [{'label': None}],
        [{'label': 1}],
    ],
)
def test_optional_occupations(provider, occupations):
    text = provider.get_text({**record(), 'professionOrOccupation': occupations})
    label = ElementTree.fromstring(f'<span>{text}</span>')
    assert ''.join(label.itertext()) == f'{record()["preferredName"]} [{record()["gndIdentifier"]}]'
    assert provider.get_search(text) == record()['preferredName']


def test_saved_occupation_labels(provider):
    item = {**record(), 'professionOrOccupation': [{'label': 'Chemist'}]}
    occupation_label = provider.get_text(item)
    assert ' | Chemist [' in occupation_label
    assert provider.get_search(occupation_label) == record()['preferredName']


def test_identifier_restoration_bypasses_keyword_length_and_uses_record_cache(settings, provider, http_get):
    settings.GND_SEARCH_MIN_LEN = 20
    http_get.return_value = response(record())
    for identifier in ('2129905-5', record()['id']):
        assert provider.get_options(None, search=identifier) == [
            {
                'id': '2129905-5',
                'text': provider.get_text(record()),
            }
        ]
    http_get.assert_called_once()


def test_upstream_failure_returns_empty_options(provider, http_get, caplog):
    http_get.return_value = response({'status': 500, 'requestId': 'test-failure'}, status=500)
    assert_error_options(provider.get_options(None, search='Zeolite'))
    assert 'HTTP 500' in caplog.text
