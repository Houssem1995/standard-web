"""
Script that should run every minute. Collects and stores stats from all servers to the db.
"""
import json
import os
import time
import urllib2
os.environ['DJANGO_SETTINGS_MODULE'] = 'standardweb.settings'

import rollbar

from django.conf import settings
from django.db import transaction

from standardweb.models import *
from standardweb.lib import api
from standardweb.lib.constants import *

from datetime import datetime, timedelta

def _query_server(server, mojang_status):
    try:
        server_status = api.get_server_status(server)
    except:
        server_status = {}
    
    player_stats = []
    
    online_player_ids = []
    for player_info in server_status.get('players', []):
        try:
            player = MinecraftPlayer.objects.get(username=player_info.get('username'))
        except:
            player = MinecraftPlayer(username=player_info.get('username'))
            player.save()
        
        online_player_ids.append(player.id)
        
        try:
            last_activity = PlayerActivity.objects.filter(server=server, player=player).latest('timestamp')
        except:
            last_activity = None
        
        # if the last activity for this player is an 'exit' activity (or there isn't an activity),
        # create a new 'enter' activity since they just joined this minute
        if not last_activity or last_activity.activity_type == PLAYER_ACTIVITY_TYPES['exit']:
            enter = PlayerActivity(server=server, player=player,
                                   activity_type=PLAYER_ACTIVITY_TYPES['enter'])
            enter.save()
        
        # respect nicknames from the main server
        if server.id == settings.MAIN_SERVER_ID:
            nickname_ansi = player_info.get('nickname_ansi')
            nickname = player_info.get('nickname')
            
            player.nickname_ansi = nickname_ansi
            player.nickname = nickname
            player.save()
        
        ip = player_info.get('address')
        
        if ip:
            try:
                IPTracking.objects.get(ip=ip, player=player)
            except:
                existing_player_ip = IPTracking(ip=ip, player=player)
                existing_player_ip.save()
        
        try:
            stats = PlayerStats.objects.get(server=server, player=player)
            stats.last_seen = datetime.utcnow()
        except:
            stats = PlayerStats(server=server, player=player)
        
        stats.pvp_logs = player_info.get('pvp_logs')
        stats.time_spent += 1
        stats.save()
        
        player_stats.append({
            'username': player.username,
            'minutes': stats.time_spent,
            'rank': stats.get_rank()
        })
    
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    query = PlayerStats.objects.filter(server=server, last_seen__gt=five_minutes_ago)
    recent_player_ids = [x[0] for x in query.values_list('player_id')]
    
    # find all players that have recently left and insert an 'exit' activity for them
    # if their last activity was an 'enter'
    for player_id in set(recent_player_ids) - set(online_player_ids):
        try:
            latest_activity = PlayerActivity.objects.filter(server=server, player=player_id).latest('timestamp')
        except:
            latest_activity = None
        
        if latest_activity and latest_activity.activity_type == PLAYER_ACTIVITY_TYPES['enter']:
            ex = PlayerActivity(server=server, player_id=player_id,
                                activity_type=PLAYER_ACTIVITY_TYPES['exit'])
            ex.save()
    
    banned_players = server_status.get('banned_players', [])
    PlayerStats.objects.filter(server=server, player__username__in=banned_players).update(banned=True)
    PlayerStats.objects.filter(server=server).exclude(player__username__in=banned_players).update(banned=False)
    
    player_count = server_status.get('numplayers', 0) or 0
    cpu_load = server_status.get('load', 0) or 0
    tps = server_status.get('tps', 0) or 0
    
    status = ServerStatus(server=server, player_count=player_count, cpu_load=cpu_load, tps=tps)
    status.save()

    api.send_stats(server, {
        'player_stats': player_stats,
        'login': mojang_status.login,
        'session': mojang_status.session,
        'account': mojang_status.account,
        'auth': mojang_status.auth
    })


def _get_mojang_status():
    try:
        response = urllib2.urlopen('http://status.mojang.com/check')
        result = json.loads(response.read())

        website = result[0].get('minecraft.net') == 'green'
        login = result[1].get('login.minecraft.net') == 'green'
        session = result[2].get('session.minecraft.net') == 'green'
        account = result[3].get('account.mojang.com') == 'green'
        auth = result[4].get('auth.mojang.com') == 'green'
        skins = result[5].get('skins.minecraft.net') == 'green'
    except:
        website = False
        login = False
        session = False
        account = False
        auth = False
        skins = False

    mojang_status = MojangStatus(website=website,
                                 login=login,
                                 session=session,
                                 account=account,
                                 auth=auth,
                                 skins=skins)
    mojang_status.save()

    return mojang_status


def main():
    mojang_status = _get_mojang_status()

    durations = []

    for server in Server.objects.filter(online=True):
        with transaction.commit_manually():
            start = int(round(time.time() * 1000))

            try:
                _query_server(server, mojang_status)
            except:
                transaction.rollback()
                rollbar.report_exc_info()
            else:
                transaction.commit()
                durations.append((server.id, int(round(time.time() * 1000)) - start))

    extra_data = {'server.%d.ms' % server_id: duration for server_id, duration in durations}
    extra_data['login'] = mojang_status.login
    extra_data['session'] = mojang_status.session
    rollbar.report_message('Server queries complete', 'debug',
                           extra_data=extra_data)


if __name__ == '__main__':
    rollbar.init(settings.ROLLBAR['access_token'], settings.ROLLBAR['environment'])
    
    try:
        main()
    except:
        rollbar.report_exc_info()
