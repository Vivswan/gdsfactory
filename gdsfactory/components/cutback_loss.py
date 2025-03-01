from functools import partial

import numpy as np

import gdsfactory as gf
from gdsfactory.components.bend_euler import bend_euler, bend_euler180
from gdsfactory.components.cutback_bend import cutback_bend90, cutback_bend180
from gdsfactory.components.cutback_component import cutback_component
from gdsfactory.components.mmi1x2 import mmi1x2
from gdsfactory.components.spiral import spiral
from gdsfactory.typings import ComponentFactory, CrossSectionSpec


def cutback_loss(
    component: ComponentFactory = mmi1x2,
    cutback: ComponentFactory = cutback_component,
    loss: tuple[float, ...] = (1.0, 2.0, 3.0),
    loss_dB: float = 10e-3,
    cols: int | None = 4,
    rows: int | None = None,
    **kwargs,
) -> list[gf.Component]:
    """Returns a list of component cutbacks.

    Args:
        component: component factory.
        cutback: cutback function.
        loss: list of target loss in dB.
        loss_dB: loss per component.
        cols: number of columns.
        rows: number of rows.

    Keyword Args:
        port1: name of first optical port.
        port2: name of second optical port.
        bend180: ubend.
        mirror: Flips component. Useful when 'o2' is the port that you want to route to.
        mirror1: mirrors first component.
        mirror2: mirrors second component.
        straight_length: length of the straight section between cutbacks.
        straight_length_pair: length of the straight section between each component pair.
        cross_section: specification (CrossSection, string or dict).
        kwargs: component settings.

    """
    loss = np.array(list(loss))

    if rows and cols:
        raise ValueError("Specify either cols or rows")
    elif rows is None:
        rows_list = loss / loss_dB / cols
        rows_list = rows_list // 2 * 2 + 1
        return [
            cutback(component=component, rows=int(rows), cols=cols, **kwargs)
            for rows in rows_list
        ]
    elif cols is None:
        cols_list = loss / loss_dB / rows
        return [
            cutback(component=component, rows=rows, cols=int(cols), **kwargs)
            for cols in cols_list
        ]
    else:
        raise ValueError("Specify either cols or rows")


def cutback_loss_spirals(
    spiral: ComponentFactory = spiral,
    loss: tuple[float, ...] = tuple(4 + 3 * i for i in range(3)),
    cross_section: CrossSectionSpec = "xs_sc",
    loss_dB_per_m: float = 300,
    **kwargs,
) -> list[gf.Component]:
    """Returns a list of spirals.

    Args:
        spiral: spiral factory.
        loss: list of target loss in dB.
        cross_section: strip or rib.
        loss_dB_per_m: loss per meter.
        kwargs: additional spiral arguments.
    """
    lengths = [loss_dB / loss_dB_per_m * 1e6 for loss_dB in loss]
    return [
        spiral(length=length, cross_section=cross_section, **kwargs)
        for length in lengths
    ]


cutback_loss_mmi1x2 = partial(cutback_loss, component=mmi1x2, port2="o3", mirror2=True)
cutback_loss_bend90 = partial(
    cutback_loss, component=bend_euler, cutback=cutback_bend90, cols=12
)
cutback_loss_bend180 = partial(
    cutback_loss, component=bend_euler180, cutback=cutback_bend180, cols=12
)


if __name__ == "__main__":
    # components = cutback_loss_mmi1x2()
    # c = gf.pack(components)[0]
    # c = components[0]
    c = cutback_loss()[0]
    c.show()
