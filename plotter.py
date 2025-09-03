import logging
from PIL import Image, ImageDraw, ImageColor

class Plotter:

    def __init__(self, 
                 units="usft", 
                 origin=(2180160.0001, 6660000.0000),
                 su_size=32.81,
                 tile_grid=(21, 18),
                 subcell_grid=10,
                 bottom_left=('A','A'),
                 direction='ascending'):
        self.units = units
        self.origin = origin
        self.su_size = su_size
        self.tile_grid = tile_grid
        self.subcell_grid = subcell_grid
        self.bottom_left = bottom_left
        self.direction = direction

        self.origin_x = self.origin[0]
        self.origin_y = self.origin[1]
        self.tile_grid_x = self.tile_grid[0]
        self.tile_grid_y = self.tile_grid[1]
        self.subcell_size = self.su_size / self.subcell_grid

        self.tile_sign = 1 if self.direction=='ascending' else -1;
        self.bottom_left_x = ord(self.bottom_left[0])
        self.bottom_left_y = ord(self.bottom_left[1])

    def _tile_label(self, tile_x_n, tile_y_n):
        tile_x_c = chr(int(self.bottom_left_x + (self.tile_sign * tile_x_n)))
        tile_y_c = chr(int(self.bottom_left_y + (self.tile_sign * tile_y_n)))
        tile = tile_y_c + tile_x_c
        return tile

    def _tile(self, x, y):
        # 1. How many feet away from the origin are we and how many Tiles is that?
        tile_x_n = (x - self.origin_x) // (self.tile_grid_x * self.su_size)
        tile_y_n = (y - self.origin_y) // (self.tile_grid_y * self.su_size)

        tile = self._tile_label(tile_x_n, tile_y_n)

        logging.debug(f'{x}, {y} is {tile_x_n} Tiles right and {tile_y_n} Tiles up from the origin of {self.bottom_left}')
        return (tile_x_n, tile_y_n, tile)

    def _su(self, x, y, tile_x_n, tile_y_n, tile):
        # 2a. Compute the origin of the Tile and figure out which SU we're in
        tile_origin_x = self.origin_x + (tile_x_n * self.tile_grid_x * self.su_size)
        tile_origin_y = self.origin_y + (tile_y_n * self.tile_grid_y * self.su_size)
        logging.debug(f'The origin of Tile {tile} is {tile_origin_x}, {tile_origin_y}')

        # 2b. Compute how many SUs we are from the origin of the Tile we're in
        su_x_n = (x - tile_origin_x) // self.su_size
        su_y_n = (y - tile_origin_y) // self.su_size
        logging.debug(f'{x}, {y} is {su_x_n} SUs right and {su_y_n} Sus up from the origin of {tile}')

        # SU = bottom left SU + SUs right - SU rows up
        # SUs start in the top left corner and progress left-to-right and top-to-bottom
        su = int((self.tile_grid_x * (self.tile_grid_y - 1) + 1) + (su_x_n) - (self.tile_grid_x * su_y_n))

        return (tile_origin_x, tile_origin_y, su_x_n, su_y_n, su)
    
    def _subcell(self, x, y, tile, tile_origin_x, tile_origin_y, su_x_n, su_y_n, su):
        # subcell = bottom left subcell + subcells right + subcells rows up
        # subcells start in the bottom left corner and progress left-to-right and bottom-to-top
        # 3a. Compute the origin of the SU and figure out which Subcell we're in
        su_origin_x = tile_origin_x + (su_x_n * self.su_size)
        su_origin_y = tile_origin_y + (su_y_n * self.su_size)
        logging.debug(f'The origin of SU {tile}-{su} is {su_origin_x}, {su_origin_y}')

        # 3b. Compute how many Subcells we are from the origin of the SU we're in
        subcell_x_n = (x - su_origin_x) // self.subcell_size
        subcell_y_n = (y - su_origin_y) // self.subcell_size
        logging.debug(f'{x}, {y} is {subcell_x_n} subcells right and {subcell_y_n} subcells up from the origin of {tile}-{su}')

        return int(1 + (subcell_x_n) + (self.subcell_grid * subcell_y_n))


    def convert_xy(self, x, y):
        """
        x: Local coordinate Easting in given units
        y: Local coordinate Northing in given units
        origin: (x,y) of the bottom left corner
        su_size: horizontal and vertical size of an SU in given units
        tile_grid: dimensions of an Tile as (width in SUs, height in SUs)
        subcell_grid: number of subcells to divide each SU into horizontally and vertically
        bottom_left: the label for the Tile in the bottom left corner of the map, aka the origin
        direction: should the letters in the Tile label go up or down alphabetically

        Converts from Local coordinate format into Tile, SU, Subcell. 
        2180160.0001, 6660000.0000 -> ("AA", 358, 91)

        >>> convert_xy(2180160.0001, 6660000.0000)  
        ('AA', 358, 1)

        >>> convert_xy(2180160.0001 + 32.81*21.01, 6660000.0000)
        ('AB', 358, 1)

        >>> convert_xy(2180160.0001 + 32.81*22.01 + 4, 6660000.0000 + 32.81*19.01 + 4)
        ('BB', 338, 12)

        >>> convert_xy(2119489.0441, 6790803.3131, origin=(2119489.0440, 6790803.3130), bottom_left=('Z','Z'), direction='descending')
        ('ZZ', 358, 1)
        """
        # TODO: Probably worth adding a bunch more test cases using other parameters
        #       to make sure all the calculations work properly.
        (tile_x_n, tile_y_n, tile) = self._tile(x, y)
        (tile_origin_x, tile_origin_y, su_x_n, su_y_n, su) = self._su(x, y, tile_x_n, tile_y_n, tile)
        subcell = self._subcell(x, y, tile, tile_origin_x, tile_origin_y, su_x_n, su_y_n, su)

        return (tile, su, subcell)


    def plot(self, xs=[], ys=[], colors=[], shadings={},         
        subcell_size_px=50,
        base_su=(1, 1),
        height_tiles=3,
        width_tiles=3,
        subcell_text=False,
        su_text=False,
        tile_text=False,
        level_colors=('red','blue','gray')):
        """
        xs, ys, colors: points to plot with a small dot
        shadings: dictionary of shading color keyed on subcell or cell

        Plots the appropriate grid and a series of given points in that grid
        """

        tile_grid_x = self.tile_grid[0]
        tile_grid_y = self.tile_grid[1]

        su_size_px = subcell_size_px * self.subcell_grid
        tile_size_x_px = tile_grid_x * su_size_px
        tile_size_y_px = tile_grid_y * su_size_px

        width_px = width_tiles * tile_grid_x * self.subcell_grid * subcell_size_px
        height_px = height_tiles * tile_grid_y * self.subcell_grid * subcell_size_px

        img = Image.new("RGBA", (width_px, height_px), "white")
        draw = ImageDraw.Draw(img)
        grid = {}

        # draw the subcell, cell, su grid
        # And build our array of subcell coordinates
        for tx in range(width_tiles):
            for ty in range(height_tiles):
        
                tile_x = tx * tile_size_x_px
                tile_y = ty * tile_size_y_px
                tile_x_n = base_su[0]-1 + tx
                tile_y_n = base_su[1]-1 + height_tiles - ty - 1
                tile = self._tile_label(tile_x_n, tile_y_n)

                tile_box = [tile_x, tile_y, (tx+1) * tile_size_x_px, (ty+1) * tile_size_y_px]
                
                logging.info(f"Drawing Tile: {tile} at {tile_box}")
                draw.rectangle(tile_box, None, level_colors[0], 5)

                su_num = 1
                for sy in range(tile_grid_y):
                    for sx in range(tile_grid_x):
                        su_x = tile_x + (sx * su_size_px)
                        su_y = tile_y + (sy * su_size_px)
                        su_box = [su_x, su_y, su_x + su_size_px, su_y + su_size_px]
                        # logging.debug(f"Drawing SU: {tile}-{su} at {su_box}")
                        if (tile, su_num) in shadings:
                            su_color = shadings.get((tile, su_num))
                        elif tile+'-'+str(su_num) in shadings:
                            su_color = shadings.get(tile+'-'+str(su_num))
                        else:
                            su_color = None
                        draw.rectangle(su_box, su_color, level_colors[1], 3)
                        if su_text:
                            draw.text([su_x + su_size_px/2, su_y + su_size_px/2], 
                                    f'{tile}-{su_num}', level_colors[1],
                                    anchor='mm', font_size=2*subcell_size_px)

                        subcell = 1
                        for by in range(self.subcell_grid, 0, -1):
                            for bx in range(self.subcell_grid):
                                subcell_x = su_x + (bx * subcell_size_px)
                                subcell_y = su_y + ((by-1) * subcell_size_px)
                                subcell_box = [subcell_x, subcell_y, subcell_x + subcell_size_px, subcell_y + subcell_size_px]
                                # logging.debug(f"Drawing Subcell: {tile}-{su}-{subcell} at {subcell_box}")
                                if (tile, su_num, subcell) in shadings:
                                    subcell_color = shadings.get((tile, su_num, subcell))
                                elif tile+'-'+str(su_num)+'-'+str(subcell) in shadings:
                                    subcell_color = shadings.get(tile+'-'+str(su_num)+'-'+str(subcell))
                                else:
                                    subcell_color = None
                                draw.rectangle(subcell_box, subcell_color, level_colors[2], 1)
                                if subcell_text:
                                    draw.text([subcell_x + subcell_size_px/2, subcell_y + subcell_size_px/2], 
                                            f'{tile}-{su_num}-{subcell}', level_colors[2],
                                            anchor='mm', font_size=subcell_size_px/5)

                                # Store the subcell coordinates
                                grid[(tile, su_num, subcell)] = subcell_box
                                subcell += 1

                        # Store the SU coordinates
                        grid[(tile, su_num)] = su_box
                        su_num += 1

                # Store the Tile coordinates
                grid[(tile)] = tile_box

                if tile_text:
                    draw.text([tile_x + tile_size_x_px/2, tile_y + tile_size_y_px/2], 
                            f'{tile}', level_colors[0],
                            anchor='mm', font_size=20*subcell_size_px)


        # Now plot our points
        for in_x, in_y, color in zip(xs, ys, colors):
            # Distance from origin in given units
            # TODO: Take into account that we've shifted up/over some number of tiles
            base_x = in_x - self.origin[0]
            base_y = in_y - self.origin[1]

            # Size of a pixel in given units
            unit_per_px = self.su_size / self.subcell_grid / subcell_size_px
            base_x_px = base_x / unit_per_px
            base_y_px = base_y / unit_per_px

            # Reset coordinate system
            x_coord = base_x_px
            y_coord = height_px - base_y_px

            # Location info
            (tile, su, subcell) = self.convert_xy(in_x, in_y)
            logging.debug(f"Drawing point {in_x}, {in_y} in {tile} at {x_coord}, {y_coord}")
            draw.circle([x_coord, y_coord], 10, color)


        return (img, grid)