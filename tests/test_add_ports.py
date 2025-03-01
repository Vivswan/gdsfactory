from __future__ import annotations

import gdsfactory as gf
from gdsfactory.add_pins import add_pins, add_pins_siepic
from gdsfactory.add_ports import (
    add_ports_from_markers_inside,
    add_ports_from_siepic_pins,
)


def test_add_ports_dict() -> None:
    c = gf.Component()
    s = c << gf.components.straight()
    c.add_ports(s.ports)
    assert len(c.ports) == 2, len(c.ports)


def test_add_ports_list() -> None:
    c = gf.Component()
    s = c << gf.components.straight()
    c.add_ports(s.ports)
    assert len(c.ports) == 2, len(c.ports)


def test_add_ports_from_pins(data_regression) -> None:
    c = gf.components.straight()
    add_pins(c)
    gdspath = c.write_gds()
    c2 = gf.import_gds(
        gdspath, post_process=add_ports_from_markers_inside, unique_names=False
    )
    d = c2.to_dict(with_ports=True)
    if data_regression:
        data_regression.check(d)


def test_add_ports_from_pins_siepic(data_regression) -> None:
    c = gf.components.straight()
    add_pins_siepic(c)
    gdspath = c.write_gds()
    c2 = gf.import_gds(
        gdspath, post_process=add_ports_from_siepic_pins, unique_names=False
    )
    d = c2.to_dict(with_ports=True)
    if data_regression:
        data_regression.check(d)


if __name__ == "__main__":
    test_add_ports_from_pins_siepic(None)
    # test_add_ports_from_pins(None)
    # test_add_ports_dict()
    # test_add_ports_list()
