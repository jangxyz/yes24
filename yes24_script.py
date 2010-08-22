#!/usr/bin/python
# -*- coding: utf-8 -*-
import getpass
import urllib, urllib2, cookielib
from BeautifulSoup import BeautifulSoup
from datetime import datetime
import sys, re
import logging

if '-d' in sys.argv:
    logging.basicConfig(level=logging.DEBUG)

target_month=datetime.now().strftime("%Y.%m")

default_url = "http://www.yes24.com/"
secure_url  = "https://www.yes24.com/"
login_url   = "https://www.yes24.com/Templates/FTLogIn.aspx"
order_path  = "/Member/FTMyOrderList01.aspx"
order_url   = secure_url + order_path
order_detail_url = "https://www.yes24.com/Member/FTMyOrderDtl01.aspx"

login_data = {
    "SMemberID"              : None,
    "SMemberPassword"        : None,
    "RefererUrl"             : "http://www.yes24.com/Main/Default.aspx",
    "AutoLogin"              : "1",
    "LoginIDSave"            : "N",
    "FBLoginSub:LoginType"   : '',
    "FBLoginSub:ReturnURL"   : '',
    "FBLoginSub:ReturnParams": '',
}


def authorize(username, password):
    cj = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

    login_data['SMemberID'] = username
    login_data['SMemberPassword'] = password

    resp = opener.open(login_url, urllib.urlencode(login_data))
    html = resp.read()
    if 'location.replace' not in html:
        return None
    else:
        return opener


def open_url(url):
    logging.debug("openening url: " + url)
    site = opener.open(url)
    text = site.read()
    return text.decode('cp949')


def test_login(html):
    if 'Login' in html:    # 로그아웃 돼 있으니 login하라고 뜬다
        return False
    elif 'Logout' in html: # 로그인 돼 있으니 logout할 수 있다고 뜬다
        return True
    else:
        raise Exception("로그인 여부를 판단할 수 없습니다.")

def massage_html(text):
    return text.replace('''<a style="cursor:hand";''', '''<a style="cursor:hand"''')

def parse_order_page(text):
    start_pattern = '''<div id="ordList"'''
    end_pattern   = '''<script language='JavaScript'>'''
    start_idx = text.find(start_pattern)
    end_idx   = text[start_idx:].find(end_pattern) + start_idx
    if end_idx == start_idx -1:
        raise Exception('cannot find end pattern from %s: %s' % (order_url, end_pattern))
    text = text[start_idx:end_idx]
    # massage
    text = text.replace('''<a style="cursor:hand";''', '''<a style="cursor:hand"''')
    # parse
    soup = BeautifulSoup(text)
    order_list_table     = soup.table(id="MyOrderListTbl")[0]
    page_navigator_table = soup.table(id="tblNavigator")[0]
    # navigation
    current_page_anchor = page_navigator_table.find('a', href=None)
    next_page_anchor = current_page_anchor.findNextSibling('a')
    print 'current page:', current_page_anchor.string
    print 'next page:', next_page_anchor["href"]
    navi_info = (current_page_anchor.string, next_page_anchor["href"])
    # order list
    orders = []
    remove_bogus_rows = lambda tag: tag.name == u'tr' and len(tag.findAll('td')) != 1
    remove_bogus_cell = lambda tag: tag.name == u'td' and tag['width'] != u'1'
    for tr in order_list_table.find('tr').findNextSiblings(remove_bogus_rows):
        tds = tr.findAll(remove_bogus_cell)
        order_id = tds[0].b.string
        order_detail_link = get_order_detail_link(order_id)
        order_date = tds[1].string
        order_name = tds[2].span.string
        order_price = tds[3].b.string
        pkg_num = tds[3].b.string.next.rsplit('/')[-1]
        deliver_state_link = get_deliver_state_link(order_id)
        if not str(order_date).startswith(target_month):
            continue
        #print '-', order_date, order_id, order_name, order_price, pkg_num, deliver_state_link
        #print '[%s] %s 에 %s원치(%s개)를 샀습니다: %s' % (order_id, order_date, order_price, pkg_num, order_name)
        orders.append( (order_id, order_date, order_price, pkg_num, order_name) )
    return (orders, navi_info)

    

def get_order_detail_link(order_id):
    return order_detail_url + "?ordNoH=" + order_id

def get_deliver_state_link(order_id):
    return "http://www.yes24.com/Order/FTDelvTrcListFrame.aspx?OID="+order_id+"&TTL=L"

def parse_order_detail_page(text):
    start_pattern = '''<span id="infoQuickDlv"'''
    end_pattern   = '''<script Language=javascript>'''
    start_idx = text.find(start_pattern)
    end_idx   = text[start_idx:].find(end_pattern) + start_idx
    if end_idx == start_idx -1:
        raise Exception('cannot find end pattern from %s: %s' % (order_url, end_pattern))
    text = text[start_idx:end_idx]
    # massage
    text = text.replace('''<table cellpadding="0" cellspacing=0" border="0" >''', '''<table cellpadding="0" cellspacing="0" border="0" >''')
    # parse
    soup = BeautifulSoup(text)
    order_price = soup.find(id="CLbTotOrdAmt").b.string
    text = ''.join(filter(lambda x: '<span id="CLbPayPrInfo">' in x, text.split("\r\n"))).strip()
    text = '<table>' + text[text[1:].find('<')+1:-7] + '</table>'
    soup = BeautifulSoup(text)
    point_saved = soup.find(attrs={'class':"price"}).b.string
    if soup.find(attrs={'class':"priceB"}) is not None:
        money_spent = soup.find(attrs={'class':"priceB"}).string
    else:
        money_spent = u'0'
    if soup.find(text=re.compile(u'결제.*수단')) is not None:
        payment_method = soup.find(text=re.compile(u'결제.*수단')).parent.findNextSibling('td').next.replace("&nbsp;", '').strip()
    else:
        payment_method = None
    find_discount = lambda tag: tag.name == u'td' and \
        tag.findNextSibling('td') and \
        tag.findNextSibling('td').findNextSibling('td') and \
        tag.findNextSibling('td').findNextSibling('td').b and \
        tag.findNextSibling('td').findNextSibling('td').b.string != u'0'
    discounts = soup.table.table.table.findAll(find_discount)
    discounts = map(lambda td: (td.contents[-1], td.findNextSibling('td').findNextSibling('td').b.string), discounts)

    # output
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
    return order_price, point_saved, payment_method, money_spent, discounts


# login
username = raw_input('Username: ')
password = getpass.getpass()
opener = authorize(username, password)
del username, password

# orders
orders = []
path = order_path
while True:
    text = open_url(secure_url + path)
    partial_orders, (page_no, path) = parse_order_page(text)
    if len(partial_orders) == 0 or path is None:
        break
    logging.debug('%d orders for page %s' % (len(partial_orders), page_no))
    orders.extend(partial_orders)
logging.info(len(orders), 'orders')

earliest_date = min(order[1] for order in orders)
latest_date   = max(order[1] for order in orders)
prices_sum    = sum(int(order[2].replace(",", '')) for order in orders)
pkg_count     = sum(int(order[3]) for order in orders)
import locale; locale.setlocale(locale.LC_ALL, '')
print u"%s ~ %s 동안 %d번 주문: 총 %d개, %s원" % (earliest_date, latest_date, len(orders), pkg_count, locale.format("%d", prices_sum, True))

# order details
for i,order in enumerate(orders):
    text = open_url(get_order_detail_link(order[0]))
    parse_order_detail_page(text)


