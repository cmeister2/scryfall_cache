# -*- coding: utf-8 -*-
"""Classes for main Scryfall cache objects."""

import logging
import os
import time

import appdirs
from pony import orm
import requests
from requests_ratelimit_adapter import HTTPRateLimitAdapter


log = logging.getLogger(__name__)


# Module information
__version__ = "0.1.0"
__author__ = """Max Dymond"""
__email__ = "cmeister2@gmail.com"
package = "scryfall_cache"


# Define a rate limiter adapter for Scryfall.  The upper limit is 10 requests
# per second or 1 every 100ms.
ScryfallRateLimiter = HTTPRateLimitAdapter(calls=1, period=0.1)


# Define time periods in seconds
ONE_DAY = 24 * 60 * 60
TWELVE_WEEKS = 12 * 7 * ONE_DAY


# Database for Pony abstraction.
db = orm.Database()


class ScryfallCacheException(Exception):
    """Exception raised by ScryfallCache."""

    pass


class ScryfallCache(object):
    """Main cache object."""

    BULK_DATA_LIST = "default_cards"
    DATABASE_FILENAME = "scryfallcache.sqlite3"

    def __init__(
        self, application=None, bulk_update_period=TWELVE_WEEKS, sql_debug=False
    ):
        """Construct a ScryfallCache object.

        Args:
            application (str): Name of application to use for cached data.
            bulk_update_period (int): The period after which the cache is bulk-updated.
            sql_debug (bool): Whether SQL debug commands are shown.
        """
        self.bulk_update_period = bulk_update_period

        # Create a requests Session and mount the rate limiter to protect
        # Scryfall.
        self.session = requests.Session()
        self.session.mount("http://", ScryfallRateLimiter)
        self.session.mount("https://", ScryfallRateLimiter)

        # Create an Appdirs instance to find where the local cache should
        # be stored.
        self.app = appdirs.AppDirs(package, application, version=__version__)

        # If the application folders do not exist, make them.
        if not os.path.exists(self.app.user_data_dir):
            os.makedirs(self.app.user_data_dir)

        # Get the local database.
        self.database_path = os.path.join(
            self.app.user_data_dir, self.DATABASE_FILENAME
        )

        log.debug("Scryfall database path: %s", self.database_path)

        # Create the database if it doesn't exist.
        db.bind(provider="sqlite", filename=self.database_path, create_db=True)

        # Create database tables if necessary.
        orm.set_sql_debug(sql_debug)
        db.generate_mapping(create_tables=True)

        # Check the database for an update.
        self._check_database()

    def card_from_mtgo_id(self, mtgo_id):
        """Request card data by MTGO ID.

        Args:
            mtgo_id(int): The MTGO ID of the card.

        Returns:
            Dictionary of card data if card is found, else None.

        """
        with orm.db_session:
            results = orm.select(c for c in Card if c.mtgo_id == mtgo_id)
            if not results:
                results = []

            cards_json = [m.data for m in results]

        if len(cards_json) == 1:
            log.debug("Returning single result for MTGO ID %d", mtgo_id)
            card_json = cards_json[0]

        else:
            log.debug(
                "Expected 1 result for MTGO ID %d, got %d results instead",
                mtgo_id,
                len(cards_json),
            )

            # Query the API for what Scryfall thinks is correct.
            card_json = self._query_scryfall(
                "https://api.scryfall.com/cards/mtgo/{mtgo_id}".format(mtgo_id=mtgo_id),
                timeout=ONE_DAY,
            )

        return card_json

    def _check_database(self):
        with orm.db_session:
            metadata = orm.select(m for m in Metadata).first()

            if not metadata:
                metadata = Metadata(lastupdate=0)

        if metadata.lastupdate + self.bulk_update_period < time.time():
            log.debug(
                "Updating database due to aging out (%d)", self.bulk_update_period
            )
            self._bulk_update_database()

    def _bulk_clear_database(self):
        # We need to clear the database out. Delete all the cards in the database.
        with orm.db_session:
            orm.delete(c for c in Card)

    def _bulk_update_database(self):
        # Request the /bulkdata endpoint from Scryfall. Do not request this from cache.
        bulk_req = self.session.get("https://api.scryfall.com/bulk-data")
        bulk_req.raise_for_status()

        bulkdata = bulk_req.json()

        # Get the URI for the all_cards object.
        for obj in bulkdata["data"]:
            if obj["type"] == self.BULK_DATA_LIST:
                bulk_data_list_uri = obj["permalink_uri"]
                break
        else:
            raise ScryfallCacheException(
                "Failed to find {0}".format(self.BULK_DATA_LIST)
            )

        # Request the bulk data list from the URI we just queried.
        bulk_data_list_req = self.session.get(bulk_data_list_uri)
        bulk_data_list_req.raise_for_status()

        # Clear the database of cards.
        self._bulk_clear_database()

        # Insert the data into the database.
        log.debug("Starting bulk card insertion")

        with orm.db_session:
            for card_obj in bulk_data_list_req.json():
                mtgo_id = card_obj.get("mtgo_id", None)

                # Create the card.
                Card(id=card_obj["id"], mtgo_id=mtgo_id, data=card_obj)

        log.debug("Finished bulk card insertion")

        # Update the metadata to store the latest timestamp
        self._update_metadata()

    def _update_metadata(self):
        with orm.db_session:
            metadata = orm.select(m for m in Metadata).first()

            # Update the timestamp
            metadata.lastupdate = int(time.time())
            log.debug("Updated metadata: last update now %d", metadata.lastupdate)

    def _query_scryfall(self, url, timeout=ONE_DAY):
        with orm.db_session:
            result = ScryfallResultCache.get(url=url)

        now = int(time.time())

        if result and result.timestamp + timeout > now:
            log.debug("Found result in cache")
            return result.data

        # Query Scryfall.
        try:
            res = self.session.get(url)
            res.raise_for_status()

            # Convert the result to an object.
            card_data = res.json()

            # Store the result in the database.
            with orm.db_session:
                log.debug("Storing result for url %s at timestamp %d", url, now)
                ScryfallResultCache(url=url, timestamp=now, data=card_data)

            return card_data

        except requests.exceptions.RequestException:
            log.exception("Failed to find information from URL: %s", url)
            return None


class Card(db.Entity):
    """Card object as retrieved from Scryfall."""

    id = orm.PrimaryKey(str)
    mtgo_id = orm.Optional(int, index=True)
    data = orm.Required(orm.Json)


class Metadata(db.Entity):
    """Metadata about the cache information."""

    lastupdate = orm.Required(int)


class ScryfallResultCache(db.Entity):
    """URL response retrieved from Scryfall."""

    url = orm.PrimaryKey(str)
    timestamp = orm.Required(int)
    data = orm.Required(orm.Json)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        stream=sys.stdout, format="%(asctime)s %(message)s", level=logging.DEBUG
    )
    x = ScryfallCache("mynewapp")
