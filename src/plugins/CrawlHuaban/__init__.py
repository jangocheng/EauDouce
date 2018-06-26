# -*- coding: utf-8 -*-
"""
    EauDouce.plugins.CrawlHuaban
    ~~~~~~~~~~~~~~

    抓取花瓣、堆糖图片

    :copyright: (c) 2018 by taochengwei.
    :license: MIT, see LICENSE for more details.
"""

from __future__ import absolute_import
from libs.base import PluginBase
import os, json
from config import PLUGINS
from utils.qf import DownloadBoard, DownloadBoardAddTimes
from utils.tool import logger, get_current_timestamp, timestamp_after_timestamp, timestamp_to_timestring
from flask import Blueprint, jsonify, request, make_response, url_for, send_from_directory
from werkzeug import secure_filename

__name__ = "CrawlHuaban"
__description__ = "抓取花瓣、堆糖图片并压缩提供下载"
__author__ = "Mr.tao"
__version__ = "0.2"
__license__ = "MIT"
if PLUGINS["CrawlHuaban"] in ("true", "True", True):
    __state__ = "enabled"
else:
    __state__ = "disabled"

pb = PluginBase()
basedir = os.path.dirname(os.path.abspath(__file__))
CrawlHuabanBlueprint = Blueprint("CrawlHuaban", "CrawlHuaban")
@CrawlHuabanBlueprint.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        """ 下载图片压缩文件
        :board_id(str):  下载分类(子)目录，比如attachment、script
        :filename(str): 下载的实际文件(不需要目录，目录由catalog指定)，包含扩展名
        当前目录是EauDouce/src/plugins/CrawlHuaban/，作为根。
        1. 以board_id为子，进去子目录下载保存；
        2. 返回根目录，压缩board_id目录成文件，再移动到board_id下。
        """
        # 下载画板
        board_id = secure_filename(str(request.args.get("board_id", "")))
        # 下载文件名
        filename = secure_filename(request.args.get("filename", ""))
        if board_id and filename:
            # 下载文件存放目录
            directory = os.path.join(basedir, board_id)
            logger.sys.debug("Want to download a file with directory: {0}, filename: {1}".format(directory, filename))
            headers = ("Content-Disposition", "attachment;filename={}".format(filename))
            if os.path.isfile(os.path.join(directory, filename)):
                pb.asyncQueue.enqueue_call(func=DownloadBoardAddTimes, args=(board_id, filename, get_current_timestamp()))
                response = make_response(send_from_directory(directory=directory, filename=filename, as_attachment=True))
                response.headers[headers[0]] = headers[1]
            else:
                response = make_response("Not Found File")
        else:
            response = make_response("Invalid Download Request")
        return response
    else:
        res = dict(success=False, msg=None)
        try:
            #site站点，花瓣网1、堆糖网2
            site = int(request.form.get("site", 1))
            #version脚本版本
            version = request.form.get("version", "")
            #以下board同album，不区分
            board_id = str(request.form.get("board_id", ""))
            board_pins = json.loads(request.form.get("pins"))
            board_total = int(request.form.get("board_total", 0))
            if board_id and board_pins:
                if not isinstance(board_pins, (list, tuple)):
                    raise ValueError
            else:
                raise ValueError
        except ValueError:
            res.update(msg="Invalid data")
        except Exception, e:
            logger.sys.error(e, exc_info=True)
            res.update(msg="Unknown error, please contact staugur@saintic.com, thanks!")
        else:
            logger.sys.debug("dir: {}, site: {}, version: {}, board_id: {}, board_pins number: {}".format(basedir, site, version, board_id, len(board_pins)))
            #将site+board_id存入redis，限定时间内不允许重复下载
            key = "EauDouce:CrawlHuaban:{site}:{board_id}".format(site=site, board_id=board_id)
            hasKey = False
            try:
                hasKey = pb.redis.exists(key)
            except Exception,e:
                logger.sys.error(e, exc_info=True)
            if hasKey:
                data = pb.redis.hgetall(key)
                res.update(success=True, downloadUrl=data["downloadUrl"], expireTime=data["expireTime"], msg="Qualified Repetition")
            else:
                ctime = get_current_timestamp()
                etime = timestamp_after_timestamp(hours=24)
                filename = "{}_{}.zip".format(board_id, ctime)
                expireTime = timestamp_to_timestring(etime)
                downloadUrl = url_for("CrawlHuaban.index", board_id=board_id, filename=filename, _external=True)
                pipe = pb.redis.pipeline()
                pipe.hmset(key, dict(downloadUrl=downloadUrl, expireTime=expireTime))
                pipe.expire(key, 60)
                try:
                    pipe.execute()
                except Exception,e:
                    logger.sys.error(e, exc_info=True)
                finally:
                    pb.asyncQueueHigh.enqueue_call(func=DownloadBoard, args=(basedir, board_id, filename, board_pins, board_total, ctime, etime, version, site), timeout=3600)
                    res.update(success=True, downloadUrl=downloadUrl, expireTime=expireTime)
        logger.sys.info(res)
        return jsonify(res)


def getPluginClass():
    return CrawlHuabanMain


class CrawlHuabanMain(PluginBase):
    """ 抓取花瓣网画板图片 """

    def register_bep(self):
        """ 注册一个查询uv接口 """
        return {"prefix": "/CrawlHuaban", "blueprint": CrawlHuabanBlueprint}
