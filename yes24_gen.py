#!/usr/bin/python
# -*- coding: utf-8 -*-
import getpass
import urllib, urllib2, cookielib
import sys, re, datetime
from BeautifulSoup import BeautifulSoup
import logging
import locale; locale.setlocale(locale.LC_ALL, '')

if '--debug' in sys.argv:
    logging.basicConfig(level=logging.DEBUG)

target_month = datetime.datetime.now().strftime("%Y.%m")

class Yes24:
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

    @staticmethod
    def get_order_detail_link(order_id):
        return Yes24.order_detail_url + "?ordNoH=" + order_id

    @staticmethod
    def get_deliver_state_link(order_id):
        return Yes24.default_url + 'Order/FTDelvTrcListFrame.aspx?OID='+order_id+"&TTL=L"



def open_url(opener, url):
    logging.debug('opening url: %s' % url)
    site = opener.open(url)
    text = site.read()
    logging.debug('read %d bytes' % len(text))
    return text.decode('cp949')

def authorize(username, password):
    cookie_jar = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))

    Yes24.login_data['SMemberID']       = username
    Yes24.login_data['SMemberPassword'] = password

    logging.debug('opening url: %s' % Yes24.login_url)
    resp = opener.open(Yes24.login_url, urllib.urlencode(Yes24.login_data))
    html = resp.read()
    logging.debug('read %d bytes' % len(html))

    if 'location.replace' not in html:
        logging.warning('"location.replace" not found in response body')
        return None
    else:
        return opener

def verify_login(opener, url):
    html = open_url(opener, url)
    # 로그아웃 돼 있으니 login하라고 뜬다
    if   'Login'  in html:  return False
    # 로그인 돼 있으니 logout할 수 있다고 뜬다
    elif 'Logout' in html:  return True
    else:
        raise Exception("로그인 여부를 판단할 수 없습니다.")


class OrderListPage:
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
    def parse_navi_info(text):
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
    def parse_order_info(text):
        ''' parse order list page and return list of orders --
        [(order_id, order_date, order_price, pkg_num, order_name)] '''

        # parse
        text = OrderListPage.crop(text)
        text = OrderListPage.massage(text)
        soup = BeautifulSoup(text)
    
        # order list
        orders = []
        order_list_table  = soup.table(id="MyOrderListTbl")[0]
        remove_bogus_rows = lambda tag: tag.name == u'tr' and len(tag.findAll('td')) != 1
        for tr in order_list_table.find('tr').findNextSiblings(remove_bogus_rows):
            order = OrderListPage.parse_single_order(tr)
            if order is None:
                continue
            orders.append( order )
        logging.debug("%d orders total." % len(orders))
        return orders

    @staticmethod
    def parse_single_order(tr):
        ''' parse and return (order_id, order_date, order_price, pkg_num, order_name) 
        from single table row in order list page
        
        returns None if order_date != target_date
        '''
        remove_bogus_cell = lambda tag: tag.name == u'td' and tag['width'] != u'1'
        tds = tr.findAll(remove_bogus_cell)
        order_id    = tds[0].b.string
        order_date  = tds[1].string
        order_name  = tds[2].span.string
        order_price = tds[3].b.string
        pkg_num     = tds[3].b.string.next.rsplit('/')[-1]
        if not str(order_date).startswith(target_month):
            return None
    
        logging.debug("#%(order_id)s - \"%(order_name)s\""  % locals())
        return (order_id, order_date, order_price, pkg_num, order_name)

    @staticmethod
    # generator
    def retrieve_order_list_page(opener, start_path):
        ''' yield text of next order list page '''
        path = start_path
        while path is not None:
            text = open_url(opener, Yes24.secure_url + path)
            yield text
    
            # find out next page
            page_no, path = OrderListPage.parse_navi_info(text)
    
    @staticmethod
    # generator
    def retrieve_orders(opener, start_path):
        ''' yield url of order detail page that starts with target date '''
        # order list page iterator
        order_list_page_texts = OrderListPage.retrieve_order_list_page(opener, start_path)
    
        for text in order_list_page_texts:
            orders = OrderListPage.parse_order_info(text)
            if orders == []:
                break

            for order in orders:
                yield order


class OrderPage:
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
        text = OrderPage.crop(text)
        text = OrderPage.massage(text)
        soup = BeautifulSoup(text)
    
        # order price
        order_price = soup.find(id="CLbTotOrdAmt").b.string

        text = ''.join(filter(lambda x: '<span id="CLbPayPrInfo">' in x, text.split("\r\n"))).strip()
        text = '<table>%s</table>' %s text[text[1:].find('<')+1:-7]
        soup = BeautifulSoup(text)

        # points saved
        point_saved = soup.find(attrs={'class':"price"}).b.string

        # money spent
        money_spent = u'0'
        priceB_el = soup.find(attrs={'class':"priceB"})
        if priceB_el is not None:
            money_spent = priceB.string

        # payment method
        payment_method = None
        payment_el = soup.find(text=re.compile(u'결제.*수단'))
        if payment_el is not None:
            payment_method = payment_el.parent.findNextSibling('td').next.replace("&nbsp;", '').strip()

        # discount
        find_discount = lambda tag: tag.name == u'td' and \
            tag.findNextSibling('td') and \
            tag.findNextSibling('td').findNextSibling('td') and \
            tag.findNextSibling('td').findNextSibling('td').b and \
            tag.findNextSibling('td').findNextSibling('td').b.string != u'0'
        discounts = soup.table.table.table.findAll(find_discount)
        discounts = map(lambda td: (td.contents[-1], td.findNextSibling('td').findNextSibling('td').b.string), discounts)
    
        return order_price, point_saved, payment_method, money_spent, discounts

# authorize
username = raw_input('Username: ')
password = getpass.getpass()
opener = authorize(username, password)
del username, password
assert opener != None, "not logged in!"

# orders from order list page
orders = OrderListPage.retrieve_orders(opener, start_path=Yes24.order_path)

# summary -- evaluate orders
orders = list(orders)
earliest_date = min(order[1] for order in orders)
latest_date   = max(order[1] for order in orders)
prices_sum    = sum(int(order[2].replace(",", '')) for order in orders)
pkg_count     = sum(int(order[3]) for order in orders)
print u"%s ~ %s 동안 %d번 주문: 총 %d개, %s원" % 
    (earliest_date, latest_date, len(orders), pkg_count, locale.format("%d", prices_sum, True))

# order detail page
order_ids   = (order[0] for order in orders)
order_urls  = (Yes24.get_order_detail_link(order_id) for order_id in order_ids)
order_pages = (open_url(opener, url) for url  in order_urls)
results     = (OrderPage.parse(text) for text in order_pages)

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


