# -*- coding: utf8 -*-

import re, requests, hashlib, datetime, random, upyun
from uuid import uuid4
from log import Syslog
from base64 import b32encode
from config import SSO, PLUGINS
from functools import wraps
from flask import g, request, redirect, url_for

ip_pat          = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
mail_pat        = re.compile(r"([0-9a-zA-Z\_*\.*\-*]+)@([a-zA-Z0-9\-*\_*\.*]+)\.([a-zA-Z]+$)")
user_pat        = re.compile(r'[a-zA-Z\_][0-9a-zA-Z\_]')
comma_pat       = re.compile(r"\s*,\s*")
logger          = Syslog.getLogger()
md5             = lambda pwd:hashlib.md5(pwd).hexdigest()
gen_token       = lambda n=32:b32encode(uuid4().hex)[:n]
gen_requestId   = lambda :str(uuid4())
get_today       = lambda :datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
gen_rnd_filename= lambda :"%s%s" %(datetime.datetime.now().strftime('%Y%m%d%H%M%S'), str(random.randrange(1000, 10000)))
ListEqualSplit  = lambda l,n=5: [ l[i:i+n] for i in range(0,len(l), n) ]


def ip_check(ip):
    if isinstance(ip, (str, unicode)):
        return ip_pat.match(ip)

def isLogged_in(cookie_str):
    ''' check username is logged in '''

    SSOURL = SSO.get("SSO.URL")
    if cookie_str and not cookie_str == '..':
        username, expires, sessionId = cookie_str.split('.')
        #success = Requests(SSOURL+"/sso/").post(data={"username": username, "time": expires, "sessionId": sessionId}).get("success", False)
        success = requests.post(SSOURL+"/sso/", data={"username": username, "time": expires, "sessionId": sessionId}, timeout=5, verify=False, headers={"User-Agent": "Template"}).json().get("success", False)
        logger.info("check login request, cookie_str: %s, success:%s" %(cookie_str, success))
        return success
    else:
        logger.info("Not Logged in")
        return False

def ParseMySQL(mysql, callback="dict"):
    protocol, dburl = mysql.split("://")
    if "?" in mysql:
        dbinfo, dbargs  = dburl.split("?")
    else:
        dbinfo, dbargs  = dburl, "charset=utf8&timezone=+8:00"
    host,port,user,password,database = dbinfo.split(":")
    charset, timezone = dbargs.split("&")[0].split("charset=")[-1] or "utf8", dbargs.split("&")[-1].split("timezone=")[-1] or "+8:00"
    if callback in ("list", "tuple"):
        return protocol,host,port,user,password,database,charset, timezone
    else:
        return {"Protocol": protocol, "Host": host, "Port": port, "Database": database, "User": user, "Password": password, "Charset": charset, "Timezone": timezone}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.signin:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.signin and g.username in g.api.user_get_admins().get("data", []):
            return f(*args, **kwargs)
        else:
            return redirect(url_for('login', next=request.url))
    return decorated_function

def UploadImage2Upyun(FilePath, FileData, kwargs=PLUGINS['UpYunStorage']):
    """ Upload image to Upyun Cloud with Api """

    up  = upyun.UpYun(kwargs.get("bucket"), username=kwargs.get("username"), password=kwargs.get("password"), timeout=10, endpoint=upyun.ED_AUTO)
    res = up.put(FilePath, FileData)
    return res

def BaiduActivePush(pushUrl, original=True, callUrl=PLUGINS['BaiduActivePush']['callUrl']):
    """百度主动推送(实时)接口提交链接"""
    callUrl = callUrl + "&type=original" if original else callUrl
    res = requests.post(url=callUrl, data=pushUrl, timeout=3, headers={"User-Agent": "BaiduActivePush/www.saintic.com"}).json()
    logger.info("BaiduActivePush PushUrl is %s, Result is %s" % (pushUrl, res))
    return res
