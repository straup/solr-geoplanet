#!/usr/bin/env python

import sqlite3

import pysolr
import codecs
import os.path
import sys
import time

import simplejson as json

import optparse

#

parser = optparse.OptionParser()
parser.add_option("-s", "--solr", dest="solr", help="...")
parser.add_option("-d", "--data", dest="data", help="...")
parser.add_option("-e", "--extrasdb", dest="extrasdb", help="...")
parser.add_option("-v", "--version", dest="version", help="...")
parser.add_option("-P", "--purge", dest="purge", help="...", default=None, action='store_true')

(opts, args) = parser.parse_args()

#

provider = "geoplanet %s" % opts.version

#

gp_places = os.path.join(opts.data, 'geoplanet_places_%s.tsv' % opts.version)
gp_sqlite = os.path.join(opts.data, 'geoplanet_sqlite_%s.db' % opts.version)

for f in (gp_places, gp_sqlite) :
	if not os.path.exists(f) :
        	print "%s does not exist" % f
        	sys.exit()

woe_conn = None
woe_db = None

if options.extrasdb:

	woe_conn = sqlite3.connect(options.extrasdb)
	woe_db = woe_conn.cursor()

#

solr = pysolr.Solr(opts.solr)

if opts.purge :
	print "purging..."
	solr.delete(q='*:*')

docs = []
total = 0

has_changes = False

#

def addslashes(value):
	value = unicode(value)
	return value.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")

#

conn = sqlite3.connect(gp_sqlite)
db = conn.cursor()

#

try :
        res = db.execute("SELECT COUNT(woeid) FROM geoplanet_changes")

        if len(list(res)) > 0 :
                has_changes = True

except Exception, e :
        # print "ACK! %s" % e
        pass

#

for ln in codecs.open(gp_places, encoding='utf-8') :

        total += 1

	if total == 1 :
            	continue

	ln = ln.strip()

	woeid, iso, name, lang, placetype, parent = ln.split('\t')

        name = name.replace('"', '')
        iso = iso.replace('"', '')
        lang = lang.replace('"', '')
        woeid = int(woeid)

        doc = {'woeid' : int(woeid),
               'parent_woeid' : int(parent),
               'adjacent_woeid' : [],
               'placetype' : unicode(placetype),
               'name' : name,
               'names' : [ { 'value' : name, 'boost' : '1.5' } ],
               'iso' : unicode(iso),
               'lang' : unicode(lang),
	       'provider' : unicode(provider) }

	# aliases

	res = db.execute("SELECT * FROM geoplanet_aliases WHERE woeid=%s" % addslashes(woeid))

        for row in res :
                alias_woeid, alias_name, alias_type, alias_lang = row

        	alias_type = alias_type.replace('"', '')
        	alias_name = alias_name.replace('"', '')

		key = "alias_%s" % alias_lang

                if alias_type != '' :
                        key += "_%s" %alias_type

                if key.endswith('_V') :
                        doc[ key ] = { 'value' : alias_name, 'boost' : '0.5' }

                elif key.endswith('_N') :
                        doc[ key ] = { 'value' : alias_name, 'boost' : '2.0' }

                else :
                	doc[ key ] = alias_name

                doc[ 'names' ].append(alias_name)

	# adjacencies

	res = db.execute("SELECT * FROM geoplanet_adjacencies WHERE woeid=%s" % addslashes(woeid))

        for row in res :
                this_woeid, this_iso, neighbour_woeid, neighbour_iso = row
		doc[ 'adjacent_woeid'].append(int(neighbour_woeid))

	# superceded by

        if has_changes :

		res = db.execute("SELECT * FROM geoplanet_changes WHERE woeid=%s" % addslashes(woeid))

                for row in res :
                        this_woeid, that_woeid, version = row
                        doc['supercededby_woeid'] = that_woeid

		res = db.execute("SELECT * FROM geoplanet_changes WHERE replacedby_woeid=%s" % addslashes(woeid))

		for row in res :
			that_woeid, this_woeid, that_version = row

			# print "%s replaced by %s" % (that_woeid, this_woeid)

			if not doc.has_key('supercedes_woeid') :
				doc['supercedes_woeid'] = []

			# CHECK ME: supercedes_woeid is not being set correctly in the new record
			# it could just be that this was indented incorrectly...

			doc['supercedes_woeid'].append(that_woeid)

			# do we have a record for this (that) woe id?

			res = solr.search("woeid:%s" % that_woeid)

			if res.hits == 0 :
				that_provider = "geoplanet %s" % that_version
				docs.append({'woeid' : that_woeid, 'supercededby_woeid' : this_woeid, 'provider' : unicode(that_provider) })

	# WOE extras

	if woe_db:
		woe_db.execute("SELECT * FROM woeids WHERE woeid=%s" % woeid)
		row = woe_db.fetchone()

		if row:
			data = json.loads(row[1])

			lat = data['centroid']['latitude']
			lon = data['centroid']['longitude']

			ne = data['boundingBox']['northEast']
			sw = data['boundingBox']['southWest']

			swlat = sw['latitude']
			swlon = sw['longitude']

			nelat = sw['latitude']
			nelon = sw['longitude']

			doc['centroid'] = '%s,%s' % (lat,lon)
			doc['bbox'] = '%s,%s,%s,%s' % (swlat,swlon,nelat,nelon)

        # TO DO:
        # check to see if doc:woeid already exists
        # if it does, check to see if there are any
        # actual updates to apply.

        # for k, v in doc.items() :
        #        print "%s\t%s" % (k, v)

	docs.append(doc)

	#

	if len(docs) >= 1000 :
            	print total
		solr.add(docs, True)
        	docs = []

print "closing db"
conn.close()

print "optimizing"
solr.optimize()

print "- done -"
