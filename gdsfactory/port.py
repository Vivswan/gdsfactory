"""We use Ports to connect Components with other Components.

we follow start from the bottom left and name the ports counter-clock-wise

.. code::

         3   4
         |___|_
     2 -|      |- 5
        |      |
     1 -|______|- 6
         |   |
         8   7

You can also rename them with W,E,S,N prefix (west, east, south, north).

    .. code::

             N0  N1
             |___|_
        W1 -|      |- E1
            |      |
        W0 -|______|- E0
             |   |
            S0   S1

Adapted from PHIDL https://github.com/amccaugh/phidl/ by Adam McCaughan
"""

from __future__ import annotations

import csv
import functools
import typing
import warnings
from collections.abc import Callable
from functools import partial

import kfactory as kf
import numpy as np
from rich.console import Console
from rich.table import Table

from gdsfactory.cross_section import CrossSectionSpec

if typing.TYPE_CHECKING:
    from gdsfactory.component import Component

Layer = tuple[int, int]
Layers = tuple[Layer, ...]
LayerSpec = Layer | str | None | kf.LayerEnum
LayerSpecs = tuple[LayerSpec, ...]
Float2 = tuple[float, float]
valid_error_types = ["error", "warn", "ignore"]


class PortNotOnGridError(ValueError):
    pass


class PortTypeError(ValueError):
    pass


class PortOrientationError(ValueError):
    pass


def pprint_ports(ports: list[Port] | kf.Ports) -> None:
    """Prints ports in a rich table."""
    console = Console()
    table = Table(show_header=True, header_style="bold")

    keys = ["name", "width", "orientation", "layer", "center", "port_type"]

    for key in keys:
        table.add_column(key)

    for port in ports:
        row = [
            str(i)
            for i in [
                port.name,
                port.d.width,
                port.d.angle,
                port.layer,
                port.d.center,
                port.port_type,
            ]
        ]
        table.add_row(*row)

    console.print(table)


class Port(kf.Port):
    """Ports are useful to connect Components with each other.

    Args:
        name: we name ports clock-wise starting from bottom left.
        center: (x, y) port center coordinate.
        width: of the port in um.
        orientation: in degrees (0: east, 90: north, 180: west, 270: south).
        parent: parent component (component to which this port belong to).
        layer: layer tuple.
        port_type: str (optical, electrical, vertical_te, vertical_tm).
        parent: Component that port belongs to.
        cross_section: cross_section spec.
    """

    def __init__(
        self,
        name: str,
        orientation: float | None,
        center: tuple[float, float] | kf.kdb.Point | kf.kdb.DPoint,
        width: float,
        layer: LayerSpec | None = None,
        port_type: str = "optical",
        cross_section: CrossSectionSpec | None = None,
        info: dict[str, int | float | str] | None = None,
    ) -> None:
        from gdsfactory.pdk import get_layer

        orientation = np.mod(orientation, 360) if orientation else orientation

        if cross_section is None and layer is None:
            raise ValueError("You need to define Port cross_section or layer")

        if cross_section is None and width is None:
            raise ValueError("You need Port to define cross_section or width")

        if layer is None or width is None:
            from gdsfactory.pdk import get_cross_section

            cross_section = get_cross_section(cross_section)

        if cross_section and layer is None:
            layer = cross_section.layer

        if isinstance(layer, list):
            layer = tuple(layer)

        if width is None:
            width = cross_section.width

        if width < 0:
            raise ValueError(f"Port width must be >=0. Got {width}")

        dcplx_trans = kf.kdb.DCplxTrans(1.0, float(orientation), False, *center)
        info = info or {}
        super().__init__(
            name=name,
            layer=get_layer(layer),
            dwidth=width,
            port_type=port_type,
            dcplx_trans=dcplx_trans,
            info=info,
        )

    @classmethod
    def __get_validators__(cls):
        """Get validators."""
        yield cls.validate

    @classmethod
    def validate(cls, v, _info):
        """For pydantic assumes Port is valid if has a name and a valid type."""
        assert isinstance(v, Port), f"TypeError, Got {type(v)}, expecting Port"
        assert v.name, f"Port has no name, got {v.name!r}"
        # assert v.assert_on_grid(), f"port.center = {v.center} has off-grid points"
        return v


def to_dict(port: Port) -> dict[str, typing.Any]:
    """Returns dict."""
    return {
        "name": port.name,
        "center": port.d.center,
        "width": port.width,
        "orientation": port.orientation,
        "layer": port.layer,
        "port_type": port.port_type,
    }


PortsMap = dict[str, list[Port]]


def port_array(
    center: tuple[float, float] = (0.0, 0.0),
    width: float = 0.5,
    orientation: float = 0,
    pitch: tuple[float, float] = (10.0, 0.0),
    n: int = 2,
    **kwargs,
) -> list[Port]:
    """Returns a list of ports placed in an array.

    Args:
        center: center point of the port.
        width: port width.
        orientation: angle in degrees.
        pitch: period of the port array.
        n: number of ports in the array.

    """
    pitch = np.array(pitch)
    return [
        Port(
            name=str(i),
            width=width,
            center=np.array(center) + i * pitch - (n - 1) / 2 * pitch,
            orientation=orientation,
            **kwargs,
        )
        for i in range(n)
    ]


def read_port_markers(component: object, layers: LayerSpecs = ("PORT",)) -> Component:
    """Returns extracted polygons from component layers.

    Args:
        component: Component to extract markers.
        layers: GDS layer specs.

    """
    from gdsfactory.pdk import get_layer

    layers = [get_layer(layer) for layer in layers]
    return component.extract(layers=layers)


def csv2port(csvpath) -> dict[str, Port]:
    """Reads ports from a CSV file and returns a Dict."""
    ports = {}
    with open(csvpath) as csvfile:
        rows = csv.reader(csvfile, delimiter=",", quotechar="|")
        for row in rows:
            ports[row[0]] = row[1:]

    return ports


def sort_ports_clockwise(ports: kf.Ports) -> kf.Ports:
    """Sort and return ports in the clockwise direction.

    .. code::

            3   4
            |___|_
        2 -|      |- 5
           |      |
        1 -|______|- 6
            |   |
            8   7

    """
    port_list = ports
    direction_ports: PortsMap = {x: [] for x in ["E", "N", "W", "S"]}

    for p in port_list:
        angle = p.angle * 90
        if angle <= 45 or angle >= 315:
            direction_ports["E"].append(p)
        elif angle <= 135 and angle >= 45:
            direction_ports["N"].append(p)
        elif angle <= 225 and angle >= 135:
            direction_ports["W"].append(p)
        else:
            direction_ports["S"].append(p)

    east_ports = direction_ports["E"]
    east_ports.sort(key=lambda p: -p.y)  # sort north to south

    north_ports = direction_ports["N"]
    north_ports.sort(key=lambda p: +p.x)  # sort west to east

    west_ports = direction_ports["W"]
    west_ports.sort(key=lambda p: +p.y)  # sort south to north

    south_ports = direction_ports["S"]
    south_ports.sort(key=lambda p: -p.x)  # sort east to west

    ports = west_ports + north_ports + east_ports + south_ports
    return list(ports)


def sort_ports_counter_clockwise(ports: kf.Ports) -> kf.Ports:
    """Sort and return ports in the counter-clockwise direction.

    .. code::

            4   3
            |___|_
        5 -|      |- 2
           |      |
        6 -|______|- 1
            |   |
            7   8

    """
    port_list = list(ports)
    direction_ports: PortsMap = {x: [] for x in ["E", "N", "W", "S"]}

    for p in port_list:
        angle = p.angle * 90
        if angle <= 45 or angle >= 315:
            direction_ports["E"].append(p)
        elif angle <= 135 and angle >= 45:
            direction_ports["N"].append(p)
        elif angle <= 225 and angle >= 135:
            direction_ports["W"].append(p)
        else:
            direction_ports["S"].append(p)

    east_ports = direction_ports["E"]
    east_ports.sort(key=lambda p: +p.y)  # sort south to north

    north_ports = direction_ports["N"]
    north_ports.sort(key=lambda p: -p.x)  # sort east to west

    west_ports = direction_ports["W"]
    west_ports.sort(key=lambda p: -p.y)  # sort north to south

    south_ports = direction_ports["S"]
    south_ports.sort(key=lambda p: +p.x)  # sort west to east

    ports = east_ports + north_ports + west_ports + south_ports
    return list(ports)


def select_ports(
    ports: kf.Ports | kf.Instance,
    layer: LayerSpec | None = None,
    prefix: str | None = None,
    suffix: str | None = None,
    orientation: int | None = None,
    width: float | None = None,
    layers_excluded: tuple[tuple[int, int], ...] | None = None,
    port_type: str | None = None,
    names: list[str] | None = None,
    clockwise: bool = True,
    sort_ports: bool = False,
) -> list[kf.Port]:
    """Returns a dict of ports from a list of ports.

    Args:
        ports: port list.
        layer: select ports with port GDS layer.
        prefix: select ports with port name prefix.
        suffix: select ports with port name suffix.
        orientation: select ports with orientation in degrees.
        width: select ports with port width.
        layers_excluded: List of layers to exclude.
        port_type: select ports with port type (optical, electrical, vertical_te).
        clockwise: if True, sort ports clockwise, False: counter-clockwise.
        sort_ports: if True, sort ports.

    Returns:
        Dict containing the selected ports {port name: port}.

    """
    if isinstance(ports, dict):
        ports = ports.values()

    if isinstance(ports, kf.Instance):
        ports = ports.ports

    if layer:
        from gdsfactory.pdk import get_layer

        layer = get_layer(layer)
        ports = [p for p in ports if get_layer(p.layer) == layer]

    if prefix:
        ports = [p for p in ports if p.name.startswith(prefix)]
    if suffix:
        ports = [p for p in ports if p.name.endswith(suffix)]
    if orientation is not None:
        ports = [p for p in ports if np.isclose(p.d.angle, orientation)]

    if layers_excluded:
        ports = [p for p in ports if p.layer not in layers_excluded]
    if width:
        ports = [p for p in ports if p.width == width]
    if port_type:
        ports = [p for p in ports if p.port_type == port_type]
    if names:
        ports = [p for p in ports if p.name in names]

    if sort_ports:
        if clockwise:
            ports = sort_ports_clockwise(ports)
        else:
            ports = sort_ports_counter_clockwise(ports)
    return ports


select_ports_optical = partial(select_ports, port_type="optical")
select_ports_electrical = partial(select_ports, port_type="electrical")
select_ports_placement = partial(select_ports, port_type="placement")


def select_ports_list(ports: kf.Ports | kf.Instance, **kwargs) -> kf.Ports:
    return select_ports(ports=ports, **kwargs)


get_ports_list = select_ports_list


def flipped(port: Port) -> Port:
    if port.orientation is None:
        raise ValueError(f"port {port.name!r} has None orientation")
    p = port.copy()
    p.trans *= kf.kdb.Trans.R180
    return p


def move_copy(port, x: int = 0, y: int = 0) -> Port:
    warnings.warn(
        "Port.move_copy(...) should be used instead of move_copy(Port, ...).",
    )
    _port = port.copy()
    _port.center += (x, y)
    return _port


def get_ports_facing(ports: list[Port], direction: str = "W") -> list[Port]:
    from gdsfactory.component import Component, ComponentReference

    valid_directions = ["E", "N", "W", "S"]

    if direction not in valid_directions:
        raise PortOrientationError(f"{direction} must be in {valid_directions} ")

    if isinstance(ports, dict):
        ports = list(ports)
    elif isinstance(ports, Component | ComponentReference):
        ports = list(ports.ports)

    direction_ports: dict[str, list[Port]] = {x: [] for x in ["E", "N", "W", "S"]}

    for p in ports:
        angle = p.orientation % 360 if p.orientation is not None else 0
        if angle <= 45 or angle >= 315:
            direction_ports["E"].append(p)
        elif angle <= 135 and angle >= 45:
            direction_ports["N"].append(p)
        elif angle <= 225 and angle >= 135:
            direction_ports["W"].append(p)
        else:
            direction_ports["S"].append(p)

    return direction_ports[direction]


def deco_rename_ports(component_factory: Callable) -> Callable:
    @functools.wraps(component_factory)
    def auto_named_component_factory(*args, **kwargs):
        component = component_factory(*args, **kwargs)
        auto_rename_ports(component)
        return component

    return auto_named_component_factory


def _rename_ports_facing_side(
    direction_ports: dict[str, list[Port]], prefix: str = ""
) -> None:
    """Renames ports clockwise."""
    for direction, list_ports in list(direction_ports.items()):
        if direction in ["E", "W"]:
            # first sort along x then y
            list_ports.sort(key=lambda p: p.x)
            list_ports.sort(key=lambda p: p.y)

        if direction in ["S", "N"]:
            # first sort along y then x
            list_ports.sort(key=lambda p: p.y)
            list_ports.sort(key=lambda p: p.x)

        for i, p in enumerate(list_ports):
            p.name = prefix + direction + str(i)


def _rename_ports_facing_side_ccw(
    direction_ports: dict[str, list[Port]], prefix: str = ""
) -> None:
    """Renames ports counter-clockwise."""
    for direction, list_ports in list(direction_ports.items()):
        if direction in ["E", "W"]:
            # first sort along x then y
            list_ports.sort(key=lambda p: -p.x)
            list_ports.sort(key=lambda p: -p.y)

        if direction in ["S", "N"]:
            # first sort along y then x
            list_ports.sort(key=lambda p: -p.y)
            list_ports.sort(key=lambda p: -p.x)

        for i, p in enumerate(list_ports):
            p.name = prefix + direction + str(i)


def _rename_ports_counter_clockwise(direction_ports, prefix="") -> None:
    east_ports = direction_ports["E"]
    east_ports.sort(key=lambda p: +p.y)  # sort south to north

    north_ports = direction_ports["N"]
    north_ports.sort(key=lambda p: -p.x)  # sort east to west

    west_ports = direction_ports["W"]
    west_ports.sort(key=lambda p: -p.y)  # sort north to south

    south_ports = direction_ports["S"]
    south_ports.sort(key=lambda p: +p.x)  # sort west to east

    ports = east_ports + north_ports + west_ports + south_ports

    for i, p in enumerate(ports):
        p.name = f"{prefix}{i+1}" if prefix else i + 1


def _rename_ports_clockwise(direction_ports: PortsMap, prefix: str = "") -> None:
    """Rename ports in the clockwise direction starting from the bottom left \
    (west) corner."""
    east_ports = direction_ports["E"]
    east_ports.sort(key=lambda p: -p.y)  # sort north to south

    north_ports = direction_ports["N"]
    north_ports.sort(key=lambda p: +p.x)  # sort west to east

    west_ports = direction_ports["W"]
    west_ports.sort(key=lambda p: +p.y)  # sort south to north

    south_ports = direction_ports["S"]
    south_ports.sort(key=lambda p: -p.x)  # sort east to west
    # south_ports.sort(key=lambda p: p.y)  #  south first

    ports = west_ports + north_ports + east_ports + south_ports

    for i, p in enumerate(ports):
        p.name = f"{prefix}{i+1}" if prefix else i + 1


def _rename_ports_clockwise_top_right(
    direction_ports: PortsMap, prefix: str = ""
) -> None:
    """Rename ports in the clockwise direction starting from the top right \
    corner."""
    east_ports = direction_ports["E"]
    east_ports.sort(key=lambda p: -p.y)  # sort north to south

    north_ports = direction_ports["N"]
    north_ports.sort(key=lambda p: +p.x)  # sort west to east

    west_ports = direction_ports["W"]
    west_ports.sort(key=lambda p: +p.y)  # sort south to north

    south_ports = direction_ports["S"]
    south_ports.sort(key=lambda p: -p.x)  # sort east to west

    ports = east_ports + south_ports + west_ports + north_ports

    for i, p in enumerate(ports):
        p.name = f"{prefix}{i+1}" if prefix else i + 1


def rename_ports_by_orientation(
    component: Component,
    layers_excluded: LayerSpec | None = None,
    select_ports: Callable = select_ports,
    function=_rename_ports_facing_side,
    prefix: str = "o",
    **kwargs,
) -> Component:
    """Returns Component with port names based on port orientation (E, N, W, S).

    Args:
        component: to rename ports.
        layers_excluded: to exclude.
        select_ports: function to select_ports.
        function: to rename ports.
        prefix: to add on each port name.
        kwargs: select_ports settings.

    .. code::

             N0  N1
             |___|_
        W1 -|      |- E1
            |      |
        W0 -|______|- E0
             |   |
            S0   S1

    """
    layers_excluded = layers_excluded or []
    direction_ports: PortsMap = {x: [] for x in ["E", "N", "W", "S"]}

    ports = component.ports
    ports = select_ports(ports, **kwargs)

    ports_on_layer = [p for p in ports if p.layer not in layers_excluded]

    for p in ports_on_layer:
        # Make sure we can backtrack the parent component from the port
        p.parent = component

        if p.orientation is not None:
            angle = p.orientation % 360
            if angle <= 45 or angle >= 315:
                direction_ports["E"].append(p)
            elif angle <= 135 and angle >= 45:
                direction_ports["N"].append(p)
            elif angle <= 225 and angle >= 135:
                direction_ports["W"].append(p)
            else:
                direction_ports["S"].append(p)
        else:
            direction_ports["S"].append(p)

    function(direction_ports, prefix=prefix)
    return component


def auto_rename_ports(
    component: Component,
    function=_rename_ports_clockwise,
    select_ports_optical: Callable | None = select_ports_optical,
    select_ports_electrical: Callable | None = select_ports_electrical,
    select_ports_placement: Callable | None = select_ports_placement,
    prefix: str = "",
    prefix_optical: str = "o",
    prefix_electrical: str = "e",
    prefix_placement: str = "p",
    port_type: str | None = None,
    **kwargs,
) -> Component:
    """Adds prefix for optical and electrical.

    Args:
        component: to auto_rename_ports.
        function: to rename ports.
        select_ports_optical: to select optical ports.
        select_ports_electrical: to select electrical ports.
        select_ports_placement: to select placement ports.
        prefix_optical: prefix of optical ports.
        prefix_electrical: prefix of electrical ports.
        prefix_placement: prefix of electrical ports.
        port_type: select ports with port type (optical, electrical, vertical_te).

    Keyword Args:
        prefix: select ports with port name prefix.
        suffix: select ports with port name suffix.
        orientation: select ports with orientation in degrees.
        width: select ports with port width.
        layers_excluded: List of layers to exclude.
        clockwise: if True, sort ports clockwise, False: counter-clockwise.

    """
    if port_type is None:
        if select_ports_optical:
            rename_ports_by_orientation(
                component=component,
                select_ports=select_ports_optical,
                prefix=prefix_optical,
                function=function,
                **kwargs,
            )
        if select_ports_electrical:
            rename_ports_by_orientation(
                component=component,
                select_ports=select_ports_electrical,
                prefix=prefix_electrical,
                function=function,
                **kwargs,
            )
        if select_ports_placement:
            rename_ports_by_orientation(
                component=component,
                select_ports=select_ports_placement,
                prefix=prefix_placement,
                function=function,
                **kwargs,
            )
    else:
        rename_ports_by_orientation(
            component=component,
            select_ports=select_ports,
            prefix=prefix,
            function=function,
            port_type=port_type,
            **kwargs,
        )
    return component


auto_rename_ports_counter_clockwise = partial(
    auto_rename_ports, function=_rename_ports_counter_clockwise
)
auto_rename_ports_orientation = partial(
    auto_rename_ports, function=_rename_ports_facing_side
)

auto_rename_ports_electrical = partial(auto_rename_ports, select_ports_optical=None)


def map_ports_layer_to_orientation(
    ports: dict[str, Port], function=_rename_ports_facing_side
) -> dict[str, str]:
    """Returns component or reference port mapping.

    .. code::

             N0  N1
             |___|_
        W1 -|      |- E1
            |      |
        W0 -|______|- E0
             |   |
            S0   S1

    """
    m = {}
    direction_ports: PortsMap = {x: [] for x in ["E", "N", "W", "S"]}
    layers = {port.layer for port in ports}

    for layer in layers:
        ports_on_layer = [p.copy() for p in ports if p.layer == layer]

        for p in ports_on_layer:
            p.name_original = p.name
            if p.orientation:
                angle = p.orientation % 360
                if angle <= 45 or angle >= 315:
                    direction_ports["E"].append(p)
                elif angle <= 135 and angle >= 45:
                    direction_ports["N"].append(p)
                elif angle <= 225 and angle >= 135:
                    direction_ports["W"].append(p)
                else:
                    direction_ports["S"].append(p)
        function(direction_ports, prefix=f"{layer[0]}_{layer[1]}_")
        m |= {p.name: p.name_original for p in ports_on_layer}
    return m


def map_ports_to_orientation_cw(
    ports: dict[str, Port], function=_rename_ports_facing_side, **kwargs
) -> dict[str, str]:
    """Returns component or reference port mapping clockwise.

    Args:
        ports: dict of ports.
        function: to rename ports.
        kwargs: for the function to rename ports.


    .. code::

             N0  N1
             |___|_
        W1 -|      |- E1
            |      |
        W0 -|______|- E0
             |   |
            S0   S1

    """
    direction_ports: PortsMap = {x: [] for x in ["E", "N", "W", "S"]}

    ports = select_ports(ports, **kwargs)
    ports_on_layer = [p.copy() for p in ports]

    for p in ports_on_layer:
        p.name_original = p.name
        angle = p.orientation % 360
        if angle <= 45 or angle >= 315:
            direction_ports["E"].append(p)
        elif angle <= 135 and angle >= 45:
            direction_ports["N"].append(p)
        elif angle <= 225 and angle >= 135:
            direction_ports["W"].append(p)
        else:
            direction_ports["S"].append(p)
    function(direction_ports)
    return {p.name: p.name_original for p in ports_on_layer}


map_ports_to_orientation_ccw = partial(
    map_ports_to_orientation_cw, function=_rename_ports_facing_side_ccw
)


def auto_rename_ports_layer_orientation(
    component: Component,
    function=_rename_ports_facing_side,
) -> None:
    """Renames port names with layer_orientation  (1_0_W0).

    port orientation (E, N, W, S) numbering is clockwise

    .. code::

             N0  N1
             |___|_
        W1 -|      |- E1
            |      |
        W0 -|______|- E0
             |   |
            S0   S1

    """
    new_ports = {}
    ports = component.ports
    direction_ports: PortsMap = {x: [] for x in ["E", "N", "W", "S"]}
    layers = {port.layer for port in ports}

    for layer in layers:
        ports_on_layer = [p for p in ports if p.layer == layer]

        for p in ports_on_layer:
            p.name_original = p.name
            angle = p.orientation % 360
            if angle <= 45 or angle >= 315:
                direction_ports["E"].append(p)
            elif angle <= 135 and angle >= 45:
                direction_ports["N"].append(p)
            elif angle <= 225 and angle >= 135:
                direction_ports["W"].append(p)
            else:
                direction_ports["S"].append(p)

        function(direction_ports, prefix=f"{layer[0]}_{layer[1]}_")
        new_ports |= {p.name: p for p in ports_on_layer}


__all__ = [
    "Port",
    "port_array",
    "read_port_markers",
    "csv2port",
    "select_ports",
    "select_ports_list",
    "flipped",
    "move_copy",
    "get_ports_facing",
    "deco_rename_ports",
    "rename_ports_by_orientation",
    "auto_rename_ports",
    "auto_rename_ports_counter_clockwise",
    "auto_rename_ports_orientation",
    "map_ports_layer_to_orientation",
]

if __name__ == "__main__":
    import gdsfactory as gf

    c = gf.c.mzi()
    p = c.ports["o1"]
    d = gf.port.to_dict(p)
    print(d)
    c.show()
