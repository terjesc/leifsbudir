

import time
import pymclevel
import numpy as np
from scipy import ndimage
import matplotlib.pyplot as plt
import heapq


SEA_LEVEL = 62 # FIXME: Read sea level from map instead?


inputs = (
	("Settlement generator", "label"),
	("Material", pymclevel.alphaMaterials.Cobblestone),
	("Creator: Terje Schjelderup", "label"),
	)

def stopwatch():
    nextTime = time.clock()
    timepassed = nextTime - stopwatch.time
    stopwatch.time = nextTime
    return timepassed
stopwatch.time = 0

# Overall idea:
# * Obtain height map. Ignore trees, plants, grass, etc.
# * Generate gradient map. Use filter such as e.g. Sobel.
# * Generate sea/river/water mask.
# => Flat, non-watery areas are habitable and traversable by land.
# => Flat, watery areas are traversable by boat.
# * Find ways to connect habitable areas to each other.
# * Find locations for key components such as farms, wells, squares, ports, castles, populated areas, religious buildings, blacksmiths, bakers, wind mills, vantage points, sightlines, lighthouses, piers etc.
# * Lay down roads, internally within areas, to key locations and to connection points.
# * Designate plots for individual structures.
# * Create list of common materials to be found in the area.
# * Generate structures on designated plots using available materials.

def perform(level, box, options):
    print("Leifsbudir filter started.")
    CLOCK_START = time.clock()

    np.set_printoptions(precision=3)

    # Initiate stopwatch
    stopwatch()

    print("Generate terrain height map...")
    heightMap = generateTerrainHeightMap(level, box)
    print("...done, after %0.3f seconds." % stopwatch())
    
    if False:
        plt.figure("Terrain height map")
        plt.imshow(heightMap)
        plt.show()
        stopwatch()

    print("Apply Sobel operator...")
    sobelX = ndimage.sobel(heightMap, 1)
    sobelZ = ndimage.sobel(heightMap, 0)
    sobel = np.sqrt(sobelX ** 2 + sobelZ ** 2)
    print("...done, after %0.3f seconds." % stopwatch())
    
    if False:
        plt.figure("Terrain gradients (Sobel)")
        plt.imshow(sobel)
        plt.show()
        stopwatch()

    print("Create sea water mask...")
    seaMask = generateSeaMask(level, box)
    print("...done, after %0.3f seconds." % stopwatch())
    
    if False:
        plt.figure("Sea water mask")
        plt.imshow(seaMask)
        plt.show()
        stopwatch()

    print("Generate Estimated Cost Of Sailing (ECOS) map...")
    ECOSMap = generateEstimatedCostOfSailingMap(
            level, box, heightMap, seaMask)
    print("...done, after %0.3f seconds." % stopwatch())
    
    if False:
        plt.figure("Estimated Cost Of Sailing (ECOS)")
        plt.imshow(ECOSMap)
        plt.show()
        stopwatch()

    print("Label traversable sea regions...")
    traversableSeaRegions = generateTraversableSeaRegionsMap(ECOSMap)
    print("...done, after %0.3f seconds." % stopwatch())
    
    if False:
        plt.figure("Traversable sea regions of a certain size")
        plt.imshow(traversableSeaRegions)
        plt.show()
        stopwatch()

    print("Find canal locations...")
    canalCoordinates = findCanalLocations(box, traversableSeaRegions,
            ECOSMap, seaMask)
    print("...done, after %0.3f seconds." % stopwatch())

    if False:
        plt.figure("Canals")
        toPlot = np.array(canalCoordinates)
        plt.plot(toPlot[:,0], toPlot[:,1], "o")
        plt.gca().invert_yaxis()
        plt.show()
        stopwatch()


    print("Total runtime: %0.1f seconds." % (time.clock() - CLOCK_START))
    print("Leifsbudir filter finished.")


def setBlock(level, (block, data), x, y, z):
	level.setBlockAt((int)(x),(int)(y),(int)(z), block)
    	level.setBlockDataAt((int)(x),(int)(y),(int)(z), data)


# This list is not exhaustive, as other "terrain" blocks does
# exist in the overworld. However, those blocks generate only
# in the depths (e.g. rare ores) or in so small quantity that
# counting them leads to significant overhead for practically
# no gain (e.g. mossy stones, infested blocks.) Chosen blocks
# are intended to cover 99.9 % of top layer terrain blocks in
# all biomes.
remainingTerrainBlocks = [
        # TODO: Sort list by general prevalence?
        # 1 - 4: stone, grass, dirt, cobblestone
        # 12 - 16: sand, gravel, gold ore, iron ore, coal ore
        82, # clay
        159, # stained clay
        172, # hardened clay
        80, # snow
        110, # mycelium
        174, # packed ice
        ]


def isTerrainBlock(block):
    # return early if water or air
    if block == 9 or block == 0:
        return False

    # return early if stone (1), grass (2), dirt (3), or cobblestone (4)
    if block <= 4:
        return True

    # return early if leaves (18, 161)
    if block == 18 or block == 161:
        return False

    # return early if sand (12), or gravel (13),
    # and if gold (14), iron (15), or coal (16) ore.
    if block >= 12 and block <= 16:
        return True

    # Time consuming check
    return block in remainingTerrainBlocks

def terrainHeight(chunkSlice, x, z, miny, maxy):
    for y in range(maxy, miny, -1):
            if isTerrainBlock(chunkSlice[x][z][y]):
                return y
    return 0


def generateTerrainHeightMap(level, box):
    mapXSize = box.maxx - box.minx
    mapZSize = box.maxz - box.minz
    heightMap = np.zeros((mapZSize, mapXSize), dtype=int)

    chunkSlices = level.getChunkSlices(box)
    for (chunk, slices, point) in chunkSlices:
        chunkSlice = chunk.Blocks[slices]
        roughHeightMap = chunk.HeightMap.T
        xOffset = (chunk.chunkPosition[0] << 4) - box.minx
        zOffset = (chunk.chunkPosition[1] << 4) - box.minz
        for x in range(0, 16):
            for z in range(0, 16):
                y = roughHeightMap[x][z] - 1
                height = terrainHeight(chunkSlice, x, z, 0, y)
                heightMap[z + zOffset][x + xOffset] = height
    return heightMap


def generateSeaMask(level, box):
    seaMask = []
    for z in range(box.minz, box.maxz):
        row = []
        for x in range(box.minx, box.maxx):
            isWater = False
            if 9 == level.blockAt(x, SEA_LEVEL, z):
                isWater = True
            row.append(isWater)
        seaMask.append(row)
    return np.array(seaMask)


def generateEstimatedCostOfSailingMap(level, box, heightMap, seaMask):
    mapXSize = box.maxx - box.minx
    mapZSize = box.maxz - box.minz
    MAX_DIG_COST = 5
    MIN_BRIDGE_COST = 5
    BASE_COST = 1
    EDGE_COST = BASE_COST + (5 * MAX_DIG_COST)
    ECOSMap = np.full((mapZSize, mapXSize), EDGE_COST, dtype=int)
    for z in xrange(box.minz + 1, box.maxz - 1):
        zIndex = z - box.minz
        for x in xrange(box.minx + 1, box.maxx - 1):
            xIndex = x - box.minx
            cost = BASE_COST
            for xInner, zInner in ((xIndex, zIndex - 1),
             (xIndex - 1, zIndex), (xIndex, zIndex), (xIndex + 1, zIndex),
                                   (xIndex, zIndex + 1)):
                    height = heightMap[zInner][xInner]
                    costAtColumn = height - (SEA_LEVEL - 1)
                    costAtColumn = max(0, costAtColumn)
                    costAtColumn = min(MAX_DIG_COST, costAtColumn)
                    if (height < (SEA_LEVEL)
                            and False == seaMask[zInner][xInner]):
                        costAtColumn = SEA_LEVEL - height
                        costAtColumn = max(MIN_BRIDGE_COST, costAtColumn)
                    cost += costAtColumn
            ECOSMap[zIndex][xIndex] = cost
    return np.array(ECOSMap)

def generateTraversableSeaRegionsMap(ECOSMap):
    traversableSeaMask = ECOSMap <= 1
    traversableSeaRegions, count = ndimage.label(traversableSeaMask)
    sizes = ndimage.sum(
            traversableSeaMask, traversableSeaRegions, range(count + 1))
    sizeMask = sizes < 250
    removeMask = sizeMask[traversableSeaRegions]
    traversableSeaRegions[removeMask] = 0
    labels = np.unique(traversableSeaRegions)
    traversableSeaRegions = np.searchsorted(labels, traversableSeaRegions)
    return traversableSeaRegions

def findCanalLocations(box, regionMap, ECOSMap, seaMask):
    class Node:
        UNCLAIMED = 0
        MARKED = 1
        ERODING = 2
        CLAIMED = 3
        PROPER = 4

        def __init__(self, nodeType = UNCLAIMED, region = None,
                direction = None, origin = None, cost = None,
                accumulatedCost = 0, coordinates = (None, None)):
            self.nodeType = nodeType
            self.region = region
            self.direction = direction
            self.origin = origin
            self.cost = cost
            self.accumulatedCost = accumulatedCost
            self.coordinates = coordinates

        def __str__(self):
            return str(self.__class__) + ": " + str(self.__dict__)

    directions = ((-1, 0), (1, 0), (0, -1), (0, 1))
    mapXSize = box.maxx - box.minx
    mapZSize = box.maxz - box.minz
    searchMap = [[Node()] * mapXSize for i in range(mapZSize)]
    canalCoordinates = []

    def initRegions():
        for z in range(len(regionMap)):
            for x in range(len(regionMap[z])):
                region = regionMap[z][x]
                if region != 0:
                    node = Node(nodeType = Node.PROPER, region = region,
                            origin = (x, z), cost = 1,
                            coordinates = (x, z))
                    searchMap[z][x] = node
                else:
                    node = Node(coordinates = (x, z))
                    searchMap[z][x] = node

    def convertMarkedToEroding():
        for z in range(1, len(searchMap) - 1):
            for x in range(1, len(searchMap[z]) - 1):
                if searchMap[z][x].nodeType == Node.MARKED:
                    searchMap[z][x].nodeType = Node.ERODING

    def mergeRegions(regionA, regionB):
        for z in range(1, len(searchMap) - 1):
            for x in range(1, len(searchMap[z]) - 1):
                if searchMap[z][x].region == regionB:
                    searchMap[z][x].region = regionA

    def makeCanal((x, z)):
        node = searchMap[z][x]
        while node.nodeType != Node.PROPER:
            if ECOSMap[z][x] != 1:
                ECOSMap[z][x] = 1
                canalCoordinates.append(node.coordinates)
                seaMask[z][x] = True
                for xOffset, zOffset in directions:
                    seaMask[z + zOffset][x + xOffset] = True
            x = node.coordinates[0] + node.direction[0]
            z = node.coordinates[1] + node.direction[1]
            node = searchMap[z][x]

    def travelDistance(travelMask, start, goal, timeout=100):
        if start == goal:
            return 0

        def heuristic(pointA, pointB):
            (aX, aZ) = pointA
            (bX, bZ) = pointB
            return abs(bX - aX) + abs(bZ - aZ)

        bestCase = heuristic(start, goal)
        if 1 == bestCase:
            return 1

        (startX, startZ) = start
        (goalX, goalZ) = goal

        visited = set()

        edge = []
        estimate = bestCase
        distance = 0
        coordinates = start
        heapq.heappush(edge, (estimate, distance, coordinates))

        while len(edge):
            (estimate, thusFar, (x, z)) = heapq.heappop(edge)
            if (x, z) == goal:
                return thusFar

            for (xOffset, zOffset) in directions:
                xInner = x + xOffset
                zInner = z + zOffset
                if (1 == travelMask[zInner][xInner]
                        and (xInner, zInner) not in visited):

                    visited.add((xInner, zInner))

                    newThusFar = thusFar + 1
                    newHeuristic = heuristic((xInner, zInner), goal)
                    newEstimate = newThusFar + newHeuristic

                    # Only add nodes to the queue if they can result in
                    # a path that is shorter than the timeout
                    if newEstimate <= timeout:
                        newCoordinates = (xInner, zInner)
                        heapq.heappush(edge,
                                (newEstimate,
                                    newThusFar,
                                    newCoordinates))
        return timeout

    def spread(node):
        x, z = node.coordinates

        for xOffset, zOffset in directions:
            xOther = x + xOffset
            zOther = z + zOffset
            otherNode = searchMap[zOther][xOther]

            if otherNode.nodeType == Node.UNCLAIMED:
                otherNode.nodeType = Node.MARKED
                otherNode.region = node.region
                otherNode.direction = (xOffset * -1, zOffset * -1)
                otherNode.origin = node.origin
                otherNode.cost = ECOSMap[zOther][xOther]
                otherNode.accumulatedCost = node.accumulatedCost
                searchMap[zOther][xOther] = otherNode

            elif (otherNode.nodeType == Node.CLAIMED
                    or otherNode.nodeType == Node.PROPER):
                if otherNode.region == node.region:
                    # (Possible) canal interior to the region
                    # Calculate cost vs benefit
                    BASE_COST = 10
                    costOfCanal = 2 * (BASE_COST
                        + node.accumulatedCost
                        + otherNode.cost
                        + otherNode.accumulatedCost)

                    #costOfTravel = 0
                    costOfTravel = travelDistance(
                            ECOSMap,
                            node.origin,
                            otherNode.origin,
                            costOfCanal + 1)
                    if costOfTravel > costOfCanal:
                        makeCanal(node.coordinates)
                        makeCanal(otherNode.coordinates)

                else:
                    # Canal connecting two regions
                    makeCanal(node.coordinates)
                    makeCanal(otherNode.coordinates)
                    mergeRegions(node.region, otherNode.region)

    # Initialize regions
    initRegions()

    # Fist iteration: Spread from proper nodes
    for x in range(1, mapXSize - 1):
        for z in range(1, mapZSize - 1):
            node = searchMap[z][x]
            if node.nodeType == Node.PROPER:
                spread(node)

    # Subsequent iterations: Spread from eroded nodes
    MAX_COST = 250

    for iterationNumber in xrange(MAX_COST):
        convertMarkedToEroding()

        # Erode (and spread if finished)
        for x in range(1, mapXSize - 1):
            for z in range(1, mapZSize - 1):
                node = searchMap[z][x]
                if node.nodeType == Node.ERODING:
                    node.cost -= 1
                    node.accumulatedCost += 1
                    if 0 == node.cost:
                        node.nodeType = Node.CLAIMED
                        spread(node)
                    searchMap[z][x] = node

    return canalCoordinates


