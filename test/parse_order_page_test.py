#!/usr/bin/python
# -*- coding: utf-8 -*-

import unittest, sys, os
sys.path.append( os.path.dirname(__file__) + '/..' )
import yes24

order_page_filenames = [
    './html/orderdetail_20100329_52778926.html',
    './html/orderdetail_20100412_53266606_coupon.html',
    './html/orderdetail_20100412_53266648_yesmoney.html',
]

def parse(text):
    return yes24.parse_order_detail_page(text)

# parse only once
orders = []
for filename in order_page_filenames:
    file = open(os.path.dirname(__file__) + '/' + filename)
    text = file.read()
    text = text.replace("\n", "\r\n")
    orders.append( parse(text) )
    file.close()

class OrderDetailParseTestCase(unittest.TestCase):
    def setUp(self):    pass
    def tearDown(self): pass

    def test_order_detail_ex1(self):
        order = orders[0]
        # (order_price, point_saved, payment_method, money_spent, discounts)
        
        # price, point, money_spent is number
        self.assertEqual(num(order[0]), 42450) # 총 금액
        self.assertEqual(num(order[1]), 3432)  # YES포인트 적립액
        self.assertEqual(num(order[3]), 42450) # 결제 금액

        self.assertEqual(order[2], u"신용카드 : 국민카드일시불") # 결제 수단

        # discount is a list of tuples [(method, amount)]
        self.assertTrue('__len__' in dir(order[4]))
        self.assertEqual(order[4], [])


    def test_order_detail_coupon(self):
        order = orders[1]
        # (order_price, point_saved, payment_method, money_spent, discounts)
        
        # 
        total_price = num(order[0])
        self.assertEqual(total_price, 84900) # 총 금액

        # money_spent
        money_spent = num(order[3])
        self.assertEqual(money_spent, 82900) # 결제 금액

        # discount is a list of tuples [(method, amount)]
        discounts = order[4]
        self.assertEqual(len(discounts), 1)
        coupon_discount = num(discounts[0][1])
        self.assertEqual(discounts[0][0].strip(), u"쿠폰 사용")
        self.assertEqual(coupon_discount, 2000)

        self.assertEqual(total_price, money_spent + coupon_discount)

    def test_order_detail_yesmoney(self):
        order = orders[2]
        # (order_price, point_saved, payment_method, money_spent, discounts)
        
        # 
        total_price = num(order[0])
        self.assertEqual(total_price, 21420) # 총 금액

        # money_spent
        money_spent = num(order[3])
        self.assertEqual(money_spent, 0) # 결제 금액

        # discount is a list of tuples [(method, amount)]
        discounts = order[4]
        self.assertEqual(len(discounts), 1)
        yesmoney_discount = num(discounts[0][1])
        self.assertEqual(discounts[0][0].strip(), u"YES머니 사용")
        self.assertEqual(yesmoney_discount, 21420)

        self.assertEqual(total_price, yesmoney_discount)

def num(text):
    try:
        return int(text.replace(",", ''))
    except ValueError:
        return None


if __name__ == '__main__':
    unittest.main()

