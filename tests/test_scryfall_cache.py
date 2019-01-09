#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `scryfall_cache` package."""

import scryfall_cache


def test_query_mtgo_id():
    """Test querying for an MTGO ID."""
    sc = scryfall_cache.ScryfallCache(application="scryfall_tests")
    card = sc.card_from_mtgo_id(12345)

    # Verify that card 12345 is 6875ce99-badd-44da-8e5d-509600efa1d0
    assert card["id"] == "6875ce99-badd-44da-8e5d-509600efa1d0"
