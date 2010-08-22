#!/usr/bin/python
# -*- coding: utf-8 -*-
import getpass
import logging
import sys, datetime
import locale; locale.setlocale(locale.LC_ALL, '')

from yes24 import Yes24, OrderListPage, Order

if '--debug' in sys.argv:
    logging.basicConfig(level=logging.DEBUG)

target_month = datetime.datetime.now().strftime("%Y.%m")


# authorize
username = raw_input('Username: ')
password = getpass.getpass()
opener = Yes24.authorize(username, password)
del username, password
assert opener != None, "not logged in!"

# orders from order list page
orders = OrderListPage.retrieve_orders(opener, target_month=target_month)

# summary -- evaluate orders
orders = list(orders)
earliest_date = min(order.order_date for order in orders)
latest_date   = max(order.order_date for order in orders)
price_sum     = sum(int(order.price.replace(",", '')) for order in orders)
pkg_count     = sum(int(order.count) for order in orders)
print u"%s ~ %s 동안 %d번 주문: 총 %s개, %s원" % \
    (earliest_date, latest_date, len(orders), pkg_count, price_sum )
    #(earliest_date, latest_date, len(orders), pkg_count, locale.format("%d", price_sum, True))

# order detail page
order_ids   = (order.id for order in orders)
order_urls  = (Yes24.get_order_detail_link(order_id) for order_id in order_ids)
order_pages = (Yes24.open_url(opener, url) for url  in order_urls)
results     = (Order.PageParse.parse(text) for text in order_pages)

for order_price, point_saved, payment_method, money_spent, discounts in results:
    print ' *',
    if len(discounts) > 0:
        if money_spent != u'0':
            print u"%s원(%s %s원" % (order_price, payment_method, money_spent), 
        else:
            print u"%s원(%s원" % (order_price, money_spent), 
        for discount_by, discount_amt in discounts:
            print u"+ %s %s원"  % (discount_by.strip(), discount_amt),
        print u")/ %s점 적립" % (point_saved)
    else:
        print u"%s원 / %s점 적립" % (order_price, point_saved)


