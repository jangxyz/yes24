#!/usr/bin/python
# -*- coding: utf-8 -*-
import getpass
import logging
import sys, datetime
import locale; locale.setlocale(locale.LC_ALL, '')

import yes24
from yes24 import OrderListPage

def num(value, comma=True):
    ''' format number with comma '''
    import types
    if isinstance(value, types.StringTypes):
        value = value.replace(",", "")
    return locale.format("%d", int(value), comma)

def group_by(dic_list):
    ''' group values by key from multiple dictionaries.
     given  [{'A': 3, 'B': 4}, {'A': 5}],
     return [{'A': [3,5], 'B': [4]]
    '''
    result_dic = {}
    for dic in dic_list:
        for k, v in dic.iteritems():
            prev_value = result_dic.setdefault(k, [])
            result_dic[k].append(v)

    return result_dic

def authorize():
    username = raw_input('Username: ')
    password = getpass.getpass()
    opener = yes24.authorize(username, password)
    del username, password
    if opener is None:
        logging.error("failed to login!")
        sys.exit(1)
    return opener

def report_order_summary(orders):
    orders = list(orders)
    earliest_date = min(order.date  for order in orders)
    latest_date   = max(order.date  for order in orders)
    price_sum     = sum(order.price for order in orders)
    pkg_count     = sum(order.count for order in orders)
    print u"%s ~ %s 동안 %d번 주문: 총 %s개, %s원" % \
        (earliest_date, latest_date, len(orders), pkg_count, num(price_sum))
    return orders

def report_order_detail(orders):
    _orders = []
    #orders = sorted(orders, key=lambda order: order.date)
    for order in orders:
        payment = order.payment
        print ' *',
        print u"%s:" % order.date,
        print u"%7s원" % num(payment.price),
        #if len(payment.discounts) > 0:
        if True:
            print u"(",
            if payment.method != None:
                # method
                if payment.amount != u'0':
                    print u"%s" % payment.method,
                # paid
                print u"%7s원" % num(payment.amount), 
            # discounts
            for discount_by, discount_amt in payment.discounts:
                print u"+ %s %6s원"  % (discount_by, num(discount_amt)),
            print u")",
        print u"/ %s점 적립" % num(payment.point_saved)
        _orders.append(order)
    print
    return _orders

def report_payment_summary(orders):
    orders = list(orders)
    payments = [order.payment for order in orders]
    point_saved     = sum(payment.point_saved for payment in payments)
    payment_groups  = group_by({p.method: p.amount} for p in payments if p.method)
    discount_groups = group_by(dict(p.discounts) for p in payments)
    
    # report
    for paid in [payment_groups, discount_groups, {u"적립": [point_saved]}]:
        for method, amounts in paid.iteritems():
            print u'* %s: %7s원' % (method, num(sum(amounts)))
    print

    # check price integrity
    price_sum    = sum(order.price for order in orders)
    payment_sum  = sum(p.amount for p in payments)
    discount_sum = sum(d[1] for p in payments for d in p.discounts)
    if price_sum != payment_sum + discount_sum:
        logging.warn("paid sum %d does not match price sum %d!" % (num(payment_sum + discount_sum), num(price_sum)))

    return orders


if __name__ == '__main__':
    target_month = datetime.datetime.now().strftime("%Y.%m")

    if '--debug' in sys.argv:
        logging.basicConfig(level=logging.DEBUG)

    opener = authorize()
    # retrieve orders from order list page
    orders = yes24.retrieve_orders(opener, target_month=target_month)
    # parse order from order detail page
    orders = (order.parse_detail_page(opener) for order in orders)
    
    # report
    orders = report_order_detail(orders)
    orders = report_order_summary(orders)
    orders = report_payment_summary(orders)

    print 'opened', yes24.open_url_count, 'times, reading', num(yes24.read_bytes), 'bytes'

