import unicodedata
from math import radians, cos, sin, asin, atan2, tan, sqrt
import csv
import gc
import osmium
import sys
import os.path
from os import path

class Writer(osmium.SimpleHandler):
    crossings_file = None
    crossings_writer = None

    links_file = None
    links_writer = None

    nodes = {}
    nodes_appearances = {}
    new_nodes_id = {}
    nodes_used = set([])

    ways = True

    def __init__(self, nodes, new_nodes_id, nodes_appearances):
        osmium.SimpleHandler.__init__(self)
        self.new_node_id = 0
        self.new_way_id = 0
        self.nodes = nodes
        self.new_nodes_id = new_nodes_id
        self.nodes_appearances = nodes_appearances

        self.crossings_file = open('intersections.tsv', 'w', encoding='utf8',
                                   newline='\n')
        self.crossings_writer = csv.writer(self.crossings_file, delimiter='\t')
        self.crossings_writer.writerow(['id', 'name', 'x', 'y'])
        self.links_file = open('links.tsv', 'w', encoding='utf8', newline='\n')
        self.links_writer = csv.writer(self.links_file, delimiter='\t')
        self.links_writer.writerow(
            ['id', 'name', 'lanes', 'length', 'speed', 'capacity', 'function',
             'origin',
             'destination'])

    def way(self, w):
        self.write_way(w)

    def write_nodes(self):

        for n in self.nodes_used:
            node = self.nodes[n]
            id = self.new_nodes_id[n]
            name = node['name']
            x = node['lat']
            y = node['lon']

            self.crossings_writer.writerow([id, name, y, x])

    def write_way(self, way):

        if not self.is_highway(way.tags):
            return

        id = self.new_way_id
        name = id
        #Stores all the nodes the way goes through
        OD_list = []
        # Store all the nodes the way goes through, including those not part of an intersection
        OD_list_complete = []
        # TODO: Get length of road in Km
        length = 1
        # TODO: Estimate speed if not provided
        speed = None
        oneway = False
        # congestion function
        function = 2
        # TODO: Estimate number of lanes
        lanes = 1
        # TODO: Find capacity
        capacity = 3000

        for index in range(len(way.nodes)):
            if index == 0 or self.nodes_appearances[way.nodes[index].ref] > 1 or index == (len(way.nodes) - 1):
                OD_list.append(way.nodes[index].ref)

            OD_list_complete.append(way.nodes[index].ref)

        if 'maxpeed' in way.tags:
            speed = way.tags['maxspeed']

        if 'oneway' in way.tags and way.tags['oneway'] == 'yes':
            oneway = True

        if 'junction' in way.tags and way.tags['junction'] == 'roundabout':
            oneway = True

        if 'lanes' in way.tags:
            lanes = way.tags['lanes']

        if 'name' in way.tags:
            name = way.tags['name']
            name = name[:45] + '..'

        if 'addr:street' in way.tags:
            name = way.tags['addr:street']
            name = name[:45] + '..'

        if self.get_way_type(way.tags) is not None and speed is None:
            type = self.get_way_type(way.tags)
            if type is "D":
                speed = 80
            elif type is "N":
                speed = 110
            elif type is "A":
                speed = 130

        if speed is None:
            speed = 50

        for i in range(len(OD_list) - 1):
            length = 0
            index_o = OD_list_complete.index(OD_list[i])
            index_d = OD_list_complete.index(OD_list[i + 1])
            elements = OD_list_complete[index_o:index_d + 1]

            for j in range(len(elements) - 1):
                node1_long = float(self.nodes[elements[j]]['lon'])
                node1_lat = float(self.nodes[elements[j]]['lat'])
                node2_long = float(self.nodes[elements[j + 1]]['lon'])
                node2_lat = float(self.nodes[elements[j + 1]]['lat'])
                length += self.get_way_length(node1_long, node1_lat,
                                              node2_long, node2_lat)

            length = round(length, 3)
            # Link: ['id', 'name', 'lanes', 'length', 'speed', 'capacity', 'function', 'origin', 'destination']

            if OD_list[i] not in self.new_nodes_id:
                self.new_nodes_id.update({OD_list[i]: self.new_node_id})
                self.new_node_id += 1

            origin = self.new_nodes_id[OD_list[i]]

            if i == 0:
                self.nodes_used.add(OD_list[i])

            if OD_list[i + 1] not in self.new_nodes_id:
                self.new_nodes_id.update({OD_list[i + 1]: self.new_node_id})
                self.new_node_id += 1

            destination = self.new_nodes_id[OD_list[i + 1]]
            self.nodes_used.add(OD_list[i + 1])

            self.links_writer.writerow([self.new_way_id, name, lanes, length, speed, capacity, function, origin, destination])
            self.new_way_id += 1
            if not oneway:
                self.links_writer.writerow([self.new_way_id, name, lanes, length, speed, capacity,function, destination, origin])
                self.new_way_id += 1

        return

    #TODO: get way type (nationale, departementale, etc...)
    def get_way_type(self, ways):
        types = ["D", "A", "N"]

        if 'ref' not in ways:
            return None

        elif ways['ref'][0] in types:
            return ways['ref'][0]

        else:
            return None

    #Uses the haversine formula to calculate distance between 2 points
    def get_way_length(self, long1, lat1, long2, lat2):
        #Earth radius in Km
        r = 6371

        a = sin(radians(lat2-lat1)/2)**2 + cos(lat1) * cos(lat2) * sin(radians(long2-long1)/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = r * c
        return distance


    def is_highway(self, ways):

        not_highway = ["footway", "service", "track", "bus_guideway", "escape", "raceway", "bridleway", "steps", "path", "sidewalk", "cycleway", "pedestrian"]

        if 'highway' in ways and ways['highway'] not in not_highway:
            return True
        else:
            return False


class Parser(osmium.SimpleHandler):
    nodes = {}
    nodes_appearances = {}
    new_nodes_id = {}

    def __init__(self):
        osmium.SimpleHandler.__init__(self)
        self.new_node_id = 0

    def node(self, n):
        self.register_node(n)

    def way(self, w):
        self.register_way(w)

    def register_node(self, node):
        id = node.id
        name = id

        location = node.location
        x = location.lat
        y = location.lon

        tags = node.tags

        if 'name' in tags:
            name = tags['name']
            name = unicodedata.normalize('NFD', name)
            name = name.encode('ascii', 'ignore')

        node = {'id': id, 'name': name, 'lat': x, 'lon': y}

        self.nodes.update({id: node})

    def register_way(self, way):
        nodes = way.nodes

        for node in nodes:
            if node.ref in self.nodes_appearances:
                self.nodes_appearances.update({node.ref: self.nodes_appearances[node.ref] + 1})
            else:
                self.nodes_appearances.update({node.ref: 1})


if __name__ == '__main__':

    #User forgot to input the file name
    if len(sys.argv) < 2:
        print("Please specify the name of the OSM file and the extension.")
        sys.exit(0)

    file = sys.argv[1]#"Paris.osm.pbf"

    #File does not exists or is not in the same folder as the script
    if not path.exists(file):
        print("The file \'%s\' does not exists or is not in the same folder as the script." % file)
        sys.exit(0)

    h = Parser()

    print("Reading file....")
    h.apply_file(file, locations=True, idx='flex_mem')
    print("Done!")

    g = Writer(h.nodes, h.new_nodes_id, h.nodes_appearances)

    h = None
    gc.collect()

    print("Writing ways....")
    g.apply_file(file, locations=True, idx='flex_mem')
    print("Done!")
    print("Writing nodes....")
    g.write_nodes()
    print("Done!")

    print("Finished!")



