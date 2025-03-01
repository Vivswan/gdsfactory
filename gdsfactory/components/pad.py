from __future__ import annotations

import warnings
from functools import partial

import gdsfactory as gf
from gdsfactory import cell
from gdsfactory.component import Component
from gdsfactory.components.compass import compass
from gdsfactory.typings import ComponentFactory, Float2, LayerSpec


@cell
def pad(
    size: str | Float2 = (100.0, 100.0),
    layer: LayerSpec = "MTOP",
    bbox_layers: tuple[LayerSpec, ...] | None = None,
    bbox_offsets: tuple[float, ...] | None = None,
    port_inclusion: float = 0,
    port_orientation: float = 0,
) -> Component:
    """Returns rectangular pad with ports.

    Args:
        size: x, y size.
        layer: pad layer.
        bbox_layers: list of layers.
        bbox_offsets: Optional offsets for each layer with respect to size.
            positive grows, negative shrinks the size.
        port_inclusion: from edge.
        port_orientation: in degrees.
    """
    c = Component()
    layer = gf.get_layer(layer)
    size = gf.get_constant(size)
    rect = compass(
        size=size, layer=layer, port_inclusion=port_inclusion, port_type="electrical"
    )
    c_ref = c.add_ref(rect)
    c.add_ports(c_ref.ports)
    c.info["size"] = size
    c.info["xsize"] = size[0]
    c.info["ysize"] = size[1]

    if bbox_layers and bbox_offsets:
        sizes = []
        for cladding_offset in bbox_offsets:
            size = (size[0] + 2 * cladding_offset, size[1] + 2 * cladding_offset)
            sizes.append(size)

        for layer, size in zip(bbox_layers, sizes):
            c.add_ref(
                compass(
                    size=size,
                    layer=layer,
                )
            )

    width = size[1] if port_orientation in {0, 180} else size[0]

    c.add_port(
        name="pad",
        port_type="vertical_dc",
        layer=layer,
        center=(0, 0),
        orientation=port_orientation,
        width=width,
    )
    c.flatten()
    return c


pad_rectangular = partial(pad, size="pad_size")
pad_small = partial(pad, size=(80, 80))


@cell
def pad_array(
    pad: ComponentFactory = pad,
    spacing: tuple[float, float] = (150.0, 150.0),
    columns: int = 6,
    rows: int = 1,
    port_orientation: float = 0,
    orientation: float | None = None,
    size: Float2 = (100.0, 100.0),
    layer: LayerSpec = "MTOP",
) -> Component:
    """Returns 2D array of pads.

    Args:
        pad: pad element.
        spacing: x, y pitch.
        columns: number of columns.
        rows: number of rows.
        port_orientation: port orientation in deg. None for low speed DC ports.
        orientation: Deprecated, use port_orientation.
        size: pad size.
        layer: pad layer.
    """

    if orientation is not None:
        warnings.warn("orientation is deprecated, use port_orientation")
        port_orientation = orientation

    c = Component()
    pad = pad(size=size, port_orientation=port_orientation, layer=layer)

    c.add_array(pad, columns=columns, rows=rows, spacing=spacing)
    width = size[0] if port_orientation in {90, 270} else size[1]

    for col in range(columns):
        for row in range(rows):
            c.add_port(
                name=f"e{row+1}{col+1}",
                center=(col * spacing[0], row * spacing[1]),
                width=width,
                orientation=port_orientation,
                port_type="electrical",
                layer=layer,
            )
    return c


pad_array90 = partial(pad_array, port_orientation=90)
pad_array270 = partial(pad_array, port_orientation=270)

pad_array0 = partial(pad_array, port_orientation=0, columns=1, rows=3)
pad_array180 = partial(pad_array, port_orientation=180, columns=1, rows=3)


if __name__ == "__main__":
    # c = pad_rectangular()
    # c = pad()
    # c = pad(layer_to_inclusion={(3, 0): 10})
    # print(c.ports)
    # c = pad(width=10, height=10)
    # print(c.ports.keys())
    c = pad_array90()
    # c = pad_array0()
    # c = pad_array270()
    # c.pprint_ports()
    # c = pad_array_2d(cols=2, rows=3, port_names=("e2",))
    # c = pad_array(columns=2, rows=2, orientation=270)
    # c.auto_rename_ports()
    c.show()
