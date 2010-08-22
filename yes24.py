#!/usr/bin/python
# -*- coding: utf-8 -*-
import urllib, urllib2, cookielib
import re
from BeautifulSoup import BeautifulSoup
import logging

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

    @staticmethod
    def open_url(opener, url):
        logging.debug('opening url: %s' % url)
        site = opener.open(url)
        text = site.read()
        logging.debug('read %d bytes' % len(text))
        return text.decode('cp949')


    @staticmethod
    def authorize(username, password):
        ''' authorize Yes24 with username and password, and return the opener '''
        cookie_jar = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
    
        Yes24.login_data['SMemberID']       = username
        Yes24.login_data['SMemberPassword'] = password
    
        logging.debug('opening url: %s' % Yes24.login_url)
        resp = opener.open(Yes24.login_url, urllib.urlencode(Yes24.login_data))
        html = resp.read()
        logging.debug('read %d bytes' % len(html))
    
        if 'location.replace' not in html:
            logging.warning('"location.replace" not found in response body. maybe login fail?')
            return None
        else:
            return opener

    @staticmethod
    def verify_login(opener, url):
        html = opener.open(url).read()
        # 로그아웃 돼 있으니 login하라고 뜬다
        if   'Login'  in html:  return False
        # 로그인 돼 있으니 logout할 수 있다고 뜬다
        elif 'Logout' in html:  return True
        else:
            raise Exception("로그인 여부를 판단할 수 없습니다.")


class OrderListPage:
    @staticmethod
    # generator
    def retrieve_order_list_pages(opener, path):
        ''' yield text of next order list page '''
        while path is not None:
            text = Yes24.open_url(opener, Yes24.secure_url + path)
            yield text
            # find out next page
            page_no, path = OrderListPage.Parse.navi_info(text)
    
    @staticmethod
    # generator
    def retrieve_orders(opener, target_month):
        ''' yield url of order detail page that starts with target date '''
        start_path = Yes24.order_path
        # order list page iterator
        order_list_page_texts = OrderListPage.retrieve_order_list_pages(opener, start_path)
    
        for text in order_list_page_texts:
            orders = OrderListPage.Parse.order_info(text, target_month)
            if orders == []:
                break

            for order in orders:
                yield order


    class Parse:
        ''' class (more like a namespace) holding methods to help parsing '''
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
            text = OrderListPage.Parse.crop(text)
            text = OrderListPage.Parse.massage(text)
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
            ''' parse order list page and return list of orders --
            [(order_id, order_date, order_price, pkg_num, order_name)] '''

            # parse
            text = OrderListPage.Parse.crop(text)
            text = OrderListPage.Parse.massage(text)
            soup = BeautifulSoup(text)
        
            # order list
            orders = []
            order_list_table  = soup.table(id="MyOrderListTbl")[0]
            remove_bogus_rows = lambda tag: tag.name == u'tr' and len(tag.findAll('td')) != 1
            for tr in order_list_table.find('tr').findNextSiblings(remove_bogus_rows):
                #order = OrderListPage.Parse.single_order(tr, target_month)
                order = Order.build_from_order_list_page(tr, target_month)
                if order is None:
                    continue
                orders.append( order )
            logging.debug("%d orders total." % len(orders))
            return orders

        #@staticmethod
        #def single_order(tr, target_month):
        #    ''' parse and return Order instance from single table row in order list page
        #    
        #    returns None if order_date != target_date
        #    '''

        #    order = Order()

        #    remove_bogus_cell = lambda tag: tag.name == u'td' and tag['width'] != u'1'
        #    tds = tr.findAll(remove_bogus_cell)
        #    order.id    = tds[0].b.string
        #    order.order_date  = tds[1].string
        #    order.title = tds[2].span.string
        #    order.price = tds[3].b.string
        #    order.count = tds[3].b.string.next.rsplit('/')[-1]

        #    # check target month
        #    if target_month is not None:
        #        if not str(order.order_date).startswith(target_month):
        #            return None
        #
        #    #logging.debug("#%(order_id)s - \"%(order_name)s\""  % locals())
        #    return order
        #    #return (order_id, order_date, order_price, pkg_num, order_name)

class Order:
    def __init__(self):
        self.id = None
        self.order_date = None
        self.price = None
        self.count = None
        self.title = None

        self.payment = Payment()

    @classmethod
    def build_from_order_list_page(cls, tr, target_month):
        ''' parse and return Order instance from single table row in order list page
        
        returns None if order_date != target_date
        '''

        order = Order()

        remove_bogus_cell = lambda tag: tag.name == u'td' and tag['width'] != u'1'
        tds = tr.findAll(remove_bogus_cell)
        order.id    = tds[0].b.string
        order.order_date  = tds[1].string
        order.title = tds[2].span.string
        order.price = tds[3].b.string
        order.count = tds[3].b.string.next.rsplit('/')[-1]

        # check target month
        if target_month is not None:
            if not str(order.order_date).startswith(target_month):
                return None
    
        return order


    class PageParse:
        ''' class (more like a namespace) holding methods to help parsing '''
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
            text = Order.PageParse.crop(text)
            text = Order.PageParse.massage(text)
            soup = BeautifulSoup(text)
        
            # order price
            order_price = soup.find(id="CLbTotOrdAmt").b.string

            text = ''.join(filter(lambda x: '<span id="CLbPayPrInfo">' in x, text.split("\r\n"))).strip()
            text = '<table>%s</table>' % text[text[1:].find('<')+1:-7]
            soup = BeautifulSoup(text)

            # points saved
            point_saved = soup.find(attrs={'class':"price"}).b.string

            # money spent
            money_spent = u'0'
            priceB_el = soup.find(attrs={'class':"priceB"})
            if priceB_el is not None:
                money_spent = priceB_el.string

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


class Payment:
    def __init__(self):
        self.price  = None
        self.method = None
        self.discount  = None
        self.cash_paid = None
        self.points_saved = None

