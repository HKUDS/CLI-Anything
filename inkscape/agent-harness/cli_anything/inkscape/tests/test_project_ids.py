"""ID allocation regressions through the public document/core APIs."""
import copy
import gc
import json
import sys
import weakref

import pytest

from cli_anything.inkscape.core.document import (
    create_document, open_document, save_document, save_svg,
)
from cli_anything.inkscape.core.gradients import add_linear_gradient, add_radial_gradient
from cli_anything.inkscape.core.layers import add_layer
from cli_anything.inkscape.core.paths import path_union
from cli_anything.inkscape.core.session import Session
from cli_anything.inkscape.core.shapes import (
    add_rect, add_circle, add_ellipse, add_line, add_polygon, add_path, add_star,
    duplicate_object, remove_object,
)
from cli_anything.inkscape.core.text import add_text
from cli_anything.inkscape.utils.svg_utils import (
    generate_id, parse_svg_file, reset_id_counter,
)


@pytest.fixture(autouse=True)
def reset_ids():
    reset_id_counter()


def existing_ids(project):
    return {item.get("id") for key in ("objects", "layers", "gradients")
            for item in project.get(key, [])}


def next_rect_id(project):
    # Also prime the allocator before mutating the project.
    probe = generate_id("probe", project)
    return f"rect{int(probe[5:]) + 1}"


def assert_new_rect(project):
    before = existing_ids(project)
    added = add_rect(project)
    assert added["id"] not in before
    return added


@pytest.mark.parametrize("factory", [add_rect, add_linear_gradient])
def test_repeated_core_creation_has_linear_id_reads(factory):
    project = create_document()
    reads = 0

    def profile(frame, event, arg):
        nonlocal reads
        if event == "c_call" and getattr(arg, "__name__", None) == "get":
            target = getattr(arg, "__self__", None)
            if isinstance(target, dict) and target is not project:
                reads += 1

    previous = sys.getprofile()
    try:
        sys.setprofile(profile)
        for _ in range(512):
            factory(project)
    finally:
        sys.setprofile(previous)

    # Count work, not wall time. Include all core/index reads, allowing ample
    # constant overhead while rejecting a scan of every existing ID per add.
    assert reads < 512 * 32
    ids = [item["id"] for key in ("objects", "layers", "gradients")
           for item in project[key]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("factory", [
    add_rect, add_circle, add_ellipse, add_line, add_polygon, add_path, add_star,
    add_text, add_layer, add_linear_gradient, add_radial_gradient,
    lambda p: duplicate_object(p, 0),
    lambda p: path_union(p, 0, 1),
])
def test_mutating_returned_item_id_cannot_hide_a_collision(factory):
    project = create_document()
    add_rect(project)
    add_circle(project)
    item = factory(project)
    item["id"] = next_rect_id(project)
    assert_new_rect(project)


@pytest.mark.parametrize("mutate", [
    lambda item, value: item.__setitem__("id", value),
    lambda item, value: item.update(id=value),
    lambda item, value: item.update([("id", value)]),
    lambda item, value: item.__ior__({"id": value}),
    lambda item, value: (item.pop("id"), item.setdefault("id", value)),
    lambda item, value: (item.__delitem__("id"), item.setdefault("id", value)),
    lambda item, value: (item.clear(), item.setdefault("id", value)),
    lambda item, value: (item.popitem(), item.update(id=value)),
])
def test_id_mapping_mutators_invalidate_used_ids(mutate):
    project = create_document()
    item = add_rect(project)
    mutate(item, next_rect_id(project))
    assert_new_rect(project)


def test_partially_failed_mapping_update_still_invalidates_ids():
    project = create_document()
    item = add_rect(project)
    target = next_rect_id(project)
    with pytest.raises(ValueError):
        item.update([("id", target), ("bad",)])
    assert item["id"] == target
    assert_new_rect(project)


@pytest.mark.parametrize("collection", ["objects", "layers", "gradients"])
def test_direct_id_edit_in_each_collection_uses_one_namespace(collection):
    project = create_document()
    add_rect(project)
    add_linear_gradient(project)
    project[collection][0]["id"] = next_rect_id(project)
    assert_new_rect(project)


@pytest.mark.parametrize("collection", ["objects", "layers", "gradients"])
def test_same_length_collection_replacement_is_checked(collection):
    project = create_document()
    add_rect(project)
    add_linear_gradient(project)
    replacement = [dict(item) for item in project[collection]]
    replacement[0]["id"] = next_rect_id(project)
    project[collection] = replacement
    assert_new_rect(project)
    # Keep an external reference and edit it after the first scan, too.
    replacement[0]["id"] = next_rect_id(project)
    assert_new_rect(project)


@pytest.mark.parametrize("insert", [
    lambda items, item: items.append(item),
    lambda items, item: items.extend([item]),
    lambda items, item: items.insert(0, item),
    lambda items, item: items.__iadd__([item]),
    lambda items, item: items.__setitem__(slice(None), [item]),
    lambda items, item: items.__setitem__(0, item),
])
def test_retained_plain_dict_insertions_remain_checked(insert):
    project = create_document()
    add_rect(project)
    external = {"id": next_rect_id(project)}
    insert(project["objects"], external)
    assert_new_rect(project)
    external["id"] = next_rect_id(project)
    assert_new_rect(project)


@pytest.mark.parametrize("remove", [
    lambda items: items.pop(),
    lambda items: items.remove(items[0]),
    lambda items: items.clear(),
    lambda items: items.__delitem__(0),
    lambda items: items.__delitem__(slice(None)),
    lambda items: items.__setitem__(slice(None), []),
    lambda items: items.__imul__(0),
])
def test_deleted_ids_can_be_reused_after_counter_reset(remove):
    project = create_document()
    assert add_rect(project)["id"] == "rect1"
    next_rect_id(project)
    remove(project["objects"])
    reset_id_counter()
    assert add_rect(project)["id"] == "rect1"


def test_delete_then_append_without_length_change():
    project = create_document()
    add_rect(project)
    target = next_rect_id(project)
    project["objects"].pop()
    project["objects"].append({"id": target})
    assert_new_rect(project)


def test_deleting_one_duplicate_does_not_release_a_surviving_id():
    project = create_document()
    original = add_rect(project)
    project["objects"].append(original)
    next_rect_id(project)
    project["objects"].pop()
    reset_id_counter()
    assert generate_id("rect", project) == "rect2"
    project["objects"] *= 2
    project["objects"].pop()
    reset_id_counter()
    assert generate_id("rect", project) == "rect2"


def test_api_removal_keeps_other_layer_references_and_ids():
    project = create_document()
    removed = add_rect(project)
    kept = add_rect(project)
    next_rect_id(project)
    remove_object(project, 0)
    reset_id_counter()
    added = add_rect(project)
    assert added["id"] == removed["id"]
    assert kept["id"] != added["id"]
    assert project["layers"][0]["objects"] == [kept["id"], added["id"]]


def test_shallow_collection_copy_does_not_share_its_id_cache():
    project = create_document()
    add_rect(project)
    next_rect_id(project)
    cloned_list = copy.copy(project["objects"])
    other = create_document()
    reset_id_counter()
    add_rect(other)
    extra = add_rect(other)
    assert extra["id"] == "rect2"
    cloned_list.append(extra)
    reset_id_counter()
    assert generate_id("rect", project) == "rect2"
    reset_id_counter()
    other["objects"] = cloned_list
    assert generate_id("rect", other) == "rect3"


def test_deepcopy_keeps_aliases_but_not_allocator_state():
    project = create_document()
    item = add_rect(project)
    project["objects"].append(item)
    next_rect_id(project)
    cloned = copy.deepcopy(project)
    assert cloned["objects"][0] is cloned["objects"][1]
    assert cloned["objects"][0] is not item
    cloned["objects"][0]["id"] = "rect2"
    reset_id_counter()
    assert generate_id("rect", project) == "rect2"
    reset_id_counter()
    assert generate_id("rect", cloned) == "rect1"


def test_plain_json_project_and_external_alias_stay_supported():
    project = json.loads(json.dumps(create_document()))
    external = {"id": "rect1"}
    project["objects"].append(external)
    assert_new_rect(project)
    external["id"] = next_rect_id(project)
    assert_new_rect(project)
    assert set(project) == {
        "version", "name", "document", "objects", "layers", "gradients", "metadata",
    }


def test_reopen_serialization_session_and_svg_keep_public_data(tmp_path):
    project = create_document()
    add_rect(project)
    add_layer(project)
    add_linear_gradient(project)
    next_rect_id(project)
    path = tmp_path / "project.json"
    save_document(project, str(path))
    public_data = json.loads(path.read_text())
    assert public_data == project
    reset_id_counter()
    reopened = open_document(str(path))
    assert reopened == public_data
    assert_new_rect(reopened)

    session = Session()
    session.set_project(reopened)
    session_path = tmp_path / "session.json"
    session.save_session(str(session_path))
    assert json.loads(session_path.read_text()) == reopened
    svg_path = tmp_path / "project.svg"
    save_svg(reopened, str(svg_path))
    svg = parse_svg_file(str(svg_path))
    svg_ids = [element.get("id") for element in svg.iter() if element.get("id")]
    assert len(svg_ids) == len(set(svg_ids))
    assert set(public_data) == set(reopened)
    assert all(not key.startswith("_") for key in reopened)


def test_undo_redo_and_switching_projects_after_cache_prime():
    session = Session()
    session.set_project(create_document())
    first = add_rect(session.project)
    session.snapshot("add second")
    second = add_rect(session.project)
    next_rect_id(session.project)
    session.undo()
    reset_id_counter()
    assert add_rect(session.project)["id"] == second["id"]
    session.redo()
    reset_id_counter()
    added = assert_new_rect(session.project)
    assert added["id"] not in (first["id"], second["id"])

    other = create_document()
    session.set_project(other)
    reset_id_counter()
    assert add_rect(session.project)["id"] == "rect1"


def test_legacy_utility_api_and_reset_with_an_existing_project():
    project = create_document()
    add_rect(project)
    next_rect_id(project)
    reset_id_counter()
    assert generate_id() == "obj1"
    assert generate_id("rect", project) == "rect2"
    reset_id_counter()
    assert generate_id("rect", project) == "rect2"


def test_sort_and_reverse_preserve_collision_checks():
    project = create_document()
    add_rect(project)
    add_rect(project)
    next_rect_id(project)
    project["objects"].reverse()
    project["objects"].sort(key=lambda item: item["id"])
    reset_id_counter()
    assert add_rect(project)["id"] == "rect3"


def test_id_indexes_do_not_reserve_ids_in_a_different_project():
    first = create_document()
    first_item = add_rect(first)
    second = create_document()
    reset_id_counter()
    add_rect(second)
    next_rect_id(second)
    first_item["id"] = "rect2"
    reset_id_counter()
    assert generate_id("rect", second) == "rect2"
    reset_id_counter()
    assert generate_id("rect", first) == "rect1"


def test_index_lifetime_does_not_retain_discarded_documents():
    def references_only():
        project = create_document()
        item = add_rect(project)
        next_rect_id(project)
        return weakref.ref(project["objects"]), weakref.ref(item)

    collection_ref, item_ref = references_only()
    gc.collect()
    assert collection_ref() is None
    assert item_ref() is None
