# coding: UTF-8
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import routing
import urllib3
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import six
from six.moves.urllib.parse import urlencode

urllib3.disable_warnings()

from .helper import Helper

base_url = sys.argv[0]
try:
    handle = int(sys.argv[1])
except:
    handle = None  # or whatever you want to do
helper = Helper(base_url, handle)
plugin = routing.Plugin()


def getTime(x, y):
    if y == 'date':
        data = '%Y-%m-%d'
    elif y == 'hour':
        data = '%H:%M'
    return datetime.fromtimestamp(x).strftime(data)


def channelList():
    timestamp = int(time.time())
    json_data = {
        'epg_limit_prev': 10,
        'epg_limit_next': 100,
        'epg_current_time': timestamp,
        'need_epg': True,
        'need_list': True,
        'need_categories': True,
        'need_offsets': False,
        'need_hash': False,
        'need_icons': False,
        'need_big_icons': False,
    }

    url = helper.base_api_url.format('TvService/GetChannels.json')
    jsdata = helper.request_sess(url, 'post', headers=helper.headers, data=json_data, json=True, json_data=True)

    categories = {}

    if jsdata.get("status", None) == 'OK':
        if "categories" in jsdata:
            for category in jsdata.get('categories', None):
                categories.update({category.get('id', None): category.get('caption', None)})

        if "list" in jsdata:
            xml_root = ET.Element("tv")
            for json_channel in jsdata.get("list"):
                channel = ET.SubElement(xml_root, "channel",
                                        attrib={"id": six.text_type(json_channel.get("id")) + ".id.com"})
                ET.SubElement(channel, "display-name", lang=helper.countryCode).text = json_channel.get("name")
                ET.SubElement(channel, "icon", src=json_channel.get("icon_url"))
            for json_channel in jsdata.get("list"):
                if "epg" in json_channel:
                    for json_epg in json_channel.get("epg"):
                        if json_channel.get("catchup") and json_channel.get("available"):
                            catchup = {"catchup-id": six.text_type(json_epg.get("id"))}
                        else:
                            catchup = {"catchup-id": "null"}

                        programme_metadata = {
                            "start": time.strftime('%Y%m%d%H%M%S',
                                                   time.localtime(json_epg.get("time_start"))) + " +0100",
                            "stop": time.strftime('%Y%m%d%H%M%S',
                                                  time.localtime(json_epg.get("time_stop") - 1)) + " +0100",
                            "channel": six.text_type(json_channel.get("id")) + ".id.com"
                        }
                        programme_metadata.update(catchup)

                        programme = ET.SubElement(xml_root, "programme", attrib=programme_metadata)
                        if json_epg.get("available") == False and json_channel.get("live_blackout") == True:
                            ET.SubElement(programme, "title",
                                          lang=helper.countryCode).text = "!NOT AVAILABLE! " + json_epg.get(
                                "text")
                        else:
                            ET.SubElement(programme, "title", lang=helper.countryCode).text = json_epg.get("text")
                else:
                    programme = ET.SubElement(xml_root, "programme", attrib={
                        "start": time.strftime('%Y%m%d%H%M%S', time.localtime(time.time())) + " +0100",
                        "stop": time.strftime('%Y%m%d%H%M%S', time.localtime(time.time() + (12 * 60 * 60))) + " +0100",
                        "channel": six.text_type(json_channel.get("id")) + ".id.com"})
                    ET.SubElement(programme, "title", lang=helper.countryCode).text = json_channel.get("name")

            tree = ET.ElementTree(xml_root)
            if sys.version_info[:3] >= (3, 9, 0):
                ET.indent(tree, space="  ", level=0)
            xmlstr = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(xml_root, encoding='utf-8')
            path_m3u = helper.get_setting('path_m3u')
            file_name = helper.get_setting('name_epg')
            if path_m3u != '' and file_name != '':
                f = xbmcvfs.File(path_m3u + file_name, 'w')
                f.write(xmlstr)
                f.close()

            data = '#EXTM3U\n'
            for json_channel in jsdata.get("list"):
                if json_channel.get('available', None):
                    img = json_channel.get('icon_v2_url', None)
                    cName = json_channel.get('name', None)
                    cid = json_channel.get('id', None)
                    category_list = ''
                    for category in json_channel.get('category', None):
                        if category in categories and category != 1000:
                            category_list += categories[category] + ';'
                    category_list = category_list[:-1]

                    if json_channel.get('catchup', None):
                        catchup = 'catchup="default" catchup-days="%d" catchup-source="plugin://plugin.video.sweettv/playvid/%s|{catchup-id}"' % (
                            int(json_channel.get('catchup_duration')), cid)
                    else:
                        catchup = ''
                    data += '#EXTINF:0 tvg-id="%s.id.com" tvg-name="%s" tvg-logo="%s" group-title="%s" %s,%s\nplugin://plugin.video.sweettv/playvid/%s|null\n' % (
                        cid, cName, img, category_list, catchup, cName, cid)

          # Step 1: Ensure 'data' is Unicode (if it's not already)
            if isinstance(data, str):  # If it's a byte string
                data = data.decode('utf-8')  # Convert to Unicode

          # Step 2: Encode the data to UTF-8
            if isinstance(data, unicode):  # If it's a Unicode string
                data = data.encode('utf-8')  # Convert to UTF-8 byte string
            file_name = helper.get_setting('name_m3u')
            if path_m3u != '' and file_name != '':
                f = xbmcvfs.File(path_m3u + file_name, 'w')
                f.write(data)
                f.close()
    else:
        xbmc.log("Failed to update channel list", xbmc.LOGERROR)
        xbmc.log("Failed to update channel list " + six.text_type(jsdata), xbmc.LOGDEBUG)

    return jsdata


@plugin.route('/')
def root():
    CreateDatas()

    refresh_token = helper.get_setting('refresh_token')

    xbmc.log("refresh " + refresh_token, xbmc.LOGDEBUG)
    xbmc.log("logged " + six.text_type(helper.get_setting('logged')), xbmc.LOGDEBUG)

    if refresh_token == 'None':
        helper.set_setting('bearer', '')
        helper.set_setting('logged', 'false')

    if helper.get_setting('logged'):
        startwt()
    else:
        helper.add_item('[COLOR lightgreen][B]Login[/COLOR][/B]', plugin.url_for(login), folder=False)
        helper.add_item('[B]Settings[/B]', plugin.url_for(settings), folder=False)

    helper.eod()


def CreateDatas():
    if not helper.uuid:
        import uuid
        uuidx = uuid.uuid4()
        helper.set_setting('uuid', six.text_type(uuidx))
    return


@plugin.route('/startwt')
def startwt():
    helper.add_item('[B]TV[/B]', plugin.url_for(mainpage, id='live'), folder=True)
    helper.add_item('[B]Replay[/B]', plugin.url_for(mainpage, id='replay'), folder=True)
    helper.add_item('[B]Logout[/B]', plugin.url_for(logout), folder=False)


def refreshToken():
    json_data = helper.json_data
    json_data.update({"refresh_token": helper.get_setting('refresh_token')})

    jsdata = helper.request_sess(helper.token_url, 'post', headers=helper.headers, data=json_data, json=True,
                                 json_data=True)
    xbmc.log("refresh " + six.text_type(jsdata), xbmc.LOGDEBUG)

    if jsdata.get("result", None) == 'COMPLETED' or jsdata.get("result", None) == 'OK':
        xbmc.log("Token refresh success", xbmc.LOGDEBUG)
        access_token = jsdata.get("access_token")
        helper.set_setting('bearer', 'Bearer ' + six.text_type(access_token))
        helper.headers.update({'authorization': helper.get_setting('bearer')})

        channelList()
        return True
    else:
        xbmc.log("Token refresh failed", xbmc.LOGERROR)
        return False


@plugin.route('/getEPG/<id>')
def getEPG(id):
    id, dur = id.split('|')
    timestamp = int(time.time())
    json_data = {
        "channels": [
            int(id)
        ],
        "epg_current_time": timestamp,
        "need_big_icons": False,
        "need_categories": False,
        "need_epg": True,
        "need_icons": False,
        "need_list": True,
        "need_offsets": False
    }
    url = 'https://api.sweet.tv/TvService/GetChannels.json'
    jsdata = helper.request_sess(url, 'post', headers=helper.headers, data=json_data, json=True, json_data=True)

    if jsdata.get("code", None) == 16:
        helper.set_setting('bearer', '')
        refr = refreshToken()
        if refr:
            mainpage(id)
        else:
            return
    if jsdata.get("status", None) == 'OK':
        progs = jsdata['list'][0]['epg']
        for p in progs:
            now = int(time.time())
            tStart = p.get('time_start', None)
            if p['available'] == True and tStart >= now - int(dur) * 24 * 60 * 60 and tStart <= now:
                pid = six.text_type(p.get('id', None))
                tit = p.get('text', None)
                date = getTime(p.get('time_start', None), 'date')
                ts = getTime(p.get('time_start', None), 'hour')
                te = getTime(p.get('time_stop', None), 'hour')
                title = '[COLOR=gold]%s[/COLOR] | [B]%s-%s[/B] %s' % (date, ts, te, tit)
                ID = id + '|' + pid

                mod = plugin.url_for(playvid, id=ID)
                fold = False
                ispla = True
                imag = p.get('preview_url', None)
                art = {'icon': imag, 'fanart': helper.addon.getAddonInfo('fanart')}

                info = {'title': title, 'plot': ''}

                helper.add_item(title, mod, playable=ispla, info=info, art=art, folder=fold, content='videos')

    helper.eod()


@plugin.route('/mainpage/<id>')
def mainpage(id):
    jsdata = channelList()

    if jsdata.get("code", None) == 16:
        helper.set_setting('bearer', '')
        refr = refreshToken()
        if refr:
            mainpage(id)
        else:
            return

    if jsdata.get("status", None) == 'OK':
        for j in jsdata.get('list', []):
            catchup = j.get('catchup', None)
            available = j.get('available', None)
            isShow = False
            if (id == 'replay' and catchup and available) or (id == 'live' and available):
                isShow = True
            if isShow:
                _id = six.text_type(j.get('id', None))
                title = j.get('name', None)
                slug = j.get('slug', None)
                epgs = j.get('epg', None)
                epg = ''
                if id == 'live' and epgs:
                    for e in epgs:
                        if e.get('time_stop', None) > int(time.time()):
                            tit = e.get('text', None)
                            ts = getTime(e.get('time_start', None), 'hour')
                            te = getTime(e.get('time_stop', None), 'hour')
                            epg += '[B]%s-%s[/B] %s\n' % (ts, te, tit)

                if id == 'live':
                    idx = _id + '|null'  # +slug
                    mod = plugin.url_for(playvid, id=idx)
                    fold = False
                    ispla = True
                else:  # id=='replay'
                    dur = six.text_type(j.get('catchup_duration', None))
                    idx = _id + '|' + dur
                    mod = plugin.url_for(getEPG, id=idx)
                    fold = True
                    ispla = False

                imag = j.get('icon_v2_url', None)
                art = {'icon': imag, 'fanart': helper.addon.getAddonInfo('fanart')}

                info = {'title': title, 'plot': epg}

                helper.add_item('[COLOR gold][B]' + title + '[/COLOR][/B]', mod, playable=ispla, info=info, art=art,
                                folder=fold)

    helper.eod()


@plugin.route('/empty')
def empty():
    return


@plugin.route('/settings')
def settings():
    helper.open_settings()
    helper.refresh()


@plugin.route('/logout')
def logout():
    log_out = helper.dialog_choice('Logout', 'Do you want to log out?', agree='Yes', disagree='No')
    if log_out:
        json_data = {"refresh_token": helper.get_setting('refresh_token')}
        helper.request_sess(helper.logout_url, 'post', headers=helper.headers, data=json_data, json=True,
                            json_data=True)
        helper.set_setting('bearer', '')
        helper.set_setting('logged', 'false')
        helper.refresh()


@plugin.route('/login')
def login():
    jsdata = helper.request_sess(helper.auth_url, 'post', headers=helper.headers, data=helper.json_data, json=True,
                                 json_data=True)
    auth_code = jsdata.get("auth_code")
    if jsdata.get("result") != 'OK' or not auth_code:
        helper.notification('Information', 'Login error')
        helper.set_setting('logged', 'false')
        return
    dialog = xbmcgui.Dialog()
    # show loading dialog
    pDialog = xbmcgui.DialogProgress()
    pDialog.create('Sweet.tv', "Enter code: {}".format(auth_code))
    # wait for user to enter code
    jsdata = {"auth_code": auth_code}
    from json import dumps
    json_data = dumps(jsdata, separators=(',', ':'))
    result = None
    headers = helper.headers
    headers.update({'Content-Type': 'application/json'})

    while not result:
        if pDialog.iscanceled():
            helper.notification('Information', 'Login interrupted')
            helper.set_setting('logged', 'false')
            return
        jsdata = helper.request_sess(helper.check_auth_url, 'post', headers=headers, data=json_data, json=True,
                                     json_data=False)
        sys.stderr.write(six.text_type(jsdata))
        if jsdata.get("result") == "COMPLETED":
            result = jsdata
        else:
            time.sleep(3)

    if result.get("result") == 'COMPLETED':

        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        helper.set_setting('bearer', 'Bearer ' + six.text_type(access_token))
        helper.set_setting('refresh_token', six.text_type(refresh_token))
        helper.set_setting('logged', 'true')

    else:

        info = jsdata.get('result', None)
        helper.notification('Information', info)

        helper.set_setting('logged', 'false')

    helper.refresh()


@plugin.route('/playvid/<id>')
def playvid(id):
    DRM = None
    lic_url = None
    PROTOCOL = 'mpd'
    subs = None

    if not helper.get_setting('logged'):
        xbmcgui.Dialog().notification('Sweet.tv', 'Log in to the plugin', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.setResolvedUrl(helper.handle, False, xbmcgui.ListItem())
    else:
        idx, pid = id.split('|')
        json_data = {
            'without_auth': True,
            'channel_id': int(idx),
            # 'accept_scheme': ['HTTP_HLS',],
            'multistream': True,
        }
        vod = False
        if pid != 'null':
            json_data.update({'epg_id': int(pid)})
            vod = True

        url = helper.base_api_url.format('TvService/OpenStream.json')
        jsdata = helper.request_sess(url, 'post', headers=helper.headers, data=json_data, json=True, json_data=True)

        if jsdata.get("code", None) == 16:
            helper.set_setting('bearer', '')
            refr = refreshToken()
            if refr:
                playvid(id)
            else:
                return

        if jsdata.get("code", None) == 13:
            xbmcgui.Dialog().notification('Sweet.tv', 'Recording unavailable', xbmcgui.NOTIFICATION_INFO)
            xbmcplugin.setResolvedUrl(helper.handle, False, xbmcgui.ListItem())
        if jsdata.get("result", None) == 'OK':
            host = jsdata.get('http_stream', None).get('host', None).get('address', None)
            nt = jsdata.get('http_stream', None).get('url', None)
            stream_url = 'https://' + host + nt
            if jsdata.get('scheme', None) == 'HTTP_DASH':
                if jsdata.get('drm_type', None) == 'DRM_WIDEVINE':
                    licURL = jsdata.get('license_server', None)
                    hea_lic = {
                        'User-Agent': helper.UA,
                        'origin': 'https://sweet.tv',
                        'referer': 'https://sweet.tv/'
                    }
                    lic_url = '%s|%s|R{SSM}|' % (licURL, urlencode(hea_lic))
                    DRM = 'com.widevine.alpha'
                else:
                    lic_url = None
                    DRM = None
                PROTOCOL = 'mpd'
                subs = None

            elif jsdata.get('scheme', None) == 'HTTP_HLS':
                lic_url = None
                mpdurl = ''
                DRM = None
                PROTOCOL = 'hls'
                subs = None

            if helper.get_setting('playerType') == 'ffmpeg' and DRM is None:
                helper.ffmpeg_player(stream_url)
            else:
                helper.PlayVid(stream_url, lic_url, PROTOCOL, DRM, flags=False, subs=subs, vod=vod)


@plugin.route('/listM3U')
def listM3U():
    if helper.get_setting('logged'):
        file_name = helper.get_setting('name_m3u')
        path_m3u = helper.get_setting('path_m3u')
        if file_name == '' or path_m3u == '':
            xbmcgui.Dialog().notification('Sweet.tv', 'Specify the file name and destination directory.',
                                          xbmcgui.NOTIFICATION_ERROR)
            return
        xbmcgui.Dialog().notification('Sweet tv', 'Generating M3U list.', xbmcgui.NOTIFICATION_INFO)
        channels = channelList()
        if channels.get("status", None) == 'OK':
            xbmcgui.Dialog().notification('Sweet.tv', 'M3U list generated.', xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().notification('Sweet.tv', 'Log in to the plugin.', xbmcgui.NOTIFICATION_INFO)


class SweetTV(Helper):
    def __init__(self):
        super(SweetTV, self).__init__()
        plugin.run()
