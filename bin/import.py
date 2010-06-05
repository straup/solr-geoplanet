#!/usr/bin/env python

import sqlite3

import pysolr
import codecs
import os.path
import sys
import time
import types

try:
	import json
except Exception, e:
	import simplejson as json

import optparse

#

parser = optparse.OptionParser()
parser.add_option("-s", "--solr", dest="solr", help="...")
parser.add_option("-d", "--data", dest="data", help="...")
parser.add_option("-e", "--extrasdb", dest="extrasdb", help="...")
parser.add_option("-v", "--version", dest="version", help="...")

parser.add_option("-S", "--spatial-solr", dest="spatial_solr", help="...", default=False, action='store_true')
parser.add_option("-P", "--purge", dest="purge", help="...", default=False, action='store_true')

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

if opts.extrasdb:

	woe_conn = sqlite3.connect(opts.extrasdb)
	woe_db = woe_conn.cursor()

#

solr = pysolr.Solr(opts.solr)

if opts.purge :
	print "purging..."
	solr.delete(q='*:*')

docs = []
total = 0

total_updates = 0
count_updates = 0

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
                        old_woeid, new_woeid, version = row
			print "changes where old WOE ID is %s: %s" % (old_woeid, new_woeid)
                        doc['supercededby_woeid'] = new_woeid

		res = db.execute("SELECT * FROM geoplanet_changes WHERE replacedby_woeid=%s" % addslashes(woeid))

		for row in res :
			old_woeid, new_woeid, that_version = row

			print "%s replaced by %s" % (old_woeid, new_woeid)

			if not doc.has_key('supercedes_woeid') :
				doc['supercedes_woeid'] = []

			# CHECK ME: supercedes_woeid is not being set correctly in the new record
			# it could just be that this was indented incorrectly...

			doc['supercedes_woeid'].append(old_woeid)

			# print doc

			# do we have a record for this (that) woe id?

			res = solr.search("woeid:%s" % old_woeid)

			if res.hits == 0 :
				that_provider = "geoplanet %s" % that_version
				docs.append({'woeid' : old_woeid, 'supercededby_woeid' : new_woeid, 'provider' : unicode(that_provider) })
			else:
				old_doc = res.docs[0]
				old_doc['supercededby_woeid'] = new_woeid

				print old_doc
				docs.append(old_doc)

	# WOE extras

	if woe_db:

		row = None

		woe_db.execute("SELECT * FROM woeids WHERE woeid=%s" % woeid)
		row = woe_db.fetchone()

		if row:
			data = json.loads(row[1])

			names = []

			for prop in ('locality1', 'locality2', 'admin1', 'admin2', 'admin3', 'country'):

				if not data.has_key(prop):
					continue

				if not data[prop]:
					continue

				if not data[prop].has_key('content'):
					continue

				if data[prop]['content']:
					names.append(data[prop]['content'])

			doc['fullname'] = ', '.join(names)

			# print "hname: %s" % doc['hierarchy_name']
			# print json.dumps(data, indent=4)

			lat = float(data['centroid']['latitude'])
			lon = float(data['centroid']['longitude'])

			ne = data['boundingBox']['northEast']
			sw = data['boundingBox']['southWest']

			swlat = float(sw['latitude'])
			swlon = float(sw['longitude'])

			nelat = float(ne['latitude'])
			nelon = float(ne['longitude'])

			# doc['geohash'] = Geohash.encode(lat,lon)

			if opts.spatial_solr:
				doc['centroid'] = '%s,%s' % (lat,lon)
				doc['bbox'] = '%s,%s,%s,%s' % (swlat,swlon,nelat,nelon)
			else:
				doc['latitude'] = lat
				doc['longitude'] = lon

				doc['sw_latitude'] = swlat
				doc['sw_longitude'] = swlon

				doc['ne_latitude'] = nelat
				doc['ne_longitude'] = nelon

	# has changes?

	has_changes_row = False

	if opts.purge:
		has_changes_row = True
	else:
		rsp = solr.search(q='woeid:%s' % doc['woeid'])

		if rsp.hits != 1:
			has_changes_row = True
		else:
			current = rsp.docs[0]

			# print doc
			# print current
			# sys.exit()

			for k,v in current.items():

				if k in ('date_indexed', 'provider'):
					continue

				if not doc.has_key(k):
					# print 'doc missing key: %s' % k
					has_changes_row = True
					break

				doc_v = doc[k]

				if type(doc_v) == types.DictType:
					doc_v = doc_v['value']
				elif type(doc_v) == types.ListType and len(doc_v) > 0:
					if type(doc_v[0]) == types.DictType:
						tmp = []
						for d in doc_v:
							tmp.append(d['value'])
						doc_v = tmp

					doc_v.sort()
					doc_v = map(unicode, doc_v)
					doc_v = ':'.join(doc_v)
				else:
					pass

				if type(v) == types.ListType:
					v.sort()
					v = map(unicode, v)
					v = ':'.join(v)

				if doc_v != v:
					# print "value mismatch for key: %s (doc: %s current: %s)" % (k, doc_v, v)
					has_changes_row = True
					break
				else:
					pass

			if not has_changes_row:
				for k, v in doc.items():

					if not current.has_key(k):
						# print 'current is missing key %s' % k
						has_changes_row = True
						break

	#

	if has_changes_row:
		docs.append(doc)

	#

	count_docs = len(docs)

	if count_docs >= 1000 :
		tries = 0

		tts = 10

		while tries < 4:

			try:
				solr.add(docs, True)
				docs = []

				count_updates += count_docs
				total_updates += count_docs

				print "added %s docs (%s total)" % (count_docs, total_updates)
				break
			except Exception, e:
				print "failed to index: %s (sleeping %s seconds)" % (e, tts)
				time.sleep(tts)
				tries += 1
				tts += (tts / 2)

	if count_updates >= 150000:
		print "resting"
		time.sleep(10)
		count_updates = 0

print "closing db"
conn.close()

print "optimizing"
solr.optimize()

print "- done -"
