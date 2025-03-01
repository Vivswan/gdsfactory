from __future__ import annotations

from functools import partial

import numpy as np

import gdsfactory as gf
from gdsfactory.component import Component
from gdsfactory.components.straight import straight
from gdsfactory.components.wire import wire_corner
from gdsfactory.cross_section import strip
from gdsfactory.path import euler
from gdsfactory.typings import CrossSectionSpec


@gf.cell
def bend_euler(
    radius: float | None = None,
    angle: float = 90.0,
    p: float = 0.5,
    with_arc_floorplan: bool = True,
    npoints: int | None = None,
    layer: gf.typings.LayerSpec | None = None,
    width: float | None = None,
    direction: str = "ccw",
    cross_section: CrossSectionSpec = "xs_sc",
    allow_min_radius_violation: bool = False,
) -> Component:
    """Euler bend with changing bend radius.

    By default, `radius` corresponds to the minimum radius of curvature of the bend.
    However, if `with_arc_floorplan` is True, `radius` corresponds to the effective
    radius of curvature (making the curve a drop-in replacement for an arc). If
    p < 1.0, will create a "partial euler" curve as described in Vogelbacher et.
    al. https://dx.doi.org/10.1364/oe.27.031394

    default p = 0.5 based on this paper
    https://www.osapublishing.org/oe/fulltext.cfm?uri=oe-25-8-9150&id=362937

    Args:
        radius: in um. Defaults to cross_section_radius.
        angle: total angle of the curve.
        p: Proportion of the curve that is an Euler curve.
        with_arc_floorplan: If False: `radius` is the minimum radius of curvature
          If True: The curve scales such that the endpoints match a bend_circular
          with parameters `radius` and `angle`.
        npoints: Number of points used per 360 degrees.
        layer: layer to use. Defaults to cross_section.layer.
        width: width to use. Defaults to cross_section.width.
        direction: cw (clock-wise) or ccw (counter clock-wise).
        cross_section: specification (CrossSection, string, CrossSectionFactory dict).
        allow_min_radius_violation: if True allows radius to be smaller than cross_section radius.

    .. code::

                  o2
                  |
                 /
                /
               /
       o1_____/
    """
    x = gf.get_cross_section(cross_section)
    radius = radius or x.radius

    if radius is None:
        return wire_corner(cross_section=x)

    if layer or width:
        x = x.copy(layer=layer or x.layer, width=width or x.width)

    c = Component()
    p = euler(
        radius=radius, angle=angle, p=p, use_eff=with_arc_floorplan, npoints=npoints
    )
    ref = c << p.extrude(x)
    c.add_ports(ref.ports)
    c.info["length"] = np.round(p.length(), 3)
    c.info["dy"] = np.round(abs(float(p.points[0][0] - p.points[-1][0])), 3)
    c.info["radius_min"] = float(np.round(p.info["Rmin"], 3))
    c.info["radius"] = float(radius)

    if direction == "cw":
        ref.mirror(p1=[0, 0], p2=[1, 0])

    if not allow_min_radius_violation:
        x.validate_radius(radius)

    top = None if int(angle) in {180, -180, -90} else 0
    bottom = 0 if int(angle) in {-90} else None
    x.add_bbox(c, top=top, bottom=bottom)
    c.add_route_info(
        cross_section=x, length=c.info["length"], n_bend_90=abs(angle / 90.0)
    )
    c.flatten()
    return c


bend_euler180 = partial(bend_euler, angle=180)


@gf.cell(check_instances=False)
def bend_euler_s(**kwargs) -> Component:
    r"""Sbend made of 2 euler bends.

    Keyword Args:
        angle: total angle of the curve.
        p: Proportion of the curve that is an Euler curve.
        with_arc_floorplan: If False: `radius` is the minimum radius of curvature
          If True: The curve scales such that the endpoints match a bend_circular
          with parameters `radius` and `angle`.
        npoints: Number of points used per 360 degrees.
        direction: cw (clock-wise) or ccw (counter clock-wise).
        with_bbox: add bbox_layers and bbox_offsets to avoid DRC sharp edges.
        cross_section: specification (CrossSection, string, CrossSectionFactory dict).
        kwargs: cross_section settings.

    .. code::

                        _____ o2
                       /
                      /
                     /
                    /
                    |
                   /
                  /
                 /
         o1_____/

    """
    c = Component()
    b = bend_euler(**kwargs)
    b1 = c.add_ref(b)
    b2 = c.add_ref(b)
    b2.mirror()
    b2.connect("o1", b1.ports["o2"])
    c.add_port("o1", port=b1.ports["o1"])
    c.add_port("o2", port=b2.ports["o2"])
    c.info["length"] = 2 * b.info["length"]
    return c


@gf.cell
def bend_straight_bend(
    straight_length: float = 10.0,
    angle: float = 90,
    p: float = 0.5,
    with_arc_floorplan: bool = True,
    npoints: int = 720,
    direction: str = "ccw",
    cross_section: CrossSectionSpec = strip,
) -> Component:
    """Sbend made of 2 euler bends and straight section in between.

    Args:
        straight_length: in um.
        angle: total angle of the curve.
        p: Proportion of the curve that is an Euler curve.
        with_arc_floorplan: If False: `radius` is the minimum radius of curvature
          If True: The curve scales such that the endpoints match a bend_circular
          with parameters `radius` and `angle`.
        npoints: Number of points used per 360 degrees.
        direction: cw (clock-wise) or ccw (counter clock-wise).
        cross_section: specification (CrossSection, string, CrossSectionFactory dict).
    """
    c = Component()
    b = bend_euler(
        angle=angle,
        p=p,
        with_arc_floorplan=with_arc_floorplan,
        npoints=npoints,
        direction=direction,
        cross_section=cross_section,
    )
    b1 = c.add_ref(b)
    b2 = c.add_ref(b)
    s = c << straight(length=straight_length, cross_section=cross_section)
    s.connect("o1", b1.ports["o2"])
    b2.mirror()
    b2.connect("o1", s.ports["o2"])
    c.add_port("o1", port=b1.ports["o1"])
    c.add_port("o2", port=b2.ports["o2"])
    return c


def _compare_bend_euler180() -> None:
    """Compare 180 bend euler with 2 90deg euler bends."""
    import gdsfactory as gf

    p1 = gf.Path()
    p1.append([gf.path.euler(angle=90), gf.path.euler(angle=90)])
    p2 = gf.path.euler(angle=180)
    x = gf.cross_section.strip()

    c1 = gf.path.extrude(p1, x)
    c1.name = "two_90_euler"
    c2 = gf.path.extrude(p2, x)
    c2.name = "one_180_euler"
    c1.add_ref(c2)
    c1.show()


def _compare_bend_euler90():
    """Compare bend euler with 90deg circular bend."""
    import gdsfactory as gf

    c = gf.Component()
    radius = 10
    b1 = bend_euler(radius=radius)
    b2 = gf.components.bend_circular(radius=radius)

    print(b1.info["length"])
    print(b2.info["length"])
    _ = c << b1
    _ = c << b2
    return c


if __name__ == "__main__":
    # c = bend_euler(cross_section="xs_rc", angle=90, radius=5)
    c = bend_euler(cross_section="xs_rc", angle=90, radius=5)
    c.show()
