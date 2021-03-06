# -*- coding: utf-8 -*-
"""
@author: Federico Cerchiari <federicocerchiari@gmail.com>
"""
import unittest

from tempy.tags import *
from tempy.tempy import DOMElement, Tag, TagAttrs


class TestTag(unittest.TestCase):

    def setUp(self):
        self.page = Html()

    def is_tag(self, tag):
        """a tag should be instance of Tag and DOMElement, and should have a TagAttrs attribute)"""
        self.assertIsInstance(tag, Tag)
        self.assertIsInstance(tag, DOMElement)
        self.assertIsInstance(tag.attrs, TagAttrs)

    def check_head_body(self, head, body):
        self.is_tag(head)
        self.is_tag(body)
        self.assertEqual(len(self.page.childs), 2)
        self.assertEqual(self.page.length, 2)
        self.assertEqual(self.page.childs[0], head)
        self.assertEqual(self.page.childs[1], body)
        self.assertEqual(self.page.first(), head)
        self.assertEqual(self.page.last(), body)

    def test_create_instantiation(self):
        self.is_tag(self.page)

    def test_create_call_singletag(self):
        head = Head()
        self.page(head)
        self.is_tag(head)
        self.assertEqual(len(self.page.childs), 1)
        self.assertEqual(self.page.length, 1)
        self.assertEqual(self.page.childs[0], head)
        self.assertEqual(self.page.first(), head)
        self.assertEqual(self.page.last(), head)

    def test_create_call_multitag(self):
        head = Head()
        body = Body()
        self.page(head, body)
        self.check_head_body(head, body)

    def test_create_call_list(self):
        l = [Head(), Body()]
        self.page(l)
        self.check_head_body(*l)

    def test_create_call_tuple(self):
        t = (Head(), Body())
        self.page(t)
        self.check_head_body(*t)

    def test_create_call_generator(self):
        g = (t for t in [Head(), Body()])
        self.page(g)
        head, body = self.page.childs
        self.check_head_body(head, body)

if __name__ == '__main__':
    unittest.main()
