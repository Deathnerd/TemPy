# -*- coding: utf-8 -*-
# @author: Federico Cerchiari <federicocerchiari@gmail.com>
from uuid import uuid4
from copy import copy
from functools import wraps
from itertools import chain
from collections import Mapping, OrderedDict, Iterable
from types import GeneratorType, MappingProxyType

from .exceptions import TagError


class _ChildElement:
    """Wrapper used to manage element insertion."""

    def __init__(self, name, obj):
        super().__init__()
        if not name and isinstance(obj, (DOMElement, Content)):
            name = obj._name
        self._name = name
        self.obj = obj


class DOMElement:
    """Takes care of the tree structure using the "childs" and "parent" attributes.
    Manages the DOM manipulation with proper valorization of those two.
    """

    def __init__(self):
        super().__init__()
        self._name = None
        self.childs = []
        self.parent = None
        self.content_data = {}
        self.uuid = uuid4()

    def __repr__(self):
        return '<{0}.{1} {2}. Son of {3}. Childs: {4}. Named \'{5}\'>'.format(
            self.__module__,
            type(self).__name__,
            self.uuid,
            '{} {}'.format(type(self.parent).__name__, self.parent.uuid) if self.parent else 'None',
            len(self.childs),
            self._name)

    def __hash__(self):
        return self.uuid

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __getitem__(self, i):
        return self.childs[i]

    def __iter__(self):
        return iter(self.childs)

    def __len__(self):
        return len(self.childs)

    def __contains__(self, x):
        return x in self.childs

    def __copy__(self):
        new = self.__class__()(copy(c) if isinstance(c, (DOMElement, Content)) else cfor c in self.childs)
        if hasattr(new, 'attrs'):
            new.attrs = self.attrs
        return new

    @property
    def _own_index(self):
        if self.parent:
            return self.parent.childs.index(self)
        return None

    def _yield_items(self, items, kwitems, reverse=False):
        """
        Recursive generator, flattens the given items/kwitems.
        Returns index after flattening and a _ChildElement.
        "reverse" parameter inverts the yielding.
        """
        verse = (1, 0)[reverse]
        unnamed = (_ChildElement(None, item) for item in items[::verse])
        named = (_ChildElement(k, v) for k, v in list(kwitems.items())[::verse])
        contents = (unnamed, named)[::verse]
        for i, item in enumerate(chain(*contents)):
            if type(item.obj) in (list, tuple, GeneratorType):
                if item._name:
                    # TODO: implement tag named containers
                    # Happens when iterable in kwitems
                    # i.e: d = Div(paragraphs=[P() for _ in range(5)])
                    # d.paragraphs -> [P(), P(), P()...]
                    yield i, item.obj
                else:
                    yield from self._yield_items(item.obj, {})
            elif isinstance(item.obj, DOMElement):
                yield i, item.obj
            else:
                yield i, item.obj

    def content_receiver(reverse=False):
        """Decorator for content adding methods.
        Takes args and kwargs and calls the decorated method one time for each argument provided.
        The reverse parameter should be used for prepending (relative to self) methods.
        """
        def _receiver(func):
            @wraps(func)
            def wrapped(inst, *tags, **kwtags):
                for i, tag in inst._yield_items(tags, kwtags, reverse):
                    inst._stable = False
                    func(inst, i, tag)
                return inst
            return wrapped
        return _receiver

    def _insert(self, child, idx=None, prepend=False):
        """Inserts something inside this element.
        If provided at the given index, if prepend at the start of the childs list, by default at the end.
        If the child is a DOMElement, correctly links the child.
        If a name is provided, an attribute containing the child is created in this instance.
        """
        if idx and idx < 0:
            idx = 0
        if prepend:
            idx = 0
        else:
            idx = idx if idx is not None else len(self.childs)
        self.childs.insert(idx, child)
        if isinstance(child, (DOMElement, Content)):
            child.parent = self
            if child._name:
                setattr(self, child._name, child)

    def _find_content(self, cont_name):
        """Search for a content_name in the content data, if not found the parent is searched."""
        try:
            a = self.content_data[cont_name]
            return a
        except KeyError:
            if self.parent:
                return self.parent._find_content(cont_name)
            else:
                # Fallback for no content (Raise NoContent?)
                return ''

    def inject(self, contents=None, **kwargs):
        """
        Adds content data in this element. This will be used in the rendering of this element's childs.
        Multiple injections on the same key will override the content (dict.update behavior).
        """
        self._stable = False
        if not contents:
            contents = {}
        if kwargs:
            contents.update(kwargs)
        self.content_data.update(contents)
        return self

    def clone(self):
        """Returns a deepcopy of this element."""
        return copy(self)

    @content_receiver()
    def __call__(self, _, child):
        """Calling the object will add the given parameters as childs"""
        self._insert(child)

    @content_receiver()
    def after(self, i, child):
        """Adds siblings after the current tag."""
        self.parent._insert(child, idx=self._own_index + 1 + i)

    @content_receiver(reverse=True)
    def before(self, i, child):
        """Adds siblings before the current tag."""
        self.parent._insert(child, idx=self._own_index - i)

    @content_receiver(reverse=True)
    def prepend(self, child):
        """Adds childs tho this tag, starting from the first position."""
        self._insert(child, prepend=True)

    def prepend_to(self, father):
        """Adds this tag to a father, at the beginning."""
        father.prepend(self)

    @content_receiver()
    def append(self, child):
        """Adds childs to this tag, after the current existing childs."""
        self._insert(child)

    def append_to(self, father):
        """Adds this tag to a parent, after the current existing childs."""
        father.append(self)

    def wrap(self, other):
        """Wraps this element inside another empty tag."""
        # TODO: make multiple with content_receiver
        if other.childs:
            raise TagError
        if self.parent:
            self.before(other)
            self.parent.pop(self._own_index)
        return other.append(self)

    def wrap_inner(self, other):
        # TODO
        pass

    def replace_with(self, other):
        """Replace this element with the given DOMElement."""
        if isinstance(other, DOMElement):
            self = other
        elif isinstance(other, (GeneratorType, Iterable)):
            self.parent.childs[self._own_index: self._own_index+1] = list(other)
        else:
            raise TagError()
        return self

    def remove(self):
        """Detach this element from his father."""
        if self._own_index and self.parent:
            self.parent.pop(i=self._own_index)
        return self

    def move(self, new_father, idx=None, prepend=None):
        """Moves this element from his father to the given one."""
        self.parent.pop(i=self._own_index)
        new_father._insert(self._name, self, idx, prepend)
        new_father._stable = False
        return self

    def pop(self, idx=None):
        """Removes the child at given position, if no position is given removes the last."""
        self._stable = False
        if not idx:
            idx = len(self.childs) - 1
        elem = self.childs.pop(idx)
        if isinstance(elem, DOMElement):
            elem.parent = None
        return elem

    def empty(self):
        """Remove all this tag's childs."""
        self._stable = False
        map(lambda child: self.pop(child._own_index), self.childs)
        return self

    # TODO: Make all the following properties?
    def childrens(self):
        """Returns Tags and Content Placehorlders childs of this element."""
        return filter(lambda x: isinstance(x, DOMElement), self.childs)

    def contents(self):
        """Returns this elements childs list, unfiltered."""
        return self.childs

    def first(self):
        """Returns the first child"""
        return self.childs[0]

    def last(self):
        """Returns the last child"""
        return self.childs[-1]

    def next(self):
        """Returns the next sibling."""
        return self.parent.child[self._own_index + 1]

    def next_all(self):
        """Returns all the next siblings as a list."""
        return self.parent.child[self._own_index + 1:]

    def prev(self):
        """Returns the previous sibling."""
        return self.parent.child[self._own_index - 1]

    def prev_all(self):
        """Returns all the previous siblings as a list."""
        return self.parent.child[:self._own_index - 1]

    def siblings(self):
        """Returns all the siblings of this element as a list."""
        return filter(lambda x: x != self, self.parent.childs)

    def parent(self):
        """Returns this element's father"""
        return self.parent

    def slice(self, start=None, end=None, step=None):
        """Slice of this element's childs as childs[start:end:step]"""
        return self.childs[start:end:step]

    def _dfs_tags(self):
        """Iterate the element inner content, in reverse depth-first.
         Used to render the tags from the childmost ones to the root.
        """
        # Based on http://www.ics.uci.edu/~eppstein/PADS/DFS.py
        # by D. Eppstein, July 2004.
        given = set()
        stack = copy(self.childs)
        while stack:
            tag = stack.pop()
            if not tag.childs:
                given.add(tag)
                yield tag
            else:
                if set(tag.childs).issubset(given):
                    given.add(tag)
                    yield tag
                else:
                    stack.append(tag)
                    stack += list(set(tag.childs) - given)
        yield self

    def render(self, *args, **kwargs):
        """Placeholder for subclass implementation"""
        raise NotImplementedError


class TagAttrs(dict):
    """
    Html tag attributes container, a subclass of dict with __setitiem__ and update overload.
    Manages the manipulation and render of tag attributes, using the dict api, with few exceptions:
    - space separated multiple value keys
        i.e. the class atrribute, an update on this key will add the value to the list
    - mapping type attributes
        i.e. style attribute, an udpate will trigger the dict.update method

    TagAttrs.render formats all the attributes in the proper html format.
    """
    _MAPPING_ATTRS = ('style', )
    _MULTI_VALUES_ATTRS = ('klass', 'typ', )
    _SPECIALS = {
        'klass': 'class',
        'typ': 'type'
    }
    _FORMAT = {
        'style': lambda x: ' '.join('%s: %s;' % (k, v) for k, v in x.items()),
        'klass': lambda x: ' '.join(x),
        'typ': lambda x: ' '.join(x),
        'comment': lambda x: x
    }

    def __setitem__(self, key, value):
        if key in self._MULTI_VALUES_ATTRS:
            if key not in self:
                super().__setitem__(key, [])
            self[key].append(value)
        elif key in self._MAPPING_ATTRS:
            if key not in self:
                super().__setitem__(key, {})
            self[key].update(value)
        else:
            super().__setitem__(key, value)

    def update(self, attrs=None, **kwargs):
        if attrs is not None:
            for k, v in attrs.items() if isinstance(attrs, Mapping) else attrs:
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v

    def render(self):
        """Renders the tag's attributes using the formats and performing special attributes name substitution."""
        if hasattr(self, '_comment'):
            # Special case for the comment tag
            return self._comment
        else:
            return ''.join(' %s="%s"' % (self._SPECIALS.get(k, k),
                                         self._FORMAT.get(k, lambda x: x)(v))
                           for k, v in self.items() if v)


class Tag(DOMElement):
    """
    Provides an api for tag inner manipulation and for rendering.
    """
    _template = '<{tag}{attrs}>{inner}</{tag}>'
    _needed_kwargs = None
    _void = False

    def __init__(self, **kwargs):
        self.attrs = TagAttrs()
        self.data = {}
        if self._needed_kwargs and not set(self._needed_kwargs).issubset(set(kwargs)):
            raise TagError()
        self.attr(**kwargs)
        self._tab_count = 0
        self._render = None
        self._stable = False
        super().__init__()
        if self._void:
            self._render = self.render()

    def __repr__(self):
        css_repr = '%s%s' % (
            ' .css_class %s' % (self.attrs['klass']) if 'klass' in self.attrs else '',
            ' .css_id %s ' % (self.attrs['id']) if 'id' in self.attrs else '',
            )
        return super().__repr__()[:-1] + '{}>'.format(css_repr)

    @property
    def length(self):
        """Returns the number of childs."""
        return len(self.childs)

    @property
    def index(self):
        """Returns the position of this element in the parent's childs list.
        If the element have no parent, returns None.
        """
        return self._own_index

    @property
    def stable(self):
        if all(c.stable for c in self.childs) and self._stable:
            self._stable = True
            return self._stable
        else:
            self._stable = False
            return self._stable

    def attr(self, attrs=None, **kwargs):
        """Add an attribute to the element"""
        self._stable = False
        self.attrs.update(attrs or kwargs)
        return self

    def remove_attr(self, attr):
        """Removes an attribute."""
        self._stable = False
        self.attrs.pop(attr, None)
        return self

    def add_class(self, cssclass):
        """Adds a css class to this element."""
        self._stable = False
        self.attrs['klass'].append(cssclass)
        return self

    def remove_class(self, cssclass):
        """Removes the given class from this element."""
        self._stable = False
        self.attrs['klass'].remove(cssclass)
        return self

    def css(self, *props, **kwprops):
        """Adds css properties tho this element."""
        self._stable = False
        styles = {}
        if props:
            if len(props) == 1 and isinstance(props[0], Mapping):
                styles = props[0]
            elif len(props) == 2:
                styles = dict(*props)
            else:
                raise TagError
        elif kwprops:
            styles = kwprops
        else:
            raise TagError
        return self.attr(attrs={'style': styles})

    def hide(self):
        """Adds the "display: none" style attribute."""
        self._stable = False
        self.attrs['style']['display'] = None
        return self

    def show(self):
        """Removes the display style attribute."""
        self._stable = False
        self.attrs['style'].pop('display')
        return self

    def toggle(self):
        """Same as jQuery's toggle, toggles the display attribute of this element."""
        self._stable = False
        return self.show() if self.attrs['style']['display'] == None else self.hide()

    def data(self, key, value=None):
        """Adds extra data to this element, this data will not be rendered."""
        if value:
            self.data[key] = value
            return self
        else:
            return self.data[key]

    def has_class(self, csscl):
        """Checks if this element have the given css class."""
        return csscl in self.attrs['klass']

    def toggle_class(self, csscl):
        """Same as jQuery's toggleClass function. It toggles the css class on this element."""
        self._stable = False
        return self.remove_class(csscl) if self.has_class(csscl) else self.add_class(csscl)

    def html(self):
        """Renders the inner html of this element."""
        return self._get_child_renders()

    def text(self):
        """Renders the contents inside this element, without html tags."""
        texts = []
        for child in self.childs:
            if isinstance(child, Tag):
                texts.append(child.text())
            elif isinstance(child, Content):
                texts.append(child.render())
            else:
                texts.append(child)
        return ''.join(texts)

    def render(self, *args, **kwargs):
        """Renders the element and all his childrens."""
        # args kwargs API provided for last minute content injection
        for arg in args:
            if isinstance(arg, dict):
                self.inject(arg)
        if kwargs:
            self.inject(kwargs)

        # If the tag or his contents are not changed, we skip all the work
        if self._stable and self._render:
            return self._render

        tag_data = {
            'tag': getattr(self, '_%s__tag' % self.__class__.__name__),
            'attrs': self.attrs.render()
        }
        tag_data['inner'] = self._get_child_renders() if not self._void and self.childs else ''

        # We declare the tag is stable and have an official render:
        self._render = self._template.format(**tag_data)
        self._stable = True
        return self._render

    def _get_child_renders(self):
        return ''.join(child.render() if isinstance(child, (DOMElement, Content)) else str(child) for child in self.childs)


class VoidTag(Tag):
    """
    A void tag, as described in W3C reference: https://www.w3.org/TR/html51/syntax.html#void-elements
    """
    _void = True
    _template = '<{tag}{attrs}/>'


class Content:
    """
    Provides the ability to use a simil-tag object as content placeholder.
    At render time, a content with the same name is searched in parents, the nearest one is used.
    If no content with the same name is used, an empty string is rendered.
    If instantiated with the named attribute content, this will override all the content injection on parents.
    """
    def __init__(self, name=None, content=None, template=None):
        super().__init__()
        self.parent = None
        self._tab_count = 0
        if not name and not content:
            raise TagError
        self._name = name
        self._fixed_content = content
        self._template = template
        self.uuid = uuid4()
        self.stable = False

    def __repr__(self):
        return '<{0}.{1} {2}. Son of {3}. Named \'{4}\'>'.format(
            self.__module__,
            type(self).__name__,
            self.uuid,
            '{} {}'.format(type(self.parent).__name__, self.parent.uuid) if self.parent else 'None',
            self._name)

    def __copy__(self):
        return self.__class__(self._name, self._fixed_content, self._template)

    @property
    def content(self):
        content = self._fixed_content or self.parent._find_content(self._name)
        if content:
            if type(content) in (list, tuple, GeneratorType) or (isinstance(content, Iterable) and content is not str):
                return list(content)
            elif type(content) in (MappingProxyType, ):
                return list(content.values())
            else:
                return (content, )
        else:
            raise StopIteration

    @property
    def length(self):
        return len(self.content)

    def render(self, pretty=False):
        ret = []
        for content in self.content:
            if isinstance(content, DOMElement):
                ret.append(content.render(pretty))
            else:
                if self._template:
                    self._template.inject(content)
                    ret.append(self._template.inject(content).render())
                else:
                    ret.append(str(content))
        return ''.join(ret)


class Css(Tag):
    """Special class for the style tag.
    Css attributes can be altered with the .attr Tag api. At render time the attr dict is transformed in valid css:
    Css({'html': {
            'body': {
                'color': 'red',
                'div': {
                    'color': 'green',
                    'border': '1px'
                }
            }
        },
        '#myid': {'color': 'blue'}
    }
    translates to:
    <style>
    html body {
        color: red;
    }

    html body div {
        color: green;
        border: 1px;
    }
    #myid {
        'color': 'blue';
    }
    </style>
    """
    _template = '<style>{css}</style>'

    def render(self, *args, **kwargs):
        pretty = kwargs.pop('pretty', False)
        result = []
        nodes_to_parse = [([], self.attrs)]

        while nodes_to_parse:
            parents, node = nodes_to_parse.pop(0)
            if parents:
                result.append("%s { " % " ".join(parents))
            else:
                parents = []

            for key, value in node.items():
                if value.__class__.__name__ in ('str', 'unicode'):
                    result.append('%s: %s; %s' % (key, value, "\n" if pretty else ""))
                elif value.__class__.__name__ == 'function':
                    result.append('%s: %s; %s' % (key, value(), "\n" if pretty else ""))
                elif value.__class__.__name__ == 'dict':
                    nodes_to_parse.append(([p for p in parents] + [key], value))
            if result:
                result.append("}" + "\n\n" if pretty else "")

        return self._template.format(css=''.join(result))
