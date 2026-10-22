"""Private, JSON-transparent ID indexes for documents owned by this harness.

Plain lists/dicts remain supported through a scan. They cannot be cached safely:
callers may retain a dictionary and change its ID without going through the API.
"""
import copy

_COLLECTIONS = ("objects", "layers", "gradients")
# Rare ID edits invalidate all indexes without retaining owners/references.
# Ordinary creation updates only the collection being appended to.
_id_revision = 0
_MISSING = object()


class _IDElement(dict):
    """A normal element mapping that invalidates indexes on an ID edit."""

    _tracked = False

    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def _changed(self, before):
        global _id_revision
        if self._tracked and before != self.get("id", _MISSING):
            _id_revision += 1

    def __setitem__(self, key, value):
        before = self.get("id", _MISSING)
        super().__setitem__(key, value)
        self._changed(before)

    def __delitem__(self, key):
        before = self.get("id", _MISSING)
        super().__delitem__(key)
        self._changed(before)

    def update(self, *args, **kwargs):
        before = self.get("id", _MISSING)
        try:
            super().update(*args, **kwargs)
        finally:
            # dict.update can change the ID before a later input raises.
            self._changed(before)

    def setdefault(self, key, default=None):
        before = self.get("id", _MISSING)
        result = super().setdefault(key, default)
        self._changed(before)
        return result

    def pop(self, *args):
        before = self.get("id", _MISSING)
        result = super().pop(*args)
        self._changed(before)
        return result

    def popitem(self):
        before = self.get("id", _MISSING)
        result = super().popitem()
        self._changed(before)
        return result

    def clear(self):
        before = self.get("id", _MISSING)
        super().clear()
        self._changed(before)

    def __ior__(self, other):
        self.update(other)
        return self

    def __copy__(self):
        return type(self)(self)

    def __deepcopy__(self, memo):
        result = type(self)()
        memo[id(self)] = result
        for key, value in self.items():
            dict.__setitem__(result, copy.deepcopy(key, memo),
                             copy.deepcopy(value, memo))
        return result


class _IDList(list):
    """Cache IDs until structural mutation or a tracked element ID edit."""

    def __init__(self, items=()):
        super().__init__()
        self._ids = None
        self._revision = _id_revision
        self.extend(items)

    @staticmethod
    def _bind(item):
        if type(item) is _IDElement:
            item._tracked = True

    def ids(self):
        if self._ids is not None and self._revision == _id_revision:
            return self._ids
        ids = set()
        cacheable = True
        for item in self:
            ids.add(item.get("id"))
            if type(item) is not _IDElement:
                cacheable = False
        # Never cache a plain mapping: an external reference can edit it later.
        self._ids = ids if cacheable else None
        self._revision = _id_revision
        return ids

    def append(self, item):
        super().append(item)
        self._bind(item)
        if self._ids is not None and self._revision == _id_revision:
            if type(item) is _IDElement:
                try:
                    self._ids.add(item.get("id"))
                except TypeError:
                    self._ids = None
            else:
                self._ids = None

    def extend(self, items):
        # list.extend accepts itself; iterate a snapshot in that case.
        for item in list(items) if items is self else items:
            self.append(item)

    def insert(self, index, item):
        super().insert(index, item)
        self._bind(item)
        self._ids = None

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            value = list(value)
            super().__setitem__(index, value)
            for item in value:
                self._bind(item)
        else:
            super().__setitem__(index, value)
            self._bind(value)
        self._ids = None

    def __delitem__(self, index):
        super().__delitem__(index)
        self._ids = None

    def pop(self, index=-1):
        result = super().pop(index)
        self._ids = None
        return result

    def remove(self, item):
        super().remove(item)
        self._ids = None

    def clear(self):
        super().clear()
        self._ids = None

    def __iadd__(self, items):
        self.extend(items)
        return self

    def __imul__(self, count):
        super().__imul__(count)
        self._ids = None
        return self

    def __copy__(self):
        return type(self)(self)

    def __deepcopy__(self, memo):
        result = type(self)()
        memo[id(self)] = result
        result.extend(copy.deepcopy(item, memo) for item in self)
        return result


def _track_project_ids(project):
    """Establish tracking at document creation/load, without JSON cache keys."""
    for key in _COLLECTIONS:
        items = project.get(key)
        if isinstance(items, list):
            project[key] = _IDList(
                _IDElement(item) if type(item) is dict else item
                for item in items
            )
    return project


def _collection_ids(items):
    if type(items) is _IDList:
        return items.ids()
    return {item.get("id") for item in items}
