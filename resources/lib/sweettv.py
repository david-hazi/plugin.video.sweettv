# coding: UTF-8
import sys
import xbmcgui, xbmcplugin, xbmcvfs
import xbmc
import time
import requests
import routing
import xml.etree.ElementTree as ET
from datetime import datetime
import threading
import urllib3
urllib3.disable_warnings()

from .helper import Helper

base_url = sys.argv[0]
try:
    handle = int(sys.argv[1])
except:
    handle = None  # or whatever you want to do
helper = Helper(base_url, handle)
plugin = routing.Plugin()

try:
    # Python 3
    from urllib.parse import quote_plus, unquote_plus, quote, unquote,parse_qsl,urlencode
    to_unicode = str
except:
    # Python 2.7
    from urllib import quote_plus, unquote_plus, quote, unquote,urlencode
    from urlparse import parse_qsl
    to_unicode = unicode

def getTime(x,y):
    if y=='date':
        data='%Y-%m-%d'
    elif y=='hour':
        data='%H:%M'
    return datetime.fromtimestamp(x).strftime(data)
    
def channelList():
    timestamp = int(time.time())
    json_data = {
    'epg_limit_prev': 1,
    'epg_limit_next': 100,
    'epg_current_time': timestamp,
    'need_epg': True,
    'need_list': True,
    'need_categories': False,
    'need_offsets': False,
    'need_hash': False,
    'need_icons': False,
    'need_big_icons': False,}

    url = helper.base_api_url.format('TvService/GetChannels.json')
    jsdata = helper.request_sess(url, 'post', headers=helper.headers, data = json_data, json=True, json_data = True)

    if "list" in jsdata:
        xml_root = ET.Element("tv")
        for json_channel in jsdata.get("list"):
            channel = ET.SubElement(xml_root, "channel", attrib={"id":json_channel.get("name")})
            ET.SubElement(channel, "display-name", lang="hu").text = json_channel.get("name")
            ET.SubElement(channel, "icon", src=json_channel.get("icon_url"))
            if "epg" in json_channel:
                for json_epg in json_channel.get("epg"):
                    programme = ET.SubElement(xml_root, "programme", attrib={"start": time.strftime('%Y%m%d%H%M%S', time.gmtime(json_epg.get("time_start"))) + " +0100", "stop": time.strftime('%Y%m%d%H%M%S', time.gmtime(json_epg.get("time_stop"))) + " +0100", "channel": json_channel.get("name")})
                    ET.SubElement(programme, "title", lang="hu").text = json_epg.get("text")

        tree = ET.ElementTree(xml_root)
        ET.indent(tree, space="  ", level=0)
        xmlstr = ET.tostring(xml_root, encoding='utf8')
        path_m3u = helper.get_setting('path_m3u')
        file_name = helper.get_setting('name_epg')
        if path_m3u != '' and file_name != '':
            f = xbmcvfs.File(path_m3u + file_name, 'w')
            f.write(xmlstr)
            f.close()
    
    return jsdata
    
    
@plugin.route('/')
def root():
    CreateDatas()
    
    refresh_token = helper.get_setting('refresh_token')
    
    xbmc.log("refresh " + refresh_token, xbmc.LOGDEBUG)
    xbmc.log("logged " + str(helper.get_setting('logged')), xbmc.LOGDEBUG)
	
    if refresh_token == 'None':
        helper.set_setting('bearer', '')    
        helper.set_setting('logged', 'false')
    
    if helper.get_setting('logged'):
        startwt()
    else:
        helper.add_item('[COLOR lightgreen][B]Login[/COLOR][/B]', plugin.url_for(login),folder=False)
        helper.add_item('[B]Settings[/B]', plugin.url_for(settings),folder=False)

    helper.eod()

def CreateDatas():
    if not helper.uuid:
        import uuid
        uuidx = uuid.uuid4()
        helper.set_setting('uuid',to_unicode(uuidx))
    return
    
@plugin.route('/startwt')    
def startwt():
    helper.add_item('[B]TV[/B]', plugin.url_for(mainpage,id='live'),folder=True)
    helper.add_item('[B]Replay[/B]', plugin.url_for(mainpage,id='replay'),folder=True)
    helper.add_item('[B]Logout[/B]', plugin.url_for(logout),folder=False)

def refreshToken(service=False):
    json_data = helper.json_data
    json_data.update({"refresh_token": helper.get_setting('refresh_token')})

    jsdata = helper.request_sess(helper.token_url, 'post', headers=helper.headers, data = json_data, json=True, json_data = True)
    xbmc.log("refresh " + str(jsdata), xbmc.LOGDEBUG)

    if service:
        timer = threading.Timer(30 * 60, refreshToken)
        timer.start()

    if jsdata.get("result", None) == 'COMPLETED' or jsdata.get("result", None) == 'OK':
        xbmc.log("success", xbmc.LOGDEBUG)
        access_token = jsdata.get("access_token")
        helper.set_setting('bearer', 'Bearer ' + to_unicode(access_token))

        channelList()
        return True
    else:
        return False

@plugin.route('/getEPG/<id>')
def getEPG(id):
    id,dur=id.split('|')
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
    jsdata = helper.request_sess(url, 'post', headers=helper.headers, data = json_data, json=True, json_data = True)

    if jsdata.get("code", None) == 16:
        helper.set_setting('bearer', '')
        refr = refreshToken()
        if refr:
            mainpage(id)
        else:
            return
    if jsdata.get("status", None) == 'OK':
        progs=jsdata['list'][0]['epg']
        for p in progs:
            now=int(time.time())
            tStart=p.get('time_start',None)
            if p['available']==True and tStart>=now-int(dur)*24*60*60 and tStart<=now:
                pid=str(p.get('id',None))
                tit=p.get('text',None)
                date=getTime(p.get('time_start',None),'date')
                ts=getTime(p.get('time_start',None),'hour')
                te=getTime(p.get('time_stop',None),'hour')
                title='[COLOR=gold]%s[/COLOR] | [B]%s-%s[/B] %s'%(date,ts,te,tit)
                ID=id+'|'+pid
                
                mod = plugin.url_for(playvid, id=ID)
                fold = False
                ispla = True
                imag = p.get('preview_url',None)
                art = {'icon': imag, 'fanart': helper.addon.getAddonInfo('fanart')}
                                              
                info = {'title': title, 'plot':''}
                
                helper.add_item(title, mod, playable=ispla, info=info, art=art, folder=fold, content='videos')    

    helper.eod()
            

@plugin.route('/mainpage/<id>')    
def mainpage(id):
    jsdata=channelList()

    if jsdata.get("code", None) == 16:
        helper.set_setting('bearer', '')
        refr = refreshToken()
        if refr:
            mainpage(id)
        else:
            return
    
    if jsdata.get("status", None) == 'OK':
        for j in jsdata.get('list', []):
            catchup = j.get('catchup',None)
            available = j.get('available',None)
            isShow=False
            if (id=='replay' and catchup and available) or (id=='live' and available):
                isShow=True
            if isShow:
                _id = str(j.get('id',None))
                title = j.get('name',None)
                slug = j.get('slug',None)
                epgs = j.get('epg',None)
                epg =''
                if id=='live' and epgs:
                    for e in epgs:
                        if e.get('time_stop',None)>int(time.time()):
                            tit=e.get('text',None)
                            ts=getTime(e.get('time_start',None),'hour')
                            te=getTime(e.get('time_stop',None),'hour')
                            epg+='[B]%s-%s[/B] %s\n'%(ts,te,tit)

                if id=='live':
                    idx = _id+'|null'#+slug
                    mod = plugin.url_for(playvid, id=idx)
                    fold = False
                    ispla = True
                else: # id=='replay'
                    dur=str(j.get('catchup_duration',None))
                    idx = _id+'|'+dur
                    mod = plugin.url_for(getEPG, id=idx)
                    fold = True
                    ispla = False
                
                imag = j.get('icon_v2_url',None)
                art = {'icon': imag, 'fanart': helper.addon.getAddonInfo('fanart')}
                     
                info = {'title': title, 'plot':epg}
                
                helper.add_item('[COLOR gold][B]'+title+'[/COLOR][/B]', mod, playable=ispla, info=info, art=art, folder=fold)    

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
    log_out = helper.dialog_choice('Logout','Do you want to log out?',agree='Yes', disagree='No')
    if log_out:
        helper.set_setting('bearer', '')    
        helper.set_setting('logged', 'false')
        helper.refresh()
        
@plugin.route('/login')
def login():
    jsdata = helper.request_sess(helper.auth_url, 'post', headers=helper.headers, data = helper.json_data, json=True, json_data = True)
    auth_code = jsdata.get("auth_code")
    if jsdata.get("result") != 'OK' or not auth_code:
        helper.notification('Information', 'Login error')
        helper.set_setting('logged', 'false')
        return
    dialog = xbmcgui.Dialog()
    # show loading dialog
    pDialog = xbmcgui.DialogProgress()
    pDialog.create('Sweet.tv', f"Enter code: {auth_code}")
    # wait for user to enter code
    jsdata = {"auth_code": auth_code}
    from json import dumps
    json_data = dumps(jsdata, separators=(',', ':'))
    result = None
    headers = {
        **helper.headers,
        'Content-Type': 'application/json',
    }
    while not result:
        if pDialog.iscanceled():
            helper.notification('Information', 'Login interrupted')
            helper.set_setting('logged', 'false')
            return
        jsdata = helper.request_sess(helper.check_auth_url, 'post', headers=headers, data = json_data, json=True, json_data = False)
        sys.stderr.write(str(jsdata))
        if jsdata.get("result") == "COMPLETED":
            result = jsdata
        else:
            time.sleep(3)

    if result.get("result") == 'COMPLETED':

        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        helper.set_setting('bearer', 'Bearer '+to_unicode(access_token))
        helper.set_setting('refresh_token', to_unicode(refresh_token))
        helper.set_setting('logged', 'true')

    else:

        info=jsdata.get('result', None)
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
        idx,pid = id.split('|')
        json_data = {
            'without_auth': True,
            'channel_id': int(idx),
            #'accept_scheme': ['HTTP_HLS',],
            'multistream': True,
        }
        vod=False
        if pid!='null':
            json_data.update({'epg_id':int(pid)})
            vod=True
                
        url = helper.base_api_url.format('TvService/OpenStream.json')
        jsdata = helper.request_sess(url, 'post', headers=helper.headers, data = json_data, json=True, json_data = True)

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
            stream_url = 'https://'+host+nt
            if jsdata.get('scheme', None)=='HTTP_DASH':
                if jsdata.get('drm_type', None)=='DRM_WIDEVINE':
                    licURL=jsdata.get('license_server', None)
                    hea_lic={
                        'User-Agent':helper.UA,
                        'origin': 'https://sweet.tv',
                        'referer': 'https://sweet.tv/'
                    }
                    lic_url='%s|%s|R{SSM}|'%(licURL,urlencode(hea_lic))
                    DRM='com.widevine.alpha'
                else:
                    lic_url = None
                    DRM = None
                PROTOCOL='mpd'                
                subs =None
            
            elif jsdata.get('scheme', None)=='HTTP_HLS':
                lic_url = None
                mpdurl =''
                DRM = None
                PROTOCOL = 'hls'
                subs =None
            
            if helper.get_setting('playerType')=='ffmpeg' and DRM is None:
                helper.ffmpeg_player(stream_url)
            else:
                helper.PlayVid(stream_url, lic_url, PROTOCOL, DRM, flags=False, subs = subs,vod=vod)

@plugin.route('/listM3U')
def listM3U():
    if helper.get_setting('logged'):
        file_name = helper.get_setting('name_m3u')
        path_m3u = helper.get_setting('path_m3u')
        if file_name == '' or path_m3u == '':
            xbmcgui.Dialog().notification('Sweet.tv', 'Specify the file name and destination directory.', xbmcgui.NOTIFICATION_ERROR)
            return
        xbmcgui.Dialog().notification('Sweet tv', 'Generating M3U list.', xbmcgui.NOTIFICATION_INFO)
        data = '#EXTM3U\n'
        channels=channelList()
        if channels.get("code", None) == 16:
            helper.set_setting('bearer', '')
            refr = refreshToken()
            if refr:
                channels=channelList()
            else:
                return
        if 'list' in channels:
            for c in channels['list']:
                if c.get('available',None):
                    img=c.get('icon_v2_url',None)
                    cName=c.get('name',None)
                    cid=c.get('id',None)
                    data += '#EXTINF:0 tvg-id="%s" tvg-logo="%s" group-title="Sweet.tv" ,%s\nplugin://plugin.video.sweettv/playvid/%s|null\n' %(cName,img,cName,cid)
            
            f = xbmcvfs.File(path_m3u + file_name, 'w')
            f.write(data)
            f.close()
            xbmcgui.Dialog().notification('Sweet.tv', 'M3U list generated.', xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().notification('Sweet.tv', 'Log in to the plugin.', xbmcgui.NOTIFICATION_INFO)

class SweetTV(Helper):
    def __init__(self):
        super().__init__()
        plugin.run()