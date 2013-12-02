from standardweb.models import *


def _build_kill_leaderboard(server, type):
    kill_type = KillType.objects.get(type=type)
    kills = KillCount.objects.filter(server=server, kill_type=kill_type) \
                .select_related('killer')
    if kills:
        return sorted([(x.count, x.killer) for x in kills], key=lambda x: (-x[0], x[1].displayname.lower()))[:10]

    return None


def _build_block_discovery_leaderboard(server, type):
    material_type = MaterialType.objects.get(type=type)
    discoveries = OreDiscoveryCount.objects.filter(server=server, material_type=material_type) \
                        .select_related('player')

    if discoveries:
        return sorted([(x.count, x.player) for x in discoveries], key=lambda x: (-x[0], x[1].displayname.lower()))[:10]

    return None


def _get_leaderboard_report(server, type, element, title, section, subtitle):
    func = {
        'kills': _build_kill_leaderboard,
        'ores': _build_block_discovery_leaderboard
    }[type]

    leaderboard_list = func(server, element)

    if leaderboard_list:
        leaderboard_data = {
            'title': title,
            'list': leaderboard_list
        }

        if subtitle:
            leaderboard_data['subtitle'] = subtitle

        section.append(leaderboard_data)


def get_kill_leaderboards(server, element, title, section, subtitle=None):
    _get_leaderboard_report(server, 'kills', element, title, section, subtitle)


def get_ore_leaderboards(server, element, title, section, subtitle=None):
    _get_leaderboard_report(server, 'ores', element, title, section, subtitle)
