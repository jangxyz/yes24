#!/usr/bin/python

import unittest, sys, os
sys.path.append( os.path.dirname(__file__) + '/..' )
import yes24


order_list_page_filenames = [
    './html/orderlist_20100505_p1.html', 
    './html/orderlist_20100505_p2.html',
]
target_month = "2010.05"

def parse(text):
    return yes24.parse_order_list_page(text, target_month)

class OrderListParseTestCase(unittest.TestCase):
    def setUp(self):
        path = os.path.dirname(__file__)
        filenames  = (path + '/' + filename for filename in order_list_page_filenames)
        self.files = (open(filename) for filename in filenames)
        self.texts = (file.read() for file in self.files)

    def tearDown(self):
        [file.close() for file in self.files]

    def test_parse_returns_order_list_and_navi_info(self):
        for text in self.texts:
            result = parse(text)
            # tuple of size 2
            assert '__len__' in dir(result) and len(result) == 2

            # [0] is order_list
            assert '__len__' in dir(result[0])

            # [1] is navi_info (current_page_no, next_page_path)
            assert '__len__' in dir(result[1]) and len(result[1]) == 2

    def test_page_01_has_4_orders(self):
        result = parse(self.texts.next())

        # orders
        orders = result[0]
        self.assertEquals(len(orders), 4, "has 4 orders on 2010.05")

        # navi info
        navi_info = result[1]
        self.assertEquals(navi_info[0], u'01')
        self.assertEquals(navi_info[1], 
            u'/Member/FTMyOrderList01.aspx?Gcode=001_001_004&IntPage=02')

    def test_page_02_has_no_orders(self):
        self.texts.next()
        result = parse(self.texts.next())

        # orders
        orders = result[0]
        self.assertEquals(len(orders), 0, "has 0 orders on 2010.05")

        # navi info
        navi_info = result[1]
        self.assertEquals(navi_info[0], u'02')
        self.assertEquals(navi_info[1], 
            u'/Member/FTMyOrderList01.aspx?Gcode=001_001_004&IntPage=03')

    def test_orders(self):
        orders = parse(self.texts.next())[0]
        # [(order_id, order_date, order_price, pkg_num, order_name)]

        order = orders[0]
        self.assertEqual(len(order), 5)
        # id, price, pkg_num is integer
        self.assertTrue(is_num(order[0]))
        self.assertTrue(is_num(order[2]))
        self.assertTrue(is_num(order[3]))

def is_num(text):
    try:
        int(text.replace(",", ''))
        return True
    except ValueError:
        return False


if __name__ == '__main__':
    unittest.main()

