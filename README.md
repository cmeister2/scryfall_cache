# scryfall-cache


[![pypi version](https://img.shields.io/pypi/v/scryfall_cache.svg)](https://pypi.python.org/pypi/scryfall_cache)
[![Travis Status](https://img.shields.io/travis/cmeister2/scryfall_cache.svg)](https://travis-ci.org/cmeister2/scryfall_cache)
[![Documentation Status](https://readthedocs.org/projects/scryfall-cache/badge/?version=latest)](https://scryfall-cache.readthedocs.io/en/latest/?badge=latest)


Scryfall Cache is a library which minimizes the number of requests made to the Scryfall API.


- Free software: MIT license
- Documentation: https://scryfall-cache.readthedocs.io.


## Example

## Example

    >>> from scryfall_cache import ScryfallCache

    >>> cache = ScryfallCache(application="scryfall_tests")

    >>> card = cache.card_from_mtgo_id(12345)
    >>> card["name"]
    'Phyrexian Processor'

    >>> card["id"]
    '6875ce99-badd-44da-8e5d-509600efa1d0'


## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [cmeister2/cookiecutter-pypackage](https://github.com/cmeister2/cookiecutter-pypackage) project template.
