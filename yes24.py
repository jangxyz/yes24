#!/usr/bin/python
# -*- coding: utf-8 -*-
import urllib, urllib2, cookielib
import re
from BeautifulSoup import BeautifulSoup
import logging

##
## Constants
##
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

# used counting url_open
open_url_count = 0
read_bytes = 0

def get_order_detail_link(order_id):
    return order_detail_url + "?ordNoH=" + order_id

def get_deliver_state_link(order_id):
    return default_url + 'Order/FTDelvTrcListFrame.aspx?OID='+order_id+"&TTL=L"

def open_url(opener, url):
    global open_url_count, read_bytes
    logging.debug('opening url: %s' % url)
    error_count = 3
    for retry_count in range(error_count):
        try:
            site = opener.open(url)
            open_url_count += 1
            break
        except urllib2.URLError, e:
            logging.error("#%d failed to open url %s, retyring.." % retry_count+1, url)
            continue

    text = site.read()
    read_bytes += len(text)
    logging.debug('read %d bytes' % len(text))
    return text.decode('cp949')

def authorize(username, password):
    ''' authorize Yes24 with username and password, and return the opener '''
    cookie_jar = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))

    login_data['SMemberID']       = username
    login_data['SMemberPassword'] = password

    logging.debug('opening url: %s' % login_url)
    resp = opener.open(login_url, urllib.urlencode(login_data))
    html = resp.read()
    logging.debug('read %d bytes' % len(html))

    login_data['SMemberID']       = None
    login_data['SMemberPassword'] = None
    del username, password


    if 'location.replace' not in html:
        logging.warning('"location.replace" not found in response body. maybe login fail?')
        return None
    else:
        return opener

def verify_login(opener, url):
    html = opener.open(url).read()
    # 로그아웃 돼 있으니 login하라고 뜬다
    if   'Login'  in html:  return False
    # 로그인 돼 있으니 logout할 수 있다고 뜬다
    elif 'Logout' in html:  return True
    else:
        raise Exception("로그인 여부를 판단할 수 없습니다.")


##
## Generators
##
def retrieve_order_list_pages(opener, path):
    ''' yields text of next order list page '''
    while path is not None:
        text = open_url(opener, secure_url + path)
        yield text
        # find out next page
        page_no, path = OrderListPage.navi_info(text)

def retrieve_orders(opener, target_month):
    ''' yields url of order detail page that starts with target date '''
    start_path = order_path
    # order list page iterator
    order_list_page_texts = retrieve_order_list_pages(opener, start_path)

    for text in order_list_page_texts:
        orders = OrderListPage.order_info(text, target_month)
        if orders == []:
            break

        for order in orders:
            yield order


class Order:
    def __init__(self):
        self.id      = None
        self.price   = None
        self.count   = None
        self.title   = None
        self.date    = None

        self.payment = None

    def page_url(self):
        return get_order_detail_link(self.id)

    def deliver_state_url(self):
        return get_deliver_state_link(self.id)

    @classmethod
    def build_from_order_list_page(cls, tr, target_month):
        ''' parse and return Order instance from single table row in order list page
        returns None if date != target_date
        '''
        order = Order()

        remove_bogus_cell = lambda tag: tag.name == u'td' and tag['width'] != u'1'
        tds = tr.findAll(remove_bogus_cell)

        order.id    = tds[0].b.string
        order.title = tds[2].span.string
        order.price = int( tds[3].b.string.replace(',', '') )
        order.count = int( tds[3].b.string.next.rsplit('/')[-1] )
        order.date  = tds[1].string

        # check target month
        if target_month is not None:
            if not str(order.date).startswith(target_month):
                return None
    
        return order

    def parse_detail_page(self, opener):
        text = open_url(opener, self.page_url())
        self.payment = OrderPage.parse(text)
        if self.price != self.payment.price:
            logging.warn("price is different: %s vs %s" % (self.price, self.payment.price))
        return self


class Payment:
    def __init__(self):
        self.price  = None
        self.method = None
        self.discounts = None
        self.amount = None
        self.points_saved = None

#
# Page parse
#

class OrderPage:
    ''' namespace holding methods to help parsing '''
    @staticmethod
    def massage(text):
        # lacks double-quote(")
        text = text.replace(
            '''<table cellpadding="0" cellspacing=0" border="0" >''', 
            '''<table cellpadding="0" cellspacing="0" border="0" >'''
        )
        return text

    @staticmethod
    def crop(text):
        start_pattern = '''<span id="infoQuickDlv"'''
        end_pattern   = '''<script Language=javascript>'''

        start_idx = text.find(start_pattern)
        if start_idx == -1:
            raise Exception('cannot find start pattern from: %s' % start_pattern)

        end_idx = text[start_idx:].find(end_pattern)
        if end_idx == -1:
            raise Exception('cannot find end pattern from: %s' % end_pattern)
        end_idx += start_idx

        text = text[start_idx:end_idx]
        return text

    @staticmethod
    def parse(text):
        payment = Payment()

        text = OrderPage.crop(text)
        text = OrderPage.massage(text)
        soup = BeautifulSoup(text)

        str2int = lambda x: int(x.replace(",", ""))
    
        # order price
        payment.price = soup.find(id="CLbTotOrdAmt").b.string
        payment.price = str2int(payment.price)

        text = ''.join(filter(lambda x: '<span id="CLbPayPrInfo">' in x, text.split("\r\n"))).strip()
        text = '<table>%s</table>' % text[text[1:].find('<')+1:-7]
        soup = BeautifulSoup(text)

        # points saved
        payment.point_saved = soup.find(attrs={'class':"price"}).b.string
        payment.point_saved = str2int(payment.point_saved)

        # money spent
        payment.amount = 0
        priceB_el = soup.find(attrs={'class':"priceB"})
        if priceB_el is not None:
            payment.amount = priceB_el.string
            payment.amount = str2int(payment.amount)

        # payment method
        payment.method = None
        payment_el = soup.find(text=re.compile(u'결제.*수단'))
        if payment_el is not None:
            payment.method = payment_el.parent.findNextSibling('td').next.replace("&nbsp;", '').strip()

        # discounts: (name, amount)
        find_discount = lambda tag: tag.name == u'td' and \
            tag.findNextSibling('td') and \
            tag.findNextSibling('td').findNextSibling('td') and \
            tag.findNextSibling('td').findNextSibling('td').b and \
            tag.findNextSibling('td').findNextSibling('td').b.string != u'0'
        payment.discounts = soup.table.table.table.findAll(find_discount)
        payment.discounts = map(
            lambda td: (
                td.contents[-1].strip(), 
                str2int(td.findNextSibling('td').findNextSibling('td').b.string.strip())
            ), payment.discounts)
    
        return payment



class OrderListPage:
    ''' a namespace holding methods to help parsing '''
    @staticmethod
    def crop(text):
        start_pattern = '''<div id="ordList"'''
        end_pattern   = '''<script language='JavaScript'>'''

        start_idx = text.find(start_pattern)
        if start_idx == -1:
            raise Exception('cannot find start pattern from: %s' % start_pattern)

        end_idx = text[start_idx:].find(end_pattern)
        if end_idx == -1:
            raise Exception('cannot find end pattern from: %s' % end_pattern)
        end_idx += start_idx

        text = text[start_idx:end_idx]
        return text

    @staticmethod
    def massage(text):
        text = text.replace(
            '''<a style="cursor:hand";''', 
            '''<a style="cursor:hand"'''
        )
        return text

    @staticmethod
    def navi_info(text):
        # parse
        text = OrderListPage.crop(text)
        text = OrderListPage.massage(text)
        soup = BeautifulSoup(text)

        page_navigator_table = soup.table(id="tblNavigator")[0]
        current_page_anchor  = page_navigator_table.find('a', href=None)
        next_page_anchor     = current_page_anchor.findNextSibling('a')
        next_page_href = next_page_anchor["href"] if next_page_anchor else None
    
        navi_info = (current_page_anchor.string, next_page_href)
        logging.debug("current page: #%s, next page: %s" % navi_info)
        return navi_info
        
    @staticmethod
    def order_info(text, target_month):
        ''' parse order list page and return list of Order objects '''

        # parse
        text = OrderListPage.crop(text)
        text = OrderListPage.massage(text)
        soup = BeautifulSoup(text)
    
        # order list
        orders = []
        order_list_table  = soup.table(id="MyOrderListTbl")[0]
        remove_bogus_rows = lambda tag: tag.name == u'tr' and len(tag.findAll('td')) != 1
        for tr in order_list_table.find('tr').findNextSiblings(remove_bogus_rows):
            order = Order.build_from_order_list_page(tr, target_month)
            if order is None:
                continue
            orders.append( order )

        logging.debug("%d orders total." % len(orders))
        return orders

