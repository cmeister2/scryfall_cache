# scryfall-cache


[![pypi version](https://img.shields.io/pypi/v/scryfall_cache.svg)](https://pypi.python.org/pypi/scryfall_cache)
[![Travis Status](https://img.shields.io/travis/cmeister2/scryfall_cache.svg)](https://travis-ci.org/cmeister2/scryfall_cache)
[![Documentation Status](https://readthedocs.org/projects/scryfall-cache/badge/?version=latest)](https://scryfall-cache.readthedocs.io/en/latest/?badge=latest)


Scryfall Cache is a library which minimizes the number of requests made to the Scryfall API.


- Free software: MIT license
- Documentation: https://scryfall-cache.readthedocs.io.


## Example

    >>> from scryfall_cache import ScryfallCache, ScryfallCacheException
    >>> import os

    >>> cache = ScryfallCache(application="scryfall_tests")

    >>> card = cache.get_card(mtgo_id=12345)
    >>> str(card)
    'ScryfallCard[Phyrexian Processor @ 6875ce99-badd-44da-8e5d-509600efa1d0]'

    >>> # Download the card image as a PNG.
    >>> image_path = card.get_image_path("png")
    >>> os.path.basename(image_path)
    '6875ce99-badd-44da-8e5d-509600efa1d0.png'

    >>> card_two = cache.get_card(name="Black Lotus")
    >>> str(card_two)
    'ScryfallCard[Black Lotus @ bd8fa327-dd41-4737-8f19-2cf5eb1f7cdd]'

## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [cmeister2/cookiecutter-pypackage](https://github.com/cmeister2/cookiecutter-pypackage) project template.
