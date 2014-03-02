# solr-geoplanet

The long version: http://www.aaronland.info/weblog/2009/12/21/redacted/#woelr

## IMPORTANT

_THIS REPOSITORY IS OFFICIALLY DEPRECATED._

It will still work if you've got an old version of Solr 3.1 but all current development is now being on the [woedb-solr](https://github.com/straup/woedb-solr) repository.

--

This assumes you're using Solr in "multiple core" mode. If you're not sure what
that means, start here:

	http://wiki.apache.org/solr/CoreAdmin

In solr/solr.xml add the following to <cores> :

	<core name="geoplanet" instanceDir="solr-geoplanet">
		<property name="dataDir" value="solr-geoplanet/data" />
	</core>

--

To start Solr:

	# Note the extra RAM-iness; 128MB is not enough to make the faceting
	# love

	$> cd /path/to/solr
	$> java -Dsolr.solr.home=. -Xmx256m -jar start.jar

--

Importing GeoPlanet data:

	# Fetch the geoplanet data dump you want to work with:

	$> wget http://developer.yahoo.com/geo/geoplanet/data/getLatest.php

	# Next we import the aliases and adjacencies in to a temporary SQLite
        # database because there's just too much data to read it all in to
        # memory (at the same time that Solr is gobbling resources to update its
        # indexes) and too slow to read it all from disk for every WOE ID.

	# Where x.y.z is the version number of the geoplanet data dump you're
        # importing

	$> sqlite3 geoplanet_sqlite_x.y.z.db

	# Set up your tables

	sqlite> CREATE TABLE geoplanet_aliases (woeid INTEGER, name TEXT, type TEXT, lang TEXT);
	sqlite> CREATE INDEX aliases_by_woeid ON geoplanet_aliases (woeid);

	sqlite> CREATE TABLE geoplanet_adjacencies (woeid INTEGER, iso TEXT, neighbour INTEGER, neighbour_iso TEXT);
	sqlite> CREATE INDEX adjacencies_by_woeid ON geoplanet_adjacencies (woeid);

	# Note the ".mode tabs" -iness that we need to set to import the
        # tab-delimited geoplanet files

	sqlite> .mode tabs
	sqlite> .import geoplanet_adjacencies_x.y.z.tsv geoplanet_adjacencies
	sqlite> .import geoplanet_aliases_x.y.z.tsv geoplanet_aliases

	# Remove the first entry from each table because it will just be the
	# column headers and not any actual data. If there's a better way to do
	# this, please let me know. I got bored of looking.

	sqlite> DELETE FROM geoplanet_adjacencies WHERE woeid='Place_WOE_ID'
	sqlite> DELETE FROM geoplanet_aliases WHERE woeid='WOE_ID'

	# The changes file:

	# Recent versions of the geoplanet dumps ship with a 'geoplanet_changes'
	# file indicating which WOE IDs have been superceded by a newer WOE ID.

	# The import.py script (below) will check for the presence of a
	# geoplanet_changes table in your SQLite database and if it's there use
	# it to populate the 'supercedes_woeid' (multivalue) field for each
	# location. It will also update each WOE ID that has been replaced and
	# populate the 'superceded_by' field. If that WOE ID is not present in
	# the geoplanet dump then a stub record will be created consisting of
	# just the 'woeid' and 'superceded_by' fields. Like this:

	# http://localhost:8983/solr/geoplanet/select?q=woeid:10333

	<doc>
		<int name="supercededby_woeid">12696199</int>
		<int name="woeid">10333</int>
	</doc>

	# The setup is basically the same as above, although the changes file
        # for version 7.4.0 appears to have a typo (spaces instead of tabs) in
        # the column header that prevent it from being read by SQLite. Honestly,
        # the easiest thing is just to open the file in a text editor and delete
        # the first line. Then it's just more of the same:

	sqlite> CREATE TABLE geoplanet_changes (woeid INTEGER, replacedby_woeid INTEGER, version TEXT);
	sqlite> CREATE INDEX changes_by_replacement ON geoplanet_changes (replacedby_woeid);
	sqlite> CREATE INDEX changes_by_woeid ON geoplanet_changes (woeid);
	sqlite> .import geoplanet_changes_x.y.z.tsv geoplanet_changes

	# Save to disk. Finally.

	sqlite> .quit

	# Now run the import.py program. Pass the --purge flag to re-feed Solr
        # from scratch. For example:

	# The code assumes that you've just unzipped a geoplanet data dump with
	# the standard x.y.z version names in the --data dir

	$> python import.py \
		--solr 'http://localhost:8983/solr/geoplanet' \
		--data /path/to/geoplanet-7.3.2 \
		--version '7.3.2' \
		--purge

	$> python import.py \
		--solr 'http://localhost:8983/solr/geoplanet' \
		--data /path/to/geoplanet-7.4.0 \
		--version '7.4.0'

--

Importing the Flickr public shapefiles dataset:

	# See also: http://code.flickr.com/blog/2009/05/21/flickr-shapefiles-public-dataset-10/

	$> wget http://www.flickr.com/services/shapefiles/1.0/

	# unzip the file

	$> python import_flickr_shapefiles.py \
		--solr http://localhost:8983/solr/geoplanet \
		--flickr /path/to/flickr_shapefiles_public_dataset_1.0.1.xml \
