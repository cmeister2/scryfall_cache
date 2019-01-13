#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `scryfall_cache` package."""

import os
import pytest
import scryfall_cache


# Have to define the scryfall cache at the session scope - there can be only
# one otherwise Pony gets a bit upset.
@pytest.fixture(scope="session")
def scrycache():
    """
    Create a test session scope ScryfallCache.

    Returns:
        scryfall_cache.ScryfallCache: cache object.

    """
    return scryfall_cache.ScryfallCache(application="scryfall_tests")


def test_query_mtgo_id(scrycache):
    """
    Test querying for an MTGO ID.

    Args:
        scrycache: The cache under test

    """
    card = scrycache.get_card(mtgo_id=12345)

    # Verify that card 12345 is 6875ce99-badd-44da-8e5d-509600efa1d0
    assert card.get_id() == "6875ce99-badd-44da-8e5d-509600efa1d0"


def test_card_images(scrycache):
    """Test card images.

    Args:
        scrycache: The cache under test

    """
    card = scrycache.get_card(mtgo_id=12345)
    path = card.get_image_path("png")
    print(path)

    # Verify that the path is as we expect
    cache_path = os.path.join("png", "6875ce99-badd-44da-8e5d-509600efa1d0.png")
    assert path.endswith(cache_path)

    # Now try an art_crop.
    crop_path = card.get_image_path("art_crop")
    print(crop_path)

    cache_path = os.path.join("art_crop", "6875ce99-badd-44da-8e5d-509600efa1d0.jpg")
    assert crop_path.endswith(cache_path)


def test_query_name(scrycache):
    """
    Test querying for a name.

    Args:
        scrycache: The cache under test

    """
    card = scrycache.get_card(name="Black Lotus")
    assert card.get_name() == "Black Lotus"


def test_mtgo_foil(scrycache):
    """
    Explicitly get card 31156 on MTGO.

    This is a foil Swamp. We should be able to match 31156 to that card object.

    Args:
        scrycache: The cache under test.

    """
    card = scrycache.get_card(mtgo_id=31156)
    assert card.get_name() == "Swamp"
