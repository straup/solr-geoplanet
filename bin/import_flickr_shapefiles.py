#!/usr/bin/env python

import xml.sax
from shapely.geometry import Polygon, MultiPolygon
import pysolr

import sys
import optparse

#

parser = optparse.OptionParser()
parser.add_option("-s", "--solr", dest="solr", help="...")
parser.add_option("-f", "--flickr", dest="flickr", help="...")

(opts, args) = parser.parse_args()

#

class docHandler(xml.sax.ContentHandler):

        def __init__ (self, solr) :
		xml.sax.ContentHandler.__init__(self)

                self.solr = solr
                self.docs = []
                
        	self.current_woeid = None

		self.polyline_idx = None
                self.polylines = []
		self.shapedata = u''
        	self.bbox = u''
                
                self.record = False
        	self.total = 0
                
	def startDocument(self) :
                pass
                
	def startElement(self, name, attrs) :
                
                if name == 'place' :
                        self.current_woeid = attrs['woe_id']

		# only grab the most recent shapefile
                
                if name == 'shape' and not self.shapedata :
                        self.record = True

                if name == 'polylines' and self.record :
                        self.bbox = attrs['bbox']

                if name == 'polyline' and self.record :

                        if self.polyline_idx :
                                self.polyline_idx += 1
                        else :
                                self.polyline_idx = 0
                                
        def endElement(self, name) :

                if name == 'place' :

			self.total += 1

                        try :
				self.update()
                        except Exception, e :
                                print "failed to update %s: %s" % (self.current_woeid, e)
                        
                        self.polyline_idx = None
                        self.polylines = []
			self.shapedata = u''
                        self.bbox = u''
                        
                        self.current_woeid = None
                        
                if name == 'shape' and self.record == True :
                        self.record = False

		if name == 'polyline' and self.record == True :

                        self.polylines.append(self.shapedata)
                        self.shapedata = u''
                        
        def characters(self, str) :

		str = str.strip()

                if str == '' :
                        return
                
                if not self.record :
                        return

                self.shapedata += str

	def update (self) :

		count = len(self.polylines)

                if count == 0 :
                	print "WOE ID %s has no polylines!" % self.current_woeid
                        return False
                
                elif len(self.polylines) == 1 :
			coords = []

                	for pair in self.polylines[0].split(' ') :
                        	lat, lon = pair.split(',')
                		coords.append((float(lon), float(lat)))
                        
			coords.append(coords[0])

                	try :
                		poly = Polygon(coords)
                	except Exception, e :
                        	print "failed to generate poly for %s : %s" % (self.current_woeid, e)
                        	return False
                else :

			coords = []
                        
                        for p in self.polylines :
				shell = []
				holes = []
                                
                		for pair in p.split(' ') :
                        		lat, lon = pair.split(',')
                			shell.append((float(lon), float(lat)))
                        
				shell.append(shell[0])
                        	coords.append((tuple(shell), holes))

                        try :
                             	poly = MultiPolygon(coords)
                	except Exception, e :                                
                        	print "failed to generate multi poly for %s : %s" % (self.current_woeid, e)
				return False                             

                #
                
		centroid = poly.centroid
		area = poly.area
                
                lat = centroid.y
                lon = centroid.x

                swlat,swlon,nelat,nelon = map(lambda i: float(i), self.bbox.split(','))

		#
                
                res = self.solr.search("woeid:%s" % self.current_woeid)

                if res.hits == 0 :
                        return False

                doc = res.docs[0]
                
                doc['latitude'] = lat
                doc['longitude'] = lon                
		doc['area'] = area
                
                doc['sw_latitude'] = swlat
                doc['sw_longitude'] = swlon                
                doc['ne_latitude'] = nelat
                doc['ne_longitude'] = nelon                

                self.docs.append(doc)

                if len(self.docs) >= 500 :
                        self.send_updates()
                        
                return True

        def send_updates (self) :
                self.solr.add(self.docs)
                self.docs = []
                
solr = pysolr.Solr(opts.solr)

handler = docHandler(solr)
xml.sax.parse(open(opts.flickr, 'r'), handler)

sys.exit()

print "optimizing"
solr.optimize()

print "- done -"
