# -*- coding: utf-8 -*-
"""Classes for main Scryfall cache objects."""

import logging
import os
import shutil
import time

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

import appdirs
from pony import orm
import requests
from requests_ratelimit_adapter import HTTPRateLimitAdapter


log = logging.getLogger(__name__)


# Module information
__version__ = "0.2.0"
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
        self,
        application=None,
        version=None,
        bulk_update_period=TWELVE_WEEKS,
        sql_debug=False,
    ):
        """Construct a ScryfallCache object.

        Args:
            application (str): Name of application to use for cached data.
            version (str): Version string of application. If None, no version is used.
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
        self.app = appdirs.AppDirs(package, application, version=version)

        # If the cache folders do not exist, make them.
        if not os.path.isdir(self.app.user_data_dir):
            os.makedirs(self.app.user_data_dir)

        # Get the local database.
        self.database_path = os.path.join(
            self.app.user_data_dir, self.DATABASE_FILENAME
        )

        log.debug("Scryfall database path: %s", self.database_path)

        # Create the database if it doesn't exist.
        db.bind(provider="sqlite", filename=self.database_path, create_db=True)

        # Create database tables if necessary.
        try:
            orm.set_sql_debug(sql_debug)
            db.generate_mapping(create_tables=True)

        except orm.dbapiprovider.OperationalError as e:
            # There was a problem when checking the database. Drop the tables (with
            # all data) and recreate the tables. This is currently our fix for
            # schema migration while Pony does not support migration.
            log.warning(
                "Hit problem while checking database. "
                "Recreating tables to attempt recovery."
            )
            log.debug("Dropping tables")
            db.drop_all_tables(with_all_data=True)

            log.debug("Creating tables")
            db.create_tables()

        # Check the database for an update.
        self._check_database()

    def get_cache_directory(self):
        """
        Get the top level cache directory that this instance is using.

        Useful for other libraries if they want to store data in
        ScryfallCache's cache folder.

        Returns:
            str: the cache directory path.

        """
        return self.app.user_data_dir

    def get_card(self, name=None, scryfall_id=None, mtgo_id=None):
        """
        Attempt to get a ScryfallCard object for any given identifiers.

        Args:
            name (str): The name of the card if known.
            scryfall_id (str): The Scryfall ID of the card if known.
            mtgo_id (int): The MTGO ID of the card if known.

        Raises:
            ScryfallCacheException: if no identifiers are given.

        Returns:
            ScryfallCard if ID found, else None.

        """
        if name is not None:
            card_dict = self._card_from_name(name)
        elif scryfall_id is not None:
            card_dict = self._card_from_id(scryfall_id)
        elif mtgo_id is not None:
            card_dict = self._card_from_mtgo_id(mtgo_id)
        else:
            raise ScryfallCacheException("Require at least one identifier to query on")

        # Check the card dictionary.
        if not card_dict:
            return None

        # Found a card dictionary containing all the necessary information.
        # Pass a ScryfallCard back to the user.
        return ScryfallCard(self, card_dict)

    def _card_from_id(self, scryfall_id):
        """Request a card data dictionary by Scryfall ID.

        Args:
            scryfall_id(str): The Scryfall ID of the card.

        Returns:
            Dictionary of card data if card is found, else None.

        """
        with orm.db_session:
            # This is safe because id is a primary key, so there should be 0
            # or 1 entries.
            result = Card.get(id=scryfall_id)

        if result:
            card_json = result.data
        else:
            log.debug("Card not found in database: %s", scryfall_id)

            # Query the API for what Scryfall thinks is correct.
            card_json = self._query_scryfall(
                "https://api.scryfall.com/cards/{scryfall_id}".format(
                    scryfall_id=scryfall_id
                ),
                timeout=ONE_DAY,
            )

            if card_json:
                # Save this card for future as it wasn't found first time.
                self._save_card(card_json)

        return card_json

    def _card_from_name(self, name):
        """Request a card dictionary by name.

        Args:
            name (str): The name of the card.

        Returns:
            Dictionary of card data if card is found, else None.

        """
        with orm.db_session:
            results = orm.select(c for c in Card if c.name == name)
            if not results:
                results = []

            cards_json = [m.data for m in results]

        if len(cards_json) == 1:
            log.debug("Returning single result for name %s", name)
            card_json = cards_json[0]

        else:
            log.debug("Got %d results for name %s", len(cards_json), name)

            # Encode the URL parameters.
            params = urlencode({"exact": name})

            # Query the API for what Scryfall thinks is correct.
            card_json = self._query_scryfall(
                "https://api.scryfall.com/cards/named?{params}".format(params=params),
                timeout=ONE_DAY,
            )

            if card_json and len(cards_json) == 0:
                # Save this card for future as no cards were found first time.
                self._save_card(card_json)

        return card_json

    def _card_from_mtgo_id(self, mtgo_id):
        """Request a card dictionary by MTGO ID.

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

            if card_json and len(cards_json) == 0:
                # Save this card for future as no cards were found first time.
                self._save_card(card_json)

        return card_json

    def _save_card(self, card_data):
        # Insert this into the database.
        with orm.db_session:
            log.debug("Saving card information to database for %s", card_data["id"])
            Card(
                id=card_data["id"],
                name=card_data["name"],
                mtgo_id=card_data.get("mtgo_id", None),
                data=card_data,
            )

    def _check_database(self):
        with orm.db_session:
            metadata = orm.select(m for m in Metadata).first()

            if not metadata:
                # Create a new metadata object. Record the version of ScryfallCache
                # that we're using here, so we can migrate later.
                metadata = Metadata(lastupdate=0, version=__version__)

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
                # Create the card.
                Card(
                    id=card_obj["id"],
                    name=card_obj["name"],
                    mtgo_id=card_obj.get("mtgo_id", None),
                    data=card_obj,
                )

        log.debug("Finished bulk card insertion")

        # Update the metadata to store the latest timestamp
        self._update_metadata()

    def _update_metadata(self):
        with orm.db_session:
            metadata = orm.select(m for m in Metadata).first()

            # Update the timestamp
            metadata.lastupdate = int(time.time())
            log.debug("Updated metadata: last update now %d", metadata.lastupdate)

    def _download_scryfall_to_file(self, url, target_path):
        tmp_file = "{0}._scry".format(target_path)
        log.debug("Downloading %s to %s", url, tmp_file)

        req = self.session.get(url, stream=True)
        req.raise_for_status()

        with open(tmp_file, "wb") as f:
            for chunk in req.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        log.debug("Downloaded %s to %s", url, tmp_file)

        # Move the temporary file to the new destination.
        shutil.move(tmp_file, target_path)
        log.debug("Moved temporary download file %s to %s", tmp_file, target_path)

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

    def get_local_image_path(self, card, art_format):
        """Retrieve the local image path for a given image.

        If necessary, download the image into place before returning.

        Args:
            card (ScryfallCard): ScryfallCard object returned from get_card().
            art_format (str): One of the art formats to download. See
                https://scryfall.com/docs/api/images for more detail.

        Raises:
            ScryfallCacheException: on failure

        Returns:
            str: the file path

        """
        card_data = card.get_dict()

        if "image_uris" not in card_data:
            log.error("[%s] No images found", card)
            raise ScryfallCacheException("No images found")

        if art_format not in card_data["image_uris"]:
            log.error("[%s] Format %r not found", card, art_format)
            raise ScryfallCacheException("Art format {0} not found".format(art_format))

        uri = card_data["image_uris"][art_format]
        log.debug("[%s] Image URI for %r: %s", card, art_format, uri)

        # Create the folders necessary to store this image.
        art_cache_path = os.path.join(self.app.user_data_dir, "art_cache", art_format)

        if not os.path.isdir(art_cache_path):
            os.makedirs(art_cache_path)

        # Determine the extension.  As per the API, everything is a JPG except PNG.
        if art_format == "png":
            extension = "png"
        else:
            extension = "jpg"

        local_path = os.path.join(
            art_cache_path,
            "{id}.{extension}".format(id=card.get_id(), extension=extension),
        )
        log.debug("[%s] Local image path for %s: %s", card, art_format, local_path)

        if not os.path.exists(local_path):
            # Need to download that image!
            self._download_scryfall_to_file(uri, local_path)

        return local_path


class ScryfallCard(object):
    """Wrapper object for a Scryfall card data dictionary."""

    def __init__(self, cache, card_dict):
        """
        Construct a ScryfallCard.

        Args:
            cache (ScryfallCache): reference to parent Cache object.
            card_dict (dict): Card data dictionary.
        """
        self._id = card_dict["id"]
        self._name = card_dict["name"]
        self._cache = cache
        self._card_dict = card_dict

    def __repr__(self):
        """
        Return a str representation of this object when it was constructed.

        Returns:
            str: A representation of this object when it was constructed.

        """
        return "{self.__class__.__name__}({self._cache!r}, {self._card_dict!r})".format(
            self=self
        )

    def __str__(self):
        """
        Return a useful str representation of this object.

        Returns:
            str: A useful representation of this object

        """
        return "{self.__class__.__name__}[{self._name} @ {self._id}]".format(self=self)

    def get_id(self):
        """
        Return the Scryfall ID for this card.

        Returns:
            str: The Scryfall ID for this card.

        """
        return self._id

    def get_name(self):
        """
        Return the name for this card.

        Returns:
            str: The name of this card.

        """
        return self._name

    def get_dict(self):
        """
        Return the card data dictionary for this card.

        Returns:
            dict: The card data dictionary for this card.

        """
        return self._card_dict

    def get_image_path(self, art_format):
        """
        Get or download the chosen art format for this card.

        Args:
            art_format (str): One of the art formats to download. See
                https://scryfall.com/docs/api/images for more detail.

        Returns:
            str: Path to local file.

        """
        return self._cache.get_local_image_path(self, art_format)


class Card(db.Entity):
    """Card database object as retrieved from Scryfall."""

    id = orm.PrimaryKey(str)
    name = orm.Required(str, index=True)
    mtgo_id = orm.Optional(int, index=True)
    data = orm.Required(orm.Json)


class Metadata(db.Entity):
    """Metadata about the cache."""

    lastupdate = orm.Required(int)
    version = orm.Required(str)


class ScryfallResultCache(db.Entity):
    """URL response retrieved from Scryfall."""

    url = orm.PrimaryKey(str)
    timestamp = orm.Required(int)
    data = orm.Required(orm.Json)
