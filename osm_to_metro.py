import csv
import sys
import os

import osmium
import geojson
import shapely.wkb as wkblib
from shapely.geometry import Point

VALID_HIGHWAYS = ('motorway', 'trunk', 'primary', 'secondary', 'motorway_link',
                  'trunk_link', 'primary_link', 'secondary_link',
                  # 'tertiary', 'unclassified', 'road', 'residential',
                  # 'living_street',
                  )
ROADTYPE_TO_ID = {
    'motorway': 1,
    'trunk': 2,
    'primary': 3,
    'secondary': 4,
    # 'tertiary': 5,
    # 'unclassified': 6,
    # 'residential': 7,
    'motorway_link': 8,
    'trunk_link': 9,
    'primary_link': 10,
    'secondary_link': 11,
    # 'living_street': 12,
    # 'road': 13,
}

wkbfab = osmium.geom.WKBFactory()


class Writer(osmium.SimpleHandler):

    def __init__(self):
        super(Writer, self).__init__()
        self.edges = list()
        self.nodes = dict()
        self.counter = 1

    def way(self, w):
        self.add_way(w)

    def add_way(self, way):

        road_type = way.tags.get('highway', None)
        if road_type not in VALID_HIGHWAYS:
            return
        road_type = ROADTYPE_TO_ID[road_type]

        name = (
            way.tags.get('name', '')
            or way.tags.get('addr:street', '')
            or way.tags.get('ref', '')
        )

        source = way.nodes[0].ref
        target = way.nodes[-1].ref

        oneway = way.tags.get('oneway', 'no') == 'yes'

        edge_id = self.counter
        self.counter += 1
        if not oneway:
            back_edge_id = self.counter
            self.counter += 1

        # Find maximum speed if available.
        try:
            speed = float(way.tags.get('maxspeed', ''))
        except ValueError:
            speed = None
        if not oneway:
            try:
                speed = float(way.tags.get('maxspeed:forward', '0')) or speed
            except ValueError:
                speed = None
            try:
                back_speed = (
                    float(way.tags.get('maxspeed:backward', '0'))
                    or speed
                )
            except ValueError:
                back_speed = None

        # Find number of lanes if available.
        if oneway:
            try:
                lanes = int(way.tags.get('lanes', ''))
            except ValueError:
                lanes = None
        else:
            try:
                lanes = (
                    int(way.tags.get('lanes:forward', '0'))
                    or int(way.tags.get('lanes', '')) // 2
                )
            except ValueError:
                lanes = None
            try:
                back_lanes = (
                    int(way.tags.get('lanes:backward', '0'))
                    or int(way.tags.get('lanes', '')) // 2
                )
            except ValueError:
                back_lanes = None

        # Create a geometry of the road.
        wkb = wkbfab.create_linestring(way)
        geometry = wkblib.loads(wkb, hex=True)
        if not oneway:
            wkb = wkbfab.create_linestring(
                way, direction=osmium.geom.direction.BACKWARD)
            back_geometry = wkblib.loads(wkb, hex=True)

        # Add source and target to the nodes of the network.
        self.nodes[source] = geojson.Feature(
            geometry=Point(geometry.coords[0]),
            properties={"id": source}
        )
        self.nodes[target] = geojson.Feature(
            geometry=Point(geometry.coords[-1]),
            properties={"id": target}
        )

        # Compute length in kilometers.
        length = osmium.geom.haversine_distance(way.nodes) / 1e3

        self.edges.append(geojson.Feature(
            geometry=geometry,
            properties={
                "id": edge_id,
                "name": name,
                "road_type": road_type,
                "lanes": lanes,
                "length": length,
                "speed": speed,
                "source": source,
                "target": target,
                "osm_id": way.id,
            },
        ))

        if not oneway:
            self.edges.append(geojson.Feature(
                geometry=back_geometry,
                properties={
                    "id": back_edge_id,
                    "name": name,
                    "road_type": road_type,
                    "lanes": back_lanes,
                    "length": length,
                    "speed": back_speed,
                    "source": target,
                    "target": source,
                    "osm_id": way.id,
                },
            ))

    def write_ways(self, filename):
        feature_collection = geojson.FeatureCollection(
            self.edges,
            crs={
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
            },
        )
        with open(filename, 'w', encoding='utf-8') as f:
            geojson.dump(feature_collection, f)

    def write_nodes(self, filename):
        feature_collection = geojson.FeatureCollection(
            list(self.nodes.values()),
            crs={
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
            },
        )
        with open(filename, 'w', encoding='utf-8') as f:
            geojson.dump(feature_collection, f)


if __name__ == '__main__':

    # User forgot to input the file name.
    if len(sys.argv) < 2:
        print("Please specify the name of the OSM file and the extension.")
        sys.exit(0)

    filename = sys.argv[1]

    # File does not exists or is not in the same folder as the script.
    if not os.path.exists(filename):
        print("File not found: {}".format(filename))
        sys.exit(0)

    g = Writer()

    print("Reading OSM data...")
    g.apply_file(filename, locations=True, idx='flex_mem')

    print("Writing ways...")
    g.write_ways('idf_osm_2021/edges.geojson')

    print("Writing nodes...")
    g.write_nodes('idf_osm_2021/nodes.geojson')

    print("Done!")
