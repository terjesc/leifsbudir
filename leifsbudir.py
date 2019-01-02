

import time
import pymclevel
import numpy as np
from scipy import ndimage
import matplotlib.pyplot as plt


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

#print(level.materials.blockWithID(9)) TODO: remove

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

#    print("Color the ground with wool...")
#    for z in range(box.minz, box.maxz):
#        sobelZIndex = z - box.minz
#        for x in range(box.minx, box.maxx):
#            sobelXIndex = x - box.minx
#            y = heightMap[sobelZIndex][sobelXIndex]
#            color = sobel[sobelZIndex][sobelXIndex].astype(int)
#            WOOL_ID = 35
#            CUTOFF = 5
#            if color < CUTOFF:
#                color = 5 # lime
#            elif color > CUTOFF:
#                color = 14 # red
#            elif color == CUTOFF:
#                color = 4 # yellow
#            setBlock(level, (WOOL_ID, color), x, y, z)
#    print("...done, after %0.3f seconds." % stopwatch())

    print("Create sea water mask...")
    seaMask = generateSeaMask(level, box)
    print("...done, after %0.3f seconds." % stopwatch())
    
    if False:
        plt.figure("Sea water mask")
        plt.imshow(seaMask)
        plt.show()
        stopwatch()

    print("Generate Estimated Cost Of Sailing (ECOS) map...")
    ECOSMap = generateEstimatedCostOfSailingMap(level, box, heightMap)
    print("...done, after %0.3f seconds." % stopwatch())
    
    if True:
        plt.figure("Estimated Cost Of Sailing (ECOS)")
        plt.imshow(ECOSMap)
        plt.show()
        stopwatch()

    print("Label traversable sea regions...")
    traversableSeaMask = ECOSMap <= 1
    traversableSeaRegions, count = ndimage.label(traversableSeaMask)
    sizes = ndimage.sum(traversableSeaMask, traversableSeaRegions, range(count + 1))
    mask_size = sizes < 250
    remove_pixel = mask_size[traversableSeaRegions]
    traversableSeaRegions[remove_pixel] = 0
    labels = np.unique(traversableSeaRegions)
    traversableSeaRegions = np.searchsorted(labels, traversableSeaRegions)
    print("...done, after %0.3f seconds." % stopwatch())
    
    if True:
        plt.figure("Traversable sea regions of a certain size")
        plt.imshow(traversableSeaRegions)
        plt.show()
        stopwatch()

    print("Leifsbudir filter finished.")


def setBlock(level, (block, data), x, y, z):
	level.setBlockAt((int)(x),(int)(y),(int)(z), block)
    	level.setBlockDataAt((int)(x),(int)(y),(int)(z), data)


terrainBlocks = [
        1, # stone
        2, # grass
        3, # dirt
        4, # cobblestone
        7, # bedrock
        12, # sand
        13, # gravel
        14, # gold ore
        15, # iron ore
        16, # coal ore
        35, # wool TODO: remove, used for debug purposes only
        21, # lapis lazuli ore
        24, # sandstone
        44, # slab
        48, # moss stone
        49, # obsidian
        56, # diamond ore
        60, # farmland
        73, # redstone ore
        79, # ice
        80, # snow
        82, # clay
        84, # clay
        97, # monster egg
        98, # stone bricks
        119, # mycelium
        121, # end stone
        129, # emerald ore
        159, # stained clay
        174, # packed ice
        179, # red sandstone
        181, # red sandstone double slab
        208, # path
        212, # frosted ice
        ]


def isTerrainBlock(block):
    # return early if air
    if block == 0 or block == 9:
        return False
    # Time consuming check
    return block in terrainBlocks


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
                y = roughHeightMap[x][z]
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


def generateEstimatedCostOfSailingMap(level, box, heightMap):
    ECOSMap = []
    for z in xrange(box.minz + 1, box.maxz - 1):
        zIndex = z - box.minz
        row = []
        for x in xrange(box.minx + 1, box.maxx - 1):
            xIndex = x - box.minx
            cost = 1
            for zInner in range(zIndex - 1, zIndex + 2):
                for xInner in range(xIndex - 1, xIndex + 2):
                    height = heightMap[zInner][xInner]
                    costAtColumn = height - (SEA_LEVEL - 1)
                    costAtColumn = max(0, costAtColumn)
                    costAtColumn = min(4, costAtColumn)
                    cost += costAtColumn
            row.append(cost)
        ECOSMap.append(row)
    return np.array(ECOSMap)

# TODO: Find suitable places to dig canals (and tunnels)
# - Inspiration from distance transform, dijkstra, etc. Find the point
#   where the distance (weightet for cost) from sea to sea is the shortest,
#   use the sea tiles closest to the shore on each side as start and
#   finish points, and calculate cost of travel with and without a
#   canal / tunnel. If canal/tunnel is cheaper, build it. Then continue
#   the search. Time out at a predetermined "maximum cost".
#
# * Let all regions grow outwards, speed dictated by ECOS.
# * When region collides with other region:
#   - Suitable canal point found
#   - Dig canal there
#   - Merge regions, including canal area
# * When region collides with itself:
#   - Find the two points from where the growth came,
#     one on each side
#   - Determine the cost of digging canal/tunnel between the points
#   - Determine the cost of sailing between the points without digging
#   - If digging is cheaper than sailing:
#     - Include canal in region
# * Decide when to stop: Max cost of canal building, regions left, etc.


