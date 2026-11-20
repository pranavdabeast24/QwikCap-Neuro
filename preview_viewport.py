"""View-only page geometry shared by the native source viewers."""
from dataclasses import dataclass


@dataclass
class PreviewViewport:
    source_size: tuple[int, int] = (0, 0)
    viewport_size: tuple[int, int] = (1, 1)
    scale: float = 1.0
    fit_width: bool = True
    margin: int = 12

    @property
    def image_size(self):
        return tuple(max(1, round(value * self.scale)) for value in self.source_size)

    @property
    def content_size(self):
        return tuple(value + self.margin * 2 for value in self.image_size)

    def resize(self, size, origin):
        old_image = self.image_size
        self.viewport_size = tuple(max(1, int(value)) for value in size)
        if self.fit_width and self.source_size[0]:
            self.scale = max(.1, min(3.0, (self.viewport_size[0] - 2 * self.margin) / self.source_size[0]))
            return 0, self.margin + (origin[1] - self.margin) * self.image_size[1] / old_image[1]
        return origin

    def zoom(self, factor, anchor, origin):
        old_image = self.image_size
        point = tuple(origin[i] + anchor[i] for i in (0, 1))
        self.fit_width = False
        self.scale = max(.1, min(3.0, self.scale * factor))
        return self._anchor_origin(point, anchor, old_image)

    def fit(self, origin):
        self.fit_width = True
        old_image = self.image_size
        center = tuple(origin[i] + self.viewport_size[i] / 2 for i in (0, 1))
        if self.source_size[0]:
            self.scale = max(.1, min(3.0, (self.viewport_size[0] - 2 * self.margin) / self.source_size[0]))
        result = self._anchor_origin(center, tuple(value / 2 for value in self.viewport_size), old_image)
        return (0, result[1])

    def _anchor_origin(self, point, anchor, old_image):
        return tuple(self.margin + (point[i] - self.margin) * self.image_size[i] / old_image[i] - anchor[i]
                     for i in (0, 1))

    def rectangle(self, region):
        width, height = self.image_size
        x, y = self.margin + region["x"] * width, self.margin + region["y"] * height
        return x, y, x + region["width"] * width, y + region["height"] * height
