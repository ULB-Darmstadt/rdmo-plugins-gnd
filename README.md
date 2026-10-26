rdmo-plugins-gnd
================

This plugin implements dynamic option set, that queries the API for the Gemeinsame Normdatei at https://lobid.org/gnd.

If you intend to use the API, please follow it's [usage policy](http://lobid.org/usage-policy/).


Setup
-----

Install the plugin in your RDMO virtual environment using pip (directly from GitHub):

```bash
pip install git+https://github.com/rdmorganiser/rdmo-plugins-gnd
```

Add the `rdmo_gnd` app to `INSTALLED_APPS` and the plugin to `OPTIONSET_PROVIDERS` in `config/settings/local.py`:

```python
INSTALLED_APPS += ['rdmo_gnd']

...

OPTIONSET_PROVIDERS += [
    ('gnd', _('GND Provider'), 'rdmo_gnd.providers.GNDProvider')
]
```

The option set provider should now be selectable for option sets in your RDMO installation. For a minimal example catalog, see the files in `xml`.

If a selection of a GND identifier should update other fields, you can add a `GND_PROVIDER_MAP` in your settings, e.g.:

```python
GND_PROVIDER_MAP = [
    {
        'gndIdentifier': 'https://rdmorganiser.github.io/terms/domain/project/coordination/gnd',
        'preferredName': 'https://rdmorganiser.github.io/terms/domain/project/coordination/name'
    }
]
```

In this case, a change to the identifier of a coordinator (`https://rdmorganiser.github.io/terms/domain/project/coordination/gnd`) will update their name (`https://rdmorganiser.github.io/terms/domain/project/coordination/name`) automatically. The value will be taken from the `preferredName` field of the response from the API for the selected `gndIdentifier`. `GND_PROVIDER_MAP` is a list of mappings, since multiple GND identifiers could be used and should update different other values.

Additional parameters can be provided using `GND_PARAMS`:

```python
GND_PARAMS = {
    'filter': '+(type:PlaceOrGeographicName)'
}
```

To search only for keywords (GND subject headings), use
`GND_PARAMS = {'filter': 'type:SubjectHeading'}`. This restricts the record type
while keeping the default search across all fields.

To also limit matching to preferred names and synonyms, configure a query template:

```python
GND_PARAMS = {
    'filter': 'type:SubjectHeading',
    'q': 'preferredName:{search} OR variantName:{search}',
}
```

The provider replaces every `{search}` placeholder with the search text as an
escaped, double-quoted phrase. For example, `Brennstoff` becomes
`preferredName:"Brennstoff" OR variantName:"Brennstoff"`. Do not add quotes around
the placeholder yourself. The `filter` is sent separately and remains fixed.
This uses [lobid's field and phrase search syntax](https://github.com/hbz/lobid/blob/master/doc/lobid-gnd.md#gleichzeitige-suche-in-ansetzungs--und-verweisungsformen).
A `q` value without `{search}` continues to be sent unchanged as a static query.
These settings apply to every option set using `GNDProvider`.

[lobid's policy](http://lobid.org/usage-policy/) asks to add a custom `User-Agent` to your requests so that they can perform statistical analyses and, if you add an email address, might contact you. This can be done by adding the following to your settings.

```python
GND_PROVIDER_HEADERS = {
    'User-Agent': 'Mein Projekt; mailto:meinprojekt@example.org'
}
```

If the GND search service cannot be reached, returns an HTTP error, or sends an invalid response,
the search dropdown shows "The GND service is currently unavailable. Please try again later."
This message cannot be selected as an answer. Details are logged through `rdmo_gnd.providers`.
The message follows the active RDMO language, with English and German translations included.
In German, it reads "Der GND-Dienst ist derzeit nicht verfügbar. Bitte versuchen Sie es später erneut."

Search requests use a timeout of 10 seconds. You can change it in your settings:

```python
GND_PROVIDER_TIMEOUT = 10
```
