import logging

from pyscroll.common import Vector2D, Vector2DInt
from pyscroll.orthographic import BufferedRenderer
from pygame.surface import Surface

log = logging.getLogger(__file__)

## TODO:
# - read through whole class
# - read through orthographic class
# - keep notes on thoughts
# - consider renaming variables and such
#
## Wants:
# - camera-space posiiton
# - intuitive 0,0
# - non-single-tile-sized tile positions (TileOffset from tsx)
# - start using clamped camera from base class in center() (and for that to.. work.)

# Notes:
# Needs world_to_map, map_to_world
# Is it correct that I'm inheriting _calculate_zoom_buffer_size?
# The fact that I'm using the original version sugests that 
# I'm drawing 2x more tiles than I strictly have to.
# This might still be faster, though, 
# since making the selection itself may be more expensive


def vector3_to_iso(
    vector3: tuple[int, int, int], offset: tuple[int, int] = (0, 0)
) -> tuple[int, int]:
    """
    Convert 3D cartesian coordinates to isometric coordinates.
    """
    if len(vector3) != 3:
        raise ValueError("Input tuple must have exactly 3 elements")
    return (
        (vector3[0] - vector3[1]) + offset[0],
        ((vector3[0] + vector3[1]) >> 1) - vector3[2] + offset[1],
    )


def vector2_to_iso(
    vector2: tuple[int, int], offset: tuple[int, int] = (0, 0)
) -> tuple[int, int]:
    """
    Convert 2D cartesian coordinates to isometric coordinates.
    """
    if len(vector2) != 2:
        raise ValueError("Input tuple must have exactly 2 elements")
    return (
        (vector2[0] - vector2[1]) + offset[0],
        ((vector2[0] + vector2[1]) >> 1) + offset[1],
    )


class IsometricBufferedRenderer(BufferedRenderer):
    """TEST ISOMETRIC

    here be dragons.  lots of odd, untested, and unoptimised stuff.

    - coalescing of surfaces is not supported
    - drawing may have depth sorting issues
    - blits in _draw_surface()?
    
    """

    def _draw_surfaces(self, surface, rect, surfaces) -> None:
        if surfaces is not None:
            [(surface.blit(i[0], i[1]), i[2]) for i in surfaces]

    def _initialize_buffers(self, view_size: Vector2DInt) -> None:
        """Create the buffers to cache tile drawing

        :param view_size: (int, int): size of the draw area
        :return: None
        """
        import math

        from pygame import Rect

        tw, th = self.data.tile_size
        mw, mh = self.data.map_size
        buffer_tile_width = int(math.ceil(view_size[0] / tw) + 2) * 2
        buffer_tile_height = int(math.ceil(view_size[1] / th) + 2) * 2
        buffer_pixel_size = buffer_tile_width * tw, buffer_tile_height * th

        self.map_rect = Rect(0, 0, mw * tw, mh * th)
        self.view_rect.size = view_size
        self._tile_view = Rect(0, 0, buffer_tile_width, buffer_tile_height)
        self._redraw_cutoff = 1  # TODO: optimize this value
        self._create_buffers(view_size, buffer_pixel_size)
        self._half_width = view_size[0] // 2
        self._half_height = view_size[1] // 2
        self._x_offset = 0
        self._y_offset = 0

        self.redraw_tiles(self._buffer)

    def _flush_tile_queue(self, surface: Surface) -> None:
        """Blits (x, y, layer) tuples to buffer from iterator"""
        iterator = self._tile_queue
        surface_blit = self._buffer.blit
        # map_get = self._animation_map.get

        bw, bh = self._buffer.get_size()
        bw /= 2

        tw, th = self.data.tile_size
        twh = tw // 2
        thh = th // 2

        for x, y, l, tile in iterator:
            # tile = map_get(gid, tile)
            x -= self._tile_view.left
            y -= self._tile_view.top

            # iso => cart
            iso_x = ((x - y) * twh) + bw
            iso_y = (x + y) * thh
            surface_blit(tile, (iso_x, iso_y))

    def center(self, coords: Vector2D) -> None:
        """center the map on a "map pixel" """
        x, y = [round(i, 0) for i in coords]
        self.view_rect.center = x, y

        tw, th = self.data.tile_size

        left, ox = divmod(x, tw)
        top, oy = divmod(y, th)

        vec = int(ox / 2), int(oy)

        iso = vector2_to_iso(vec)
        self._x_offset = iso[0]
        self._y_offset = iso[1]

        assert self._buffer

        # center the buffer on the screen
        self._x_offset += (self._buffer.get_width() - self.view_rect.width) // 2
        self._y_offset += (self._buffer.get_height() - self.view_rect.height) // 4

        # adjust the view if the view has changed without a redraw
        dx = int(left - self._tile_view.left)
        dy = int(top - self._tile_view.top)
        view_change = max(abs(dx), abs(dy))

        # force redraw every time: edge queuing not supported yet
        self._redraw_cutoff = 0

        if view_change and (view_change <= self._redraw_cutoff):
            self._buffer.scroll(-dx * tw, -dy * th)
            self._tile_view.move_ip(dx, dy)
            self._queue_edge_tiles(dx, dy)
            self._flush_tile_queue()

        elif view_change > self._redraw_cutoff:
            # logger.info('scrolling too quickly.  redraw forced')
            self._tile_view.move_ip(dx, dy)
            self.redraw_tiles(self._buffer)

    # def redraw_tiles(self):
    #     """ redraw the visible portion of the buffer -- it is slow.
    #     """
    #     if self._clear_color:
    #         self._buffer.fill(self._clear_color)
    #
    #     v = self._tile_view
    #     self._tile_queue = []
    #     for x in range(v.left, v.right):
    #         for y in range(v.top, v.bottom):
    #             ix, iy = vector2_to_iso((x, y))
    #             tile = self.data.get_tile_image((ix, iy, 0))
    #             if tile:
    #                 self._tile_queue.append((x, y, 0, tile, 0))
    #                 print((x, y), (ix, iy))
    #
    #     self._flush_tile_queue()
