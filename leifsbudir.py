

import time
import pymclevel
import numpy as np
from scipy import ndimage

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

    np.set_printoptions(precision=3)

    print("Generating height map...")
    stopwatch()
    heightMap = terrainHeightMap(level, box)
    print("...done, after %0.3f seconds." % stopwatch())
#    print(heightMap)

    print("Applying Sobel operator...")
    sobelX = ndimage.sobel(heightMap, 1)
#    print(sobelX)
    sobelZ = ndimage.sobel(heightMap, 0)
#    print(sobelZ)
    sobel = np.sqrt(sobelX ** 2 + sobelZ ** 2)
#    print(sobel.astype(int))
    print("...done, after %0.3f seconds." % stopwatch())

    print("Coloring the ground with wool...")
    for z in range(box.minz, box.maxz):
        sobelZIndex = z - box.minz
        for x in range(box.minx, box.maxx):
            sobelXIndex = x - box.minx
            y = heightMap[sobelZIndex][sobelXIndex]
            color = sobel[sobelZIndex][sobelXIndex].astype(int)
            WOOL_ID = 35
            CUTOFF = 5
            if color < CUTOFF:
                color = 5 # lime
            elif color > CUTOFF:
                color = 14 # red
            elif color == CUTOFF:
                color = 4 # yellow
            setBlock(level, (WOOL_ID, color), x, y, z)
    print("...done, after %0.3f seconds." % stopwatch())

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
    if block == 0:
        return False
    # Time consuming check
    return block in terrainBlocks


def terrainHeight(level, x, z, miny, maxy):
    nonterrainBlocks = []
    nonterrainBlocks.append(0)
    for y in xrange(maxy, miny, -1):
            if isTerrainBlock(level.blockAt(x, y, z)):
                return y
    return 0

def terrainHeightMap(level, box):
    heightMap = []
    for z in range(box.minz, box.maxz):
        column = []
        for x in range(box.minx, box.maxx):
            column.append(terrainHeight(level, x, z, box.miny, box.maxy))
        heightMap.append(column)
    return np.array(heightMap)


