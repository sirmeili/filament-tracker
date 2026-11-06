import json
from pathlib import Path

import pytest

from filament_tracker.printer.report import AmsView, TrayReport, slot_name

REPORTS = Path(__file__).parent / "reports"


def load(name: str) -> dict:
    return json.loads((REPORTS / f"{name}.json").read_text(encoding="utf-8"))


def view_of(*names: str) -> AmsView:
    view = AmsView()
    for name in names:
        view.apply(load(name))
    return view


def test_a_full_report_gives_every_slot() -> None:
    trays = view_of("pushall").trays()

    assert trays == [
        TrayReport(
            0, 0, "A1B2C3D4E5F60718293A4B5C6D7E8F90", "GFA00", "PLA", "PLA Basic", "000000FF", 85
        ),
        TrayReport(0, 1),
        TrayReport(0, 2, None, "GFG99", "PETG", None, "FF6A13FF", None),
        TrayReport(
            0, 3, "0F1E2D3C4B5A69788796A5B4C3D2E1F0", "GFG02", "PETG", "PETG HF", "515151FF", 0
        ),
    ]
    assert [t.loaded for t in trays] == [True, False, True, True]


def test_a_change_is_merged_into_what_is_known() -> None:
    trays = view_of("pushall", "remain-delta").trays()

    assert trays[0].remaining_pct == 80
    assert trays[0].tray_uuid == "A1B2C3D4E5F60718293A4B5C6D7E8F90"
    assert trays[3].remaining_pct == 0


def test_a_message_without_an_ams_section_changes_nothing() -> None:
    view = view_of("pushall")

    assert view.apply(load("no-ams")) is False
    assert view.trays() == view_of("pushall").trays()


def test_an_unloaded_slot_becomes_empty() -> None:
    trays = view_of("pushall", "unloaded").trays()

    assert trays[3] == TrayReport(0, 3)


def test_tray_exist_bits_clear_slots() -> None:
    view = view_of("pushall")
    view.apply({"print": {"ams": {"tray_exist_bits": "1"}}})

    assert [t.loaded for t in view.trays()] == [True, False, False, False]


def test_units_missing_from_the_list_are_removed() -> None:
    view = view_of("pushall")
    view.apply(
        {"print": {"ams": {"ams": [{"id": "1", "tray": [{"id": "0", "tray_type": "ABS"}]}]}}}
    )

    assert view.trays() == [TrayReport(1, 0, filament_type="ABS")]


@pytest.mark.parametrize(
    "message",
    [
        None,
        "text",
        [],
        {"print": None},
        {"print": {"ams": "x"}},
        {"print": {"ams": {"ams": "x"}}},
        {"print": {"ams": {"ams": [None, {"id": "x", "tray": []}, {"id": "0", "tray": None}]}}},
        {"print": {"ams": {"ams": [{"id": 99, "tray": []}]}}},
        {"print": {"ams": {"ams": [{"id": "0", "tray": [None, {"id": "9"}, {"id": True}]}]}}},
        {"print": {"ams": {"tray_exist_bits": "zz"}}},
    ],
)
def test_malformed_messages_are_skipped(message: object) -> None:
    view = AmsView()
    view.apply(message)

    assert view.trays() == []


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"tray_uuid": "not-hex", "remain": "55"}, TrayReport(0, 0, remaining_pct=55)),
        ({"tray_uuid": "a" * 32}, TrayReport(0, 0, tray_uuid="A" * 32)),
        ({"tray_color": "ff0000"}, TrayReport(0, 0, color_rgba="FF0000FF")),
        ({"tray_color": "red", "remain": 101}, TrayReport(0, 0)),
        ({"tray_type": "  ", "remain": True}, TrayReport(0, 0)),
        ({"tray_type": "x" * 33, "remain": "1.5"}, TrayReport(0, 0)),
        ({"tray_info_idx": 7, "remain": -1}, TrayReport(0, 0)),
    ],
)
def test_tray_fields_are_cleaned(fields: dict, expected: TrayReport) -> None:
    view = AmsView()
    view.apply({"print": {"ams": {"ams": [{"id": 0, "tray": [{"id": 0, **fields}]}]}}})

    assert view.trays() == [expected]


def test_a_real_p1s_report_with_an_ams_ht() -> None:
    """Captured from a P1S with an AMS and an AMS HT; identifiers replaced."""
    trays = view_of("p1s-pushall").trays()

    assert [(t.ams_index, t.tray_index) for t in trays] == [
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3),
        (128, 0),
    ]
    assert [t.remaining_pct for t in trays] == [85, 37, 83, 74, 6]
    assert trays[4].material_id == "GFG02"
    assert trays[4].sub_brand == "PETG HF"
    assert all(t.tray_uuid for t in trays)


def test_tray_exist_bits_cover_the_ams_ht() -> None:
    view = view_of("p1s-pushall")
    view.apply({"print": {"ams": {"tray_exist_bits": "f"}}})

    trays = view.trays()
    assert [t.loaded for t in trays] == [True, True, True, True, False]


@pytest.mark.parametrize("unit_id", ["4", "127", "136", "-1"])
def test_unknown_unit_ids_are_skipped(unit_id: str) -> None:
    view = AmsView()
    view.apply(
        {"print": {"ams": {"ams": [{"id": unit_id, "tray": [{"id": "0", "tray_type": "PLA"}]}]}}}
    )

    assert view.trays() == []


def test_an_ams_ht_has_one_slot() -> None:
    view = AmsView()
    trays = [{"id": "0", "tray_type": "PLA"}, {"id": "1", "tray_type": "PETG"}]
    view.apply({"print": {"ams": {"ams": [{"id": "129", "tray": trays}]}}})

    assert [(t.ams_index, t.tray_index) for t in view.trays()] == [(129, 0)]


@pytest.mark.parametrize(
    ("ams_index", "tray_index", "name"),
    [(0, 1, "AMS 1, slot 2"), (3, 3, "AMS 4, slot 4"), (128, 0, "AMS HT 1"), (130, 0, "AMS HT 3")],
)
def test_slot_names(ams_index: int, tray_index: int, name: str) -> None:
    assert slot_name(ams_index, tray_index) == name
