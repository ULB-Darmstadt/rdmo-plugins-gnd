import logging
import re

from django.conf import settings
from django.utils.translation import gettext as _

import requests

from rdmo.options.providers import Provider

logger = logging.getLogger(__name__)


class GNDProvider(Provider):
    search = True
    refresh = True

    def get_options(self, project, search=None, user=None, site=None):
        if search:
            url = getattr(settings, 'GND_PROVIDER_URL', 'https://lobid.org/gnd').rstrip('/')
            headers = getattr(settings, 'GND_PROVIDER_HEADERS', {})
            params = {
                'q': self.get_search(search),
                'format': 'json',
                **getattr(settings, 'GND_PARAMS', {}),
            }
            try:
                response = requests.get(
                    f'{url}/search',
                    params=params,
                    headers=headers,
                    timeout=getattr(settings, 'GND_PROVIDER_TIMEOUT', 10),
                )
                response.raise_for_status()
                data = response.json()
                if data['totalItems']:
                    return [{'id': item['gndIdentifier'], 'text': self.get_text(item)} for item in data['member']]
            except (requests.exceptions.RequestException, KeyError, TypeError, ValueError) as exc:
                logger.warning('GND search failed: %s', exc)
                # react-select displays this message but prevents it from being selected.
                return [
                    {
                        'id': '__gnd_request_error__',
                        'text': _('The GND service is currently unavailable. Please try again later.'),
                        'isDisabled': True,
                    }
                ]

        # return an empty list by default
        return []

    def get_text(self, item):
        gndId = item['id']
        gndIdentifier = item['gndIdentifier']
        gndIdentifierLink = f'<a href="{gndId}">{gndIdentifier}</a>'
        preferredName = item['preferredName']

        try:
            professionOrOccupation = item['professionOrOccupation'][0]['label']
        except (ValueError, KeyError, IndexError):
            professionOrOccupation = None

        if professionOrOccupation is None:
            return f'{preferredName} [{gndIdentifierLink}]'
        else:
            return f'{preferredName} | {professionOrOccupation} [{gndIdentifierLink}]'

    def get_search(self, search):
        # reverse get_text to perform the search, remove everything after | or [
        m = re.match(r'^[^|[]+', search)
        if m:
            return m[0].strip()
        else:
            return search
