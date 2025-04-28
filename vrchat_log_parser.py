import re
import os
from collections import OrderedDict

def extract_players_with_ids(log_path):
    current_world_name = None
    current_players = OrderedDict()
    active_world_id = None
    active_world_instance = None
    player_state = OrderedDict()

    with open(log_path, encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        # ワールドIDをアンカーとして抽出・リセット
        if "Unpacking World (wrld_" in line:
            match = re.search(r'Unpacking World \((wrld_[\w-]+)\)', line)
            if match:
                active_world_id = match.group(1)
                current_world_name = None
                active_world_instance = None
                current_players.clear()

        # ワールド名として「Entering Room: ◯◯」を使用
        elif "Entering Room:" in line:
            match = re.search(r'Entering Room: (.+)', line)
            if match:
                current_world_name = match.group(1).strip()

        # 正確なワールドインスタンス情報（URLに使う）
        elif "Joining wrld_" in line:
            match = re.search(r'Joining (wrld_[\w-]+:[^ \n]+)', line)
            if match:
                active_world_instance = match.group(1)

        # プレイヤー参加記録
        elif "OnPlayerJoined" in line or "OnPlayerJoinComplete" in line:
            match = re.search(r'(OnPlayerJoined|OnPlayerJoinComplete) (.+ \(usr_[\w-]+\))', line)
            if match:
                player_entry = match.group(2).strip()
                current_players[player_entry] = True

        # プレイヤー退出記録
        elif "OnPlayerLeft" in line:
            match = re.search(r'OnPlayerLeft (.+ \(usr_[\w-]+\))', line)
            if match:
                player_entry = match.group(1).strip()
                current_players.pop(player_entry, None)

        # スクリーンショットをトリガーにしてプレイヤーとワールド情報を記録
        elif "[VRC Camera] Took screenshot to:" in line:
            match = re.search(r'screenshot to: (.+VRChat_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}[^\\/]*\.png)', line)
            if match:
                path = match.group(1).strip()
                base = os.path.basename(path)

                player_list = []
                for p in current_players.keys():
                    try:
                        name, uid = p.split(" (usr_")
                        uid = uid.rstrip(")")
                        player_list.append({
                            "name": name,
                            "id": uid,
                            "url": f"https://vrchat.com/home/user/usr_{uid}"
                        })
                    except:
                        continue

                player_state[base] = {
                    "world_instance": active_world_instance,
                    "world_name": current_world_name,
                    "world_url": f"https://vrchat.com/home/world/{active_world_id}" if active_world_id else None,
                    "players": player_list
                }

    return player_state


def extract_players_for_photo(log_path, photo_filename):
    states = extract_players_with_ids(log_path)
    for k in states:
        if k.startswith(photo_filename):
            return states[k]
    return None
