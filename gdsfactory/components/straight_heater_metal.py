from __future__ import annotations

from functools import partial

import gdsfactory as gf
from gdsfactory import cell
from gdsfactory.component import Component
from gdsfactory.typings import ComponentSpec, CrossSectionSpec


@cell
def straight_heater_metal_undercut(
    length: float = 320.0,
    length_undercut_spacing: float = 6.0,
    length_undercut: float = 30.0,
    length_straight: float = 0.1,
    length_straight_input: float = 15.0,
    cross_section: CrossSectionSpec = "xs_sc",
    cross_section_heater: CrossSectionSpec = "xs_heater_metal",
    cross_section_waveguide_heater: CrossSectionSpec = "xs_sc_heater_metal",
    cross_section_heater_undercut: CrossSectionSpec = "xs_sc_heater_metal_undercut",
    with_undercut: bool = True,
    via_stack: ComponentSpec | None = "via_stack_heater_mtop",
    port_orientation1: int | None = None,
    port_orientation2: int | None = None,
    heater_taper_length: float | None = 5.0,
    ohms_per_square: float | None = None,
) -> Component:
    """Returns a thermal phase shifter.

    dimensions from https://doi.org/10.1364/OE.27.010456

    Args:
        length: of the waveguide.
        length_undercut_spacing: from undercut regions.
        length_undercut: length of each undercut section.
        length_straight_input: from input port to where trenches start.
        cross_section_heater: for heated sections. heater metal only.
        cross_section_waveguide_heater: for heated sections.
        cross_section_heater_undercut: for heated sections with undercut.
        with_undercut: isolation trenches for higher efficiency.
        via_stack: via stack.
        port_orientation1: left via stack port orientation.
        port_orientation2: right via stack port orientation.
        heater_taper_length: minimizes current concentrations from heater to via_stack.
        ohms_per_square: to calculate resistance.
        cross_section: for waveguide ports.
    """
    period = length_undercut + length_undercut_spacing
    n = int((length - 2 * length_straight_input) // period)

    length_straight_input = (length - n * period) / 2

    if n < 1:
        raise ValueError("length is too short")

    if length_straight > length_straight_input:
        raise ValueError("length_straight_ must be smaller than length_straight_input")

    length_straight_input -= length_straight

    s_ports = gf.components.straight(
        cross_section=cross_section,
        length=length_straight,
    )

    s_si = gf.components.straight(
        cross_section=cross_section_waveguide_heater,
        length=length_straight_input,
    )
    cross_section_undercut = (
        cross_section_heater_undercut
        if with_undercut
        else cross_section_waveguide_heater
    )
    s_uc = gf.components.straight(
        cross_section=cross_section_undercut,
        length=length_undercut,
    )
    s_spacing = gf.components.straight(
        cross_section=cross_section_waveguide_heater,
        length=length_undercut_spacing,
    )
    symbol_to_component = {
        "_": (s_ports, "o1", "o2"),
        "-": (s_si, "o1", "o2"),
        "U": (s_uc, "o1", "o2"),
        "H": (s_spacing, "o1", "o2"),
    }

    # Each character in the sequence represents a component
    sequence = "_-" + n * "UH" + "-_"

    c = Component()
    sequence = gf.components.component_sequence(
        sequence=sequence, symbol_to_component=symbol_to_component
    )
    c.add_ref(sequence)
    c.add_ports(sequence.ports)

    x = gf.get_cross_section(cross_section_heater)
    heater_width = x.width

    if via_stack:
        via_stack = gf.get_component(via_stack)
        dx = via_stack.d.xsize / 2 + heater_taper_length or 0
        dx -= length_straight

        via_stack_west = c << via_stack
        via_stack_east = c << via_stack

        via_stack_west.d.movex(-dx)
        via_stack_east.d.movex(+dx + length)

        valid_orientations = {p.orientation for p in via_stack.ports}
        p1 = list(via_stack_west.ports.filter(orientation=port_orientation1))
        p2 = list(via_stack_east.ports.filter(orientation=port_orientation2))

        if not p1:
            raise ValueError(
                f"No ports for port_orientation1 {port_orientation1} in {valid_orientations}"
            )
        if not p2:
            raise ValueError(
                f"No ports for port_orientation2 {port_orientation2} in {valid_orientations}"
            )

        c.add_ports(p1, prefix="l_")
        c.add_ports(p2, prefix="r_")

        if heater_taper_length:
            taper = gf.components.taper(
                width1=p1[0].width * c.kcl.dbu,
                width2=heater_width,
                length=heater_taper_length,
                cross_section=x,
                port_names=("e1", "e2"),
                port_types=("electrical", "electrical"),
            )
            taper1 = c << taper
            taper2 = c << taper
            taper1.connect("e1", via_stack_west.ports["e3"], allow_layer_mismatch=True)
            taper2.connect("e1", via_stack_east.ports["e1"], allow_layer_mismatch=True)

    c.info["resistance"] = (
        ohms_per_square * heater_width * length if ohms_per_square else 0
    )
    return c


@cell
def straight_heater_metal_simple(
    length: float = 320.0,
    cross_section_heater: CrossSectionSpec = "xs_heater_metal",
    cross_section_waveguide_heater: CrossSectionSpec = "xs_sc_heater_metal",
    via_stack: ComponentSpec | None = "via_stack_heater_mtop",
    port_orientation1: int | None = None,
    port_orientation2: int | None = None,
    heater_taper_length: float | None = 5.0,
    ohms_per_square: float | None = None,
) -> Component:
    """Returns a thermal phase shifter that has properly fixed electrical connectivity to extract a suitable electrical netlist and models.
    dimensions from https://doi.org/10.1364/OE.27.010456

    Args:
        length: of the waveguide.
        length_undercut_spacing: from undercut regions.
        length_undercut: length of each undercut section.
        cross_section_heater: for heated sections. heater metal only.
        cross_section_waveguide_heater: for heated sections.
        cross_section_heater_undercut: for heated sections with undercut.
        with_undercut: isolation trenches for higher efficiency.
        via_stack: via stack.
        port_orientation1: left via stack port orientation.
        port_orientation2: right via stack port orientation.
        heater_taper_length: minimizes current concentrations from heater to via_stack.
        ohms_per_square: to calculate resistance.
        cross_section: for waveguide ports.
    """
    c = Component()
    straight_heater_section = gf.components.straight(
        cross_section=cross_section_waveguide_heater,
        length=length,
    )

    c.add_ref(straight_heater_section)
    c.add_ports(straight_heater_section.ports)
    x = gf.get_cross_section(cross_section_heater)
    heater_width = x.width

    if via_stack:
        via = via_stackw = via_stacke = gf.get_component(via_stack)
        dx = via_stackw.d.xsize / 2 + heater_taper_length or 0
        via_stack_west_center = (
            straight_heater_section.d.xmin - dx,
            straight_heater_section.d.y,
        )
        via_stack_east_center = (
            straight_heater_section.d.xmax + dx,
            straight_heater_section.d.y,
        )

        via_stack_west = c << via_stackw
        via_stack_east = c << via_stacke
        via_stack_west.d.move(via_stack_west_center)
        via_stack_east.d.move(via_stack_east_center)

        valid_orientations = {p.orientation for p in via.ports}
        p1 = via_stack_west.ports.filter(orientation=port_orientation1)
        p2 = via_stack_east.ports.filter(orientation=port_orientation2)

        if not p1:
            raise ValueError(
                f"No ports for port_orientation1 {port_orientation1} in {valid_orientations}"
            )
        if not p2:
            raise ValueError(
                f"No ports for port_orientation2 {port_orientation2} in {valid_orientations}"
            )

        # c.add_ports(p1, prefix="l_")
        # c.add_ports(p2, prefix="r_")
        if heater_taper_length:
            taper = gf.components.taper(
                width1=via_stackw.ports["e1"].d.width,
                width2=heater_width,
                length=heater_taper_length,
                cross_section=x,
                port_names=("e1", "e2"),
                port_types=("electrical", "electrical"),
            )
            taper1 = c << taper
            taper2 = c << taper
            taper1.connect("e1", via_stack_west.ports["e3"], allow_layer_mismatch=True)
            taper2.connect("e1", via_stack_east.ports["e1"], allow_layer_mismatch=True)

    c.info["resistance"] = (
        ohms_per_square * heater_width * length if ohms_per_square else None
    )
    return c


straight_heater_metal = partial(
    straight_heater_metal_undercut,
    with_undercut=False,
    length_straight_input=0.1,
    length_undercut=5,
    length_undercut_spacing=0,
)
straight_heater_metal_90_90 = partial(
    straight_heater_metal,
    port_orientation1=90,
    port_orientation2=90,
)
straight_heater_metal_undercut_90_90 = partial(
    straight_heater_metal_undercut,
    port_orientation1=90,
    port_orientation2=90,
)


def test_ports() -> None:
    c = straight_heater_metal(length=50.0)
    assert c.ports["o2"].d.center[0] == 50.0, c.ports["o2"].d.center[0]


if __name__ == "__main__":
    # test_ports()
    c = straight_heater_metal()
    # print(c.ports['o2'].center[0])
    # c.pprint_ports()
    # c = straight_heater_metal(heater_width=5, length=50.0)

    # c = straight_heater_metal_undercut(length=200)
    # n = c.get_netlist()
    # c = straight_heater_metal(length=20)
    # c = straight_heater_metal_90_90(length=50)
    c.show()
    # scene = c.to_3d()
    # scene.show()
