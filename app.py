# -*- coding: utf-8 -*-
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
import json
import os
import random

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE / "data")))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(BASE / "uploads")))
STATE_FILE = DATA_DIR / "state.json"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
LOCK = RLock()
app = Flask(__name__)
# Flask 1.x（SCF Python 3.6）路由兼容；新版本 Flask 同样适用。
app.get = lambda rule: app.route(rule, methods=["GET"])
app.post = lambda rule: app.route(rule, methods=["POST"])
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
SCHEMA_VERSION = 2


@app.after_request
def inline_response(response):
    # SCF 默认 attachment 会让浏览器下载 HTML，统一改为内联展示。
    response.headers["Content-Disposition"] = "inline"
    return response


def now_text():
    return datetime.now().strftime("%m-%d %H:%M")


def stage_dates(stage):
    try:
        start = datetime.strptime(stage["start_date"], "%Y-%m-%d")
        end = datetime.strptime(stage["end_date"], "%Y-%m-%d")
        days = []
        while start <= end and len(days) < 14:
            days.append(start.strftime("%m-%d"))
            start += timedelta(days=1)
        return days
    except (ValueError, TypeError):
        return ["12-15"]


def make_stage(stage_id="sea", name="海选赛", start="2025-12-15", end="2025-12-19"):
    return {
        "id": stage_id, "name": name, "start_date": start, "end_date": end,
        "current_date": "12-15", "next_date": "12-16", "sessions": ["15:00", "19:00"],
        "daily_matches": 3, "daily_overrides": {"12-17": 4}, "min_valid_days": 2,
        "best_days": 3, "min_score": 30, "advance_quota": 108, "group_size": 6,
        "points": [10, 7, 5, 3, 2, 0], "require_idcard": True,
        "ranking_published": False, "advancement_published": False, "rules_version": 1,
        "official_uids": [], "supplemental_uids": [], "tie_excluded_uids": [],
        "require_signup": True, "stage_registration_fields": [], "custom_fields": [],
    }


def make_users():
    raw = [
        ("34943984", "张小花", "花花棋手", [35], "领队-小宝"),
        ("36367359", "北风", "北风过境", [40, 22], "领队-小宝"),
        ("34306970", "白开水", "白开水不甜", [28], "领队-小宝"),
        ("15174217", "七宝", "七宝下棋", [30, 18], "领队-星禾"),
        ("8375262", "甜酒", "甜酒微醺", [20], "领队-星禾"),
        ("51220871", "阿灿", "阿灿来啦", [12], "领队-星禾"),
        ("23838727", "夜阑", "夜阑听风", [45, 20], "领队-大王"),
        ("26493608", "青竹", "青竹一梦", [38, 19], "领队-大王"),
        ("25260694", "星禾", "星禾棋手", [33], "领队-大王"),
        ("14640769", "临温", "临温落子", [26, 17], "领队-大王"),
        ("37014032", "小宝", "小宝必胜", [15], "领队-大王"),
        ("4691014", "旺财", "旺财棋神", [8], "领队-大王"),
    ]
    return [{
        "uid": uid, "nickname": nickname, "game_nick": game_nick, "registered": True,
        "wechat": f"wx_{uid[-4:]}", "qq": "", "contact_type": "微信", "contact_value": f"wx_{uid[-4:]}", "phone": f"138****{uid[-4:]}", "game_id": f"WX{uid[-6:]}",
        "channel": "微信", "wechat_qr": "", "game_shot": "", "history_by_stage": {"sea": history},
        "next_session": "15:00", "leader": leader,
        "leader_uid": {"领队-小宝": "88001001", "领队-星禾": "88001002", "领队-大王": "88001003"}.get(leader, ""), "custom_values": {},
        "stage_signups": [], "stage_signup_values": {},
    } for uid, nickname, game_nick, history, leader in raw]


def make_match(stage_id, group, round_no, users, points, status="not_uploaded"):
    results = []
    for index, uid in enumerate(group["members"]):
        rank = (index + round_no - 1) % len(group["members"]) + 1
        user = next(u for u in users if u["uid"] == uid)
        results.append({"uid": uid, "nickname": user["game_nick"], "rank": rank, "points": points[rank - 1], "match_state": "matched"})
    return {
        "id": f"{stage_id}_g{group['id']}_m{round_no}", "stage_id": stage_id,
        "round": round_no, "group_id": group["id"], "date": group["date"], "session": group["session"],
        "status": status, "image": "", "uploaded_at": now_text() if status != "not_uploaded" else "",
        "confirmed_at": now_text() if status == "confirmed" else "", "results": results, "revisions": [],
    }


def make_event(event_id=2, name="万象点点杯 S2", season="S2"):
    stage = make_stage()
    users = make_users()
    groups = [
        {"id": 1, "stage_id": "sea", "room": "4216", "members": [u["uid"] for u in users[:6]], "date": "12-15", "session": "15:00", "notified": True},
        {"id": 2, "stage_id": "sea", "room": "4217", "members": [u["uid"] for u in users[6:]], "date": "12-15", "session": "19:00", "notified": True},
    ]
    matches = []
    for group in groups:
        for round_no in range(1, 4):
            status = "confirmed" if round_no < 3 else "not_uploaded"
            matches.append(make_match("sea", group, round_no, users, stage["points"], status))
    return {
        "id": event_id, "name": name, "season": season, "game": "王者万象棋", "fee": "—", "status": "进行中",
        "banner_time": "12.08-12.27", "signup_time": "12.08 起", "description": "万象棋全民赛事",
        "registration_fields": ["contact", "phone", "game_nick", "game_id", "channel"], "custom_fields": [],
        "signup_start": "2025-12-08", "signup_end": "2025-12-14",
        "stages": [stage, make_stage("knockout", "淘汰赛", "2025-12-21", "2025-12-23"), make_stage("final", "总决赛", "2025-12-27", "2025-12-27")],
        "users": users, "groups": groups, "matches": matches,
        "messages": [
            {"id": 1, "batch_id": "batch_start", "uid": "34943984", "title": "开赛提醒", "content": "今天 15:00 场，房间号 4216。今日须完成全部 3 局，未打满当天成绩无效。", "time": "12-15 14:30", "read": False, "delivered": True},
            {"id": 2, "batch_id": "batch_group", "uid": "34943984", "title": "领队已为你创建小队群", "content": "领队-小宝已拉起万象棋小队群，可在点点聊天中查看。", "time": "12-15 12:10", "read": True, "delivered": True},
        ],
        "message_settings": {
            "signup": {"enabled": True, "title": "报名成功", "trigger": "提交报名后即时", "content": "你已报名{赛事名}，后续每日只需选择参赛场次。"},
            "start": {"enabled": True, "title": "开赛提醒", "trigger": "开赛前 30 分钟", "content": "你报名的{场次}将于{时间}开赛，房间号{房间号}。"},
            "score": {"enabled": True, "title": "当日积分结算", "trigger": "完成全部局次且审核后", "content": "今日全部{要求局数}局赛果已确认，当日{当日积分}分已生效。"},
            "advance": {"enabled": True, "title": "正式晋级公告", "trigger": "运营确认发布晋级名单后", "content": "恭喜你在{赛事名}{阶段}中正式晋级。"},
        },
        "logs": [{"time": "12-14 18:20", "operator": "张恬虞", "text": "发布海选赛规则，默认每日 3 局，至少 2 个有效参赛日"}],
    }


def seed_state():
    first = make_event()
    second = make_event(1, "星光之夜", "S1")
    second["status"] = "已结束"
    second["fee"] = "10"
    second["game"] = "狼人杀"
    second["banner_time"] = "09.01 起"
    second["signup_time"] = "09.01 起"
    third = make_event(3, "万象棋周末娱乐赛", "W12")
    third["status"] = "未开始"
    third["banner_time"] = "12.20-12.28"
    fourth = make_event(4, "王者峡谷战队赛", "K12")
    fourth["game"] = "王者荣耀"
    fifth = make_event(5, "和平精英周末赛", "P12")
    fifth["game"] = "和平精英"
    sixth = make_event(6, "三角洲行动挑战赛", "D12")
    sixth["game"] = "三角洲行动"
    leaders = [
        {"uid": "88001001", "name": "领队-小宝", "capacity": 8, "enabled": True},
        {"uid": "88001002", "name": "领队-星禾", "capacity": 8, "enabled": True},
        {"uid": "88001003", "name": "领队-大王", "capacity": 8, "enabled": True},
    ]
    return {"schema_version": SCHEMA_VERSION, "demo_date": "2025-12-15", "current_uid": "34943984", "current_event_id": 2, "current_stage_id": "sea", "events": [first, second, third, fourth, fifth, sixth], "leaders": leaders}


def load_state():
    with LOCK:
        if not STATE_FILE.exists():
            state = seed_state()
            save_state(state)
            return state
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if state.get("schema_version") != SCHEMA_VERSION:
            state = seed_state()
            save_state(state)
        return state


def save_state(state):
    with LOCK:
        temp = STATE_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(STATE_FILE)


def current_event(state):
    return next(event for event in state["events"] if event["id"] == state["current_event_id"])


def current_stage(state, event=None):
    event = event or current_event(state)
    return next(stage for stage in event["stages"] if stage["id"] == state["current_stage_id"])


def flat_state(state):
    event = current_event(state)
    stage = current_stage(state, event)
    required = stage["daily_overrides"].get(stage["current_date"], stage["daily_matches"])
    demo_date = state["demo_date"]
    account = next(user for user in event["users"] if user["uid"] == state["current_uid"])
    stage_signed = stage["id"] in account.get("stage_signups", [])
    signup_open = event["signup_start"] <= demo_date <= event["signup_end"]
    stage_active = stage["start_date"] <= demo_date <= stage["end_date"]
    if demo_date < stage["start_date"] and signup_open:
        c_view = "signup"
    elif stage_active and stage["require_signup"] and not stage_signed:
        c_view = "stage_signup"
    elif stage_active:
        c_view = "stage"
    elif demo_date < stage["start_date"]:
        c_view = "before_stage"
    else:
        c_view = "ended"
    runtime = {
        "id": event["id"], "name": event["name"], "season": event["season"], "game": event["game"],
        "status": event["status"], "banner_time": event["banner_time"], "signup_time": event["signup_time"],
        "registration_fields": event["registration_fields"], "stage": stage["name"],
        "stage_id": stage["id"], "date_range": f"{stage['start_date']} 至 {stage['end_date']}",
        "current_date": stage["current_date"], "next_date": stage["next_date"], "sessions": stage["sessions"],
        "daily_matches": required, "default_matches": stage["daily_matches"], "daily_overrides": stage["daily_overrides"],
        "min_valid_days": stage["min_valid_days"], "best_days": stage["best_days"], "min_score": stage["min_score"],
        "advance_quota": stage["advance_quota"], "group_size": stage["group_size"], "points": stage["points"],
        "require_idcard": stage["require_idcard"], "ranking_published": stage["ranking_published"],
        "advancement_published": stage["advancement_published"], "rules_version": stage["rules_version"],
        "days": stage_dates(stage), "start_date": stage["start_date"], "end_date": stage["end_date"],
        "message_settings": event["message_settings"], "custom_fields": event["custom_fields"],
        "require_signup": stage["require_signup"], "stage_registration_fields": stage["stage_registration_fields"],
        "stage_custom_fields": stage["custom_fields"], "demo_date": demo_date,
        "signup_start": event["signup_start"], "signup_end": event["signup_end"],
        "signup_open": signup_open, "stage_active": stage_active, "c_view": c_view,
    }
    groups = [g for g in event["groups"] if g["stage_id"] == stage["id"]]
    current_group = next((g for g in groups if state["current_uid"] in g["members"]), groups[0] if groups else {"id": 0, "room": "待录入", "members": [], "date": stage["current_date"], "session": stage["sessions"][0]})
    return {
        "current_uid": state["current_uid"], "current_event_id": event["id"], "current_stage_id": stage["id"],
        "event": runtime, "users": event["users"], "groups": groups, "group": current_group,
        "matches": [m for m in event["matches"] if m["stage_id"] == stage["id"]],
        "messages": event["messages"], "logs": event["logs"], "stage_signed": stage_signed,
    }


def current_user(flat):
    return next(user for user in flat["users"] if user["uid"] == flat["current_uid"])


def match_for_user(flat, uid):
    group = next((g for g in flat["groups"] if uid in g["members"]), None)
    if not group:
        return []
    return sorted([m for m in flat["matches"] if m["group_id"] == group["id"]], key=lambda m: m["round"])


def user_stats(flat, user):
    event = flat["event"]
    matches = match_for_user(flat, user["uid"])
    active = [m for m in matches if m["status"] in ("pending", "confirmed")]
    confirmed = [m for m in matches if m["status"] == "confirmed"]
    played = min(len(active), event["daily_matches"])
    confirmed_count = min(len(confirmed), event["daily_matches"])
    day_valid = played >= event["daily_matches"] and confirmed_count >= event["daily_matches"]
    day_score = 0
    if day_valid:
        for match in confirmed[:event["daily_matches"]]:
            result = next((r for r in match["results"] if r["uid"] == user["uid"]), None)
            if result:
                day_score += result["points"]
    history = user.get("history_by_stage", {}).get(flat["current_stage_id"], [])
    scores = list(history) + ([day_score] if day_valid else [])
    counted = sorted(scores, reverse=True)[:event["best_days"]]
    total = sum(counted)
    valid_days = len(scores)
    return {
        "played": played, "confirmed": confirmed_count, "day_valid": day_valid, "day_score": day_score,
        "valid_days": valid_days, "counted_days": len(counted), "total_score": total,
        "eligible": valid_days >= event["min_valid_days"] and total >= event["min_score"],
    }


def event_summary(event):
    return {
        "id": event["id"], "name": event["name"], "season": event["season"], "fee": event["fee"], "game": event["game"],
        "status": event["status"], "banner_time": event["banner_time"], "signup_time": event["signup_time"],
        "stage_count": len(event["stages"]), "player_count": len(event["users"]),
        "user_uids": [user["uid"] for user in event["users"]],
        "date_range": f"{min(s['start_date'] for s in event['stages'])} 至 {max(s['end_date'] for s in event['stages'])}",
    }


def public_state(state):
    flat = flat_state(state)
    stage = current_stage(state)
    data = deepcopy(flat)
    stats = {}
    for user in flat["users"]:
        stats[user["uid"]] = user_stats(flat, user)
    ranking = sorted(flat["users"], key=lambda u: (-stats[u["uid"]]["total_score"], u["uid"]))
    for index, user in enumerate(ranking, 1):
        uid = user["uid"]
        stats[uid]["rank"] = index
        stats[uid]["expected_advance"] = (stats[uid]["eligible"] and index <= flat["event"]["advance_quota"] and uid not in stage["tie_excluded_uids"]) or uid in stage["supplemental_uids"]
        stats[uid]["supplemental"] = uid in stage["supplemental_uids"]
    for user in data["users"]:
        user["advance_official"] = user["uid"] in stage["official_uids"]
    data["stats"] = stats
    data["ranking"] = [user["uid"] for user in ranking]
    data["current_user"] = current_user(data)
    data["unread"] = sum(1 for m in data["messages"] if m["uid"] == data["current_uid"] and not m["read"])
    data["event_options"] = [event_summary(event) for event in state["events"]]
    data["stage_options"] = [{"id": s["id"], "name": s["name"], "start_date": s["start_date"], "end_date": s["end_date"]} for s in current_event(state)["stages"]]
    data["tie_pending"] = []
    quota = flat["event"]["advance_quota"]
    eligible_uids = [user["uid"] for user in ranking if stats[user["uid"]]["eligible"]]
    if len(eligible_uids) > quota:
        boundary_score = stats[eligible_uids[quota - 1]]["total_score"]
        tied = [uid for uid in eligible_uids if stats[uid]["total_score"] == boundary_score]
        if len(tied) > 1 and not any(uid in stage["supplemental_uids"] for uid in tied):
            data["tie_pending"] = tied
    batches = {}
    for message in data["messages"]:
        batch_id = message.get("batch_id", f"auto_{message['id']}")
        batch = batches.setdefault(batch_id, {"id": batch_id, "title": message["title"], "content": message["content"], "time": message["time"], "total": 0, "delivered": 0, "read_count": 0, "unread_uids": []})
        batch["total"] += 1
        batch["delivered"] += 1 if message.get("delivered", True) else 0
        if message["read"]:
            batch["read_count"] += 1
        else:
            batch["unread_uids"].append(message["uid"])
    data["message_batches"] = list(batches.values())
    data["leader_options"] = []
    for leader in state["leaders"]:
        item = deepcopy(leader)
        item["assigned_count"] = sum(1 for user in flat["users"] if user.get("leader_uid") == leader["uid"])
        item["available"] = leader["enabled"] and item["assigned_count"] < leader["capacity"]
        data["leader_options"].append(item)
    return data


def add_message(flat, uid, title, content, batch_id=None):
    message_id = max([m["id"] for m in flat["messages"]] + [0]) + 1
    flat["messages"].insert(0, {"id": message_id, "batch_id": batch_id or f"auto_{message_id}", "uid": uid, "title": title, "content": content, "time": now_text(), "read": False, "delivered": True})


def add_log(flat, text):
    flat["logs"].insert(0, {"time": now_text(), "operator": "本地运营", "text": text})


def ensure_match_counts(state, event, stage):
    count = stage["daily_overrides"].get(stage["current_date"], stage["daily_matches"])
    for group in [g for g in event["groups"] if g["stage_id"] == stage["id"]]:
        matches = [m for m in event["matches"] if m["stage_id"] == stage["id"] and m["group_id"] == group["id"]]
        for round_no in range(1, count + 1):
            if not any(m["round"] == round_no for m in matches):
                event["matches"].append(make_match(stage["id"], group, round_no, event["users"], stage["points"]))


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/c")
def c_page():
    return render_template("c.html")


@app.get("/c/chat")
def c_chat_page():
    return render_template("chat.html")


@app.get("/b")
def b_page():
    return render_template("b.html")


@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.get("/api/state")
def api_state():
    return jsonify(public_state(load_state()))


@app.post("/api/event/select")
def api_event_select():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        event = next(event for event in state["events"] if event["id"] == int(payload["event_id"]))
        state["current_event_id"] = event["id"]
        state["current_stage_id"] = event["stages"][0]["id"]
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/event/create")
def api_event_create():
    payload = request.get_json(force=True)
    name = str(payload.get("name", "新建万象棋赛事")).strip() or "新建万象棋赛事"
    season = str(payload.get("season", "S1")).strip() or "S1"
    with LOCK:
        state = load_state()
        new_id = max(event["id"] for event in state["events"]) + 1
        event = make_event(new_id, name, season)
        event["game"] = str(payload.get("game", "王者万象棋"))
        event["status"] = "未开始"
        banner_start = str(payload.get("banner_start", "2025-12-20T00:00")).replace("T", " ")
        banner_end = str(payload.get("banner_end", "2025-12-31T23:59")).replace("T", " ")
        signup_start = str(payload.get("signup_start", "2025-12-20T12:00")).replace("T", " ")
        signup_end = str(payload.get("signup_end", "2025-12-27T12:00")).replace("T", " ")
        event["banner_time"] = f"{banner_start} 至 {banner_end}"
        event["signup_time"] = f"{signup_start} 至 {signup_end}"
        event["signup_start"] = signup_start[:10]
        event["signup_end"] = signup_end[:10]
        event["logs"] = [{"time": now_text(), "operator": "本地运营", "text": "创建赛事及默认海选赛段（生成演示选手便于联调）"}]
        state["events"].append(event)
        state["current_event_id"] = new_id
        state["current_stage_id"] = "sea"
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/stage/select")
def api_stage_select():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        stage = next(stage for stage in current_event(state)["stages"] if stage["id"] == payload["stage_id"])
        state["current_stage_id"] = stage["id"]
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/stage/create")
def api_stage_create():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        event = current_event(state)
        source = current_stage(state, event)
        stage_id = f"stage_{max([int(s['id'].split('_')[-1]) if s['id'].startswith('stage_') else 0 for s in event['stages']] + [0]) + 1}"
        stage = deepcopy(source)
        stage.update({
            "id": stage_id, "name": str(payload.get("name", "自定义赛段")).strip() or "自定义赛段",
            "start_date": payload.get("start_date", source["end_date"]), "end_date": payload.get("end_date", source["end_date"]),
            "ranking_published": False, "advancement_published": False, "rules_version": 1,
            "official_uids": [], "supplemental_uids": [], "tie_excluded_uids": [], "daily_overrides": {},
        })
        event["stages"].append(stage)
        for old_group in [g for g in event["groups"] if g["stage_id"] == source["id"]]:
            group = deepcopy(old_group)
            group["stage_id"] = stage_id
            group["room"] = "待录入"
            event["groups"].append(group)
            for round_no in range(1, stage["daily_matches"] + 1):
                event["matches"].append(make_match(stage_id, group, round_no, event["users"], stage["points"]))
        state["current_stage_id"] = stage_id
        add_log(flat_state(state), f"新增赛段 {stage['name']}，规则复制自 {source['name']}")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/stage/delete")
def api_stage_delete():
    with LOCK:
        state = load_state()
        event = current_event(state)
        if len(event["stages"]) == 1:
            return jsonify({"error": "至少保留一个赛段"}), 400
        stage = current_stage(state, event)
        event["stages"] = [s for s in event["stages"] if s["id"] != stage["id"]]
        event["groups"] = [g for g in event["groups"] if g["stage_id"] != stage["id"]]
        event["matches"] = [m for m in event["matches"] if m["stage_id"] != stage["id"]]
        state["current_stage_id"] = event["stages"][0]["id"]
        add_log(flat_state(state), f"删除赛段 {stage['name']} 及其本地演示分组赛果")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/rules")
def api_rules():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        event = current_event(state)
        stage = current_stage(state, event)
        stage["name"] = str(payload.get("name", stage["name"])).strip() or stage["name"]
        stage["start_date"] = payload.get("start_date", stage["start_date"])
        stage["end_date"] = payload.get("end_date", stage["end_date"])
        if "sessions" in payload:
            sessions = [value.strip() for value in str(payload["sessions"]).replace("，", "/").replace(",", "/").split("/") if value.strip()]
            if sessions:
                stage["sessions"] = sessions
        if stage["start_date"] > stage["end_date"]:
            return jsonify({"error": "赛段开始日期不能晚于结束日期"}), 400
        for key in ["daily_matches", "min_valid_days", "best_days", "min_score", "advance_quota", "group_size"]:
            stage[key] = max(1, int(payload.get(key, stage[key])))
        duration = len(stage_dates(stage))
        if stage["min_valid_days"] > duration or stage["best_days"] > duration:
            return jsonify({"error": f"有效参赛天数和最好成绩天数不能超过赛段持续天数（当前 {duration} 天）"}), 400
        stage["require_signup"] = True if event["stages"][0]["id"] == stage["id"] else bool(payload.get("require_signup", stage["require_signup"]))
        if "stage_registration_fields" in payload:
            allowed = {"contact", "wechat", "qq", "phone", "game_nick", "game_id", "channel", "wechat_qr", "game_shot"}
            stage["stage_registration_fields"] = [key for key in payload["stage_registration_fields"] if key in allowed]
        if "points" in payload and len(payload["points"]) == 6:
            stage["points"] = [max(0, int(value)) for value in payload["points"]]
        if "registration_fields" in payload:
            allowed = {"contact", "wechat", "qq", "phone", "game_nick", "game_id", "channel", "wechat_qr", "game_shot"}
            event["registration_fields"] = [key for key in payload["registration_fields"] if key in allowed]
        stage["rules_version"] += 1
        ensure_match_counts(state, event, stage)
        add_log(flat_state(state), f"保存 {stage['name']} 赛段规则：{stage['start_date']} 至 {stage['end_date']}，每日 {stage['daily_matches']} 局")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/stage/day-override")
def api_day_override():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        event = current_event(state)
        stage = current_stage(state, event)
        date = payload["date"]
        stage["daily_overrides"][date] = max(1, int(payload["matches"]))
        stage["rules_version"] += 1
        ensure_match_counts(state, event, stage)
        add_log(flat_state(state), f"{stage['name']} {date} 单日局数调整为 {stage['daily_overrides'][date]}")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/stage/current-date")
def api_current_date():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        event = current_event(state)
        stage = current_stage(state, event)
        date = payload["date"]
        if date not in stage_dates(stage):
            return jsonify({"error": "日期不在当前赛段内"}), 400
        stage["current_date"] = date
        ensure_match_counts(state, event, stage)
        for group in [g for g in event["groups"] if g["stage_id"] == stage["id"]]:
            group["date"] = date
            for match in [m for m in event["matches"] if m["stage_id"] == stage["id"] and m["group_id"] == group["id"]]:
                match["date"] = date
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/signup")
def api_signup():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        if not flat["event"]["signup_open"]:
            return jsonify({"error": "当前不在赛事报名时间内"}), 400
        user = current_user(flat)
        for key in ["wechat", "phone", "game_nick", "game_id", "channel"]:
            user[key] = str(payload.get(key, user.get(key, ""))).strip()
        if "contact" in flat["event"]["registration_fields"]:
            contact_type = str(payload.get("contact_type", "微信"))
            contact_value = str(payload.get("contact_value", "")).strip()
            if contact_type not in ("微信", "QQ") or not contact_value:
                return jsonify({"error": "请选择微信或 QQ，并填写对应账号"}), 400
            user["contact_type"] = contact_type
            user["contact_value"] = contact_value
            if contact_type == "微信":
                user["wechat"] = contact_value
            else:
                user["qq"] = contact_value
        for field in flat["event"]["custom_fields"]:
            user["custom_values"][field["id"]] = str(payload.get(field["id"], "")).strip()
        user["registered"] = True
        add_message(flat, user["uid"], "报名成功", f"你已报名{flat['event']['name']}，后续每日只需选择参赛场次，无需重复提交资料。")
        add_log(flat, f"用户 {user['uid']} 提交报名资料")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/stage/signup")
def api_stage_signup():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        if not flat["event"]["stage_active"]:
            return jsonify({"error": "当前赛段不在进行时间内"}), 400
        user = current_user(flat)
        stage_id = flat["current_stage_id"]
        values = user["stage_signup_values"].setdefault(stage_id, {})
        for key in ["wechat", "phone", "game_nick", "game_id", "channel"]:
            if key in payload:
                values[key] = str(payload.get(key, "")).strip()
        contact_keys = flat["event"]["stage_registration_fields"] or flat["event"]["registration_fields"]
        if "contact" in contact_keys:
            contact_type = str(payload.get("contact_type", "微信"))
            contact_value = str(payload.get("contact_value", "")).strip()
            if contact_type not in ("微信", "QQ") or not contact_value:
                return jsonify({"error": "请选择微信或 QQ，并填写对应账号"}), 400
            values["contact_type"] = contact_type
            values["contact_value"] = contact_value
        for field in flat["event"]["stage_custom_fields"]:
            values[field["id"]] = str(payload.get(field["id"], "")).strip()
        if stage_id not in user["stage_signups"]:
            user["stage_signups"].append(stage_id)
        add_message(flat, user["uid"], "赛段报名成功", f"你已完成{flat['event']['stage']}报名，可查看本赛段赛程。")
        add_log(flat, f"用户 {user['uid']} 完成 {flat['event']['stage']} 赛段报名")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/fields/add")
def api_fields_add():
    payload = request.get_json(force=True)
    label = str(payload.get("label", "")).strip()
    if not label:
        return jsonify({"error": "收集项名称不能为空"}), 400
    with LOCK:
        state = load_state()
        event = current_event(state)
        target = event if payload.get("scope") == "event" else current_stage(state, event)
        field_type = payload.get("type") if payload.get("type") in ("text", "select") else "text"
        options = [value.strip() for value in str(payload.get("options", "")).replace("，", ",").split(",") if value.strip()]
        if field_type == "select" and not options:
            return jsonify({"error": "自定义选项至少填写一个"}), 400
        field = {
            "id": f"custom_{datetime.now().strftime('%H%M%S%f')}", "label": label,
            "type": field_type, "required": bool(payload.get("required", True)), "options": options,
        }
        target["custom_fields"].append(field)
        add_log(flat_state(state), f"新增自定义收集项 {label}（{payload.get('scope')}）")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/fields/delete")
def api_fields_delete():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        event = current_event(state)
        target = event if payload.get("scope") == "event" else current_stage(state, event)
        target["custom_fields"] = [field for field in target["custom_fields"] if field["id"] != payload["field_id"]]
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/demo-date")
def api_demo_date():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        state["demo_date"] = payload["date"]
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/confirm-session")
def api_confirm_session():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        session = payload.get("session")
        if session not in flat["event"]["sessions"]:
            return jsonify({"error": "场次不存在"}), 400
        user = current_user(flat)
        user["next_session"] = session
        add_message(flat, user["uid"], "次日参赛确认成功", f"已确认 {flat['event']['next_date']} {session} 场，分组与房间号将在确认截止后公布。")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/room")
def api_room():
    payload = request.get_json(force=True)
    room = str(payload.get("room", "")).strip()
    if len(room) != 4 or not room.isdigit():
        return jsonify({"error": "房间号必须为 4 位数字"}), 400
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        group = next(g for g in flat["groups"] if g["id"] == int(payload["group_id"]))
        group["room"] = room
        group["notified"] = True
        for uid in group["members"]:
            add_message(flat, uid, "房间号更新", f"{group['date']} {group['session']} 场房间号已更新为 {room}，请使用最新房间号进房。")
        add_log(flat, f"第 {group['id']} 组房间号修改为 {room} 并重新通知")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/groups/shuffle")
def api_groups_shuffle():
    with LOCK:
        state = load_state()
        event = current_event(state)
        stage = current_stage(state, event)
        users = event["users"][:]
        random.shuffle(users)
        event["groups"] = [g for g in event["groups"] if g["stage_id"] != stage["id"]]
        event["matches"] = [m for m in event["matches"] if m["stage_id"] != stage["id"]]
        for offset in range(0, len(users), stage["group_size"]):
            members = users[offset:offset + stage["group_size"]]
            group = {"id": offset // stage["group_size"] + 1, "stage_id": stage["id"], "room": "待录入", "members": [u["uid"] for u in members], "date": stage["current_date"], "session": stage["sessions"][0], "notified": False}
            event["groups"].append(group)
            for round_no in range(1, stage["daily_matches"] + 1):
                event["matches"].append(make_match(stage["id"], group, round_no, event["users"], stage["points"]))
        add_log(flat_state(state), f"{stage['name']} 重新盲排，每 {stage['group_size']} 人一组")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/upload")
def api_upload():
    match_id = request.form.get("match_id")
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        match = next((m for m in flat["matches"] if m["id"] == match_id), None)
        if not match:
            return jsonify({"error": "比赛不存在"}), 404
        file = request.files.get("screenshot")
        if file and file.filename:
            filename = secure_filename(file.filename)
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                return jsonify({"error": "仅支持 PNG、JPG、JPEG 图片"}), 400
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            file.save(UPLOAD_DIR / filename)
            match["image"] = f"/uploads/{filename}"
        else:
            match["image"] = ""
        match["status"] = "pending"
        match["uploaded_at"] = now_text()
        match["confirmed_at"] = ""
        add_message(flat, flat["current_uid"], "战绩已提交，等待确认", f"第 {match['round']} 局战绩已识别，赛果确认后积分生效。")
        add_log(flat, f"第 {match['group_id']} 组第 {match['round']} 局上传截图，本地模拟 AI 识别完成")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/review/result")
def api_review_result():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        match = next(m for m in flat["matches"] if m["id"] == payload["match_id"])
        result = next(r for r in match["results"] if r["uid"] == payload["uid"])
        old_points = result["points"]
        new_points = max(0, int(payload["points"]))
        result["points"] = new_points
        match["revisions"].insert(0, {"time": now_text(), "operator": "本地运营", "text": f"{result['nickname']}：名次保持第 {result['rank']} 名，积分 {old_points} → {new_points}"})
        add_log(flat, f"修改第 {match['group_id']} 组第 {match['round']} 局 {result['nickname']} 的积分为 {new_points}，名次不变")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/review/confirm")
def api_review_confirm():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        match = next(m for m in flat["matches"] if m["id"] == payload["match_id"])
        if match["status"] != "pending":
            return jsonify({"error": "请先上传并完成 AI 识图"}), 400
        match["status"] = "confirmed"
        match["confirmed_at"] = now_text()
        group = next(g for g in flat["groups"] if g["id"] == match["group_id"])
        for uid in group["members"]:
            add_message(flat, uid, "赛果已确认", f"第 {match['round']} 局赛果已确认。完成今日全部局次后，当日积分统一结算。")
        user = current_user(flat)
        stats = user_stats(flat, user)
        if stats["day_valid"]:
            add_message(flat, user["uid"], "当日积分已结算", f"今日全部 {flat['event']['daily_matches']} 局赛果已确认，当日 {stats['day_score']} 分已生效，当前总积分 {stats['total_score']} 分。")
        add_log(flat, f"确认第 {match['group_id']} 组第 {match['round']} 局赛果，榜单草稿已更新")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/ranking/publish")
def api_ranking_publish():
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        stage = current_stage(state)
        stage["ranking_published"] = True
        for user in flat["users"]:
            add_message(flat, user["uid"], "赛事榜单已发布", f"{flat['event']['stage']}最新榜单已发布，可在赛事榜单页查看。榜单排名不等于正式晋级结果。")
        add_log(flat, f"确认并发布 {flat['event']['stage']} C 端榜单")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/advance/supplement")
def api_advance_supplement():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        stage = current_stage(state)
        uid = str(payload["uid"])
        if uid not in stage["supplemental_uids"]:
            stage["supplemental_uids"].append(uid)
        add_log(flat_state(state), f"运营手动补录 {uid}：{payload.get('reason', '名额内人工补录')}")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/advance/publish")
def api_advance_publish():
    with LOCK:
        state = load_state()
        data = public_state(state)
        flat = flat_state(state)
        stage = current_stage(state)
        if data["tie_pending"]:
            return jsonify({"error": "请先处理晋级边界同分人员"}), 400
        stage["official_uids"] = [user["uid"] for user in flat["users"] if data["stats"][user["uid"]]["expected_advance"]]
        for uid in stage["official_uids"]:
            add_message(flat, uid, "正式晋级通知", f"恭喜你在{flat['event']['name']}{flat['event']['stage']}中正式晋级，下一阶段赛程将另行发布。")
        stage["advancement_published"] = True
        add_log(flat, f"确认并发布 {flat['event']['stage']} 正式晋级名单")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/players/add")
def api_players_add():
    payload = request.get_json(force=True)
    uid = str(payload.get("uid", "")).strip()
    nickname = str(payload.get("nickname", "补录选手")).strip() or "补录选手"
    if not uid:
        return jsonify({"error": "请输入 UID"}), 400
    with LOCK:
        state = load_state()
        event = current_event(state)
        if any(user["uid"] == uid for user in event["users"]):
            return jsonify({"error": "该 UID 已在选手列表中"}), 400
        event["users"].append({"uid": uid, "nickname": nickname, "game_nick": nickname, "registered": True, "wechat": "", "phone": "", "game_id": "", "channel": "微信", "wechat_qr": "", "game_shot": "", "history_by_stage": {}, "next_session": "15:00", "leader": "待分配", "leader_uid": "", "custom_values": {}, "stage_signups": [], "stage_signup_values": {}})
        add_log(flat_state(state), f"运营手工补录选手 {uid} {nickname}")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/message")
def api_message():
    payload = request.get_json(force=True)
    content = str(payload.get("content", "")).strip()
    if not content:
        return jsonify({"error": "消息内容不能为空"}), 400
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        target = payload.get("target", "current")
        if target == "current":
            targets = [current_user(flat)["uid"]]
        elif target == "advance_expected":
            computed = public_state(state)
            targets = [user["uid"] for user in flat["users"] if computed["stats"][user["uid"]]["expected_advance"]]
        elif target == "advance_official":
            stage = current_stage(state)
            targets = list(stage["official_uids"])
        elif target == "unread":
            targets = list({message["uid"] for message in flat["messages"] if not message["read"]})
        elif target == "group_current":
            targets = list(flat["group"]["members"])
        else:
            targets = [user["uid"] for user in flat["users"]]
        batch_id = f"custom_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        for uid in targets:
            add_message(flat, uid, str(payload.get("title", "赛事通知"))[:30], content, batch_id)
        add_log(flat, f"发送端内消息给 {len(targets)} 人")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/messages/read")
def api_messages_read():
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        for message in flat["messages"]:
            if message["uid"] == flat["current_uid"]:
                message["read"] = True
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/groups/move")
def api_groups_move():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        uid = str(payload["uid"])
        source = next(g for g in flat["groups"] if uid in g["members"])
        target = next(g for g in flat["groups"] if g["id"] == int(payload["group_id"]))
        if source["id"] == target["id"]:
            return jsonify({"error": "选手已在目标分组"}), 400
        source["members"].remove(uid)
        swap_uid = None
        if len(target["members"]) >= flat["event"]["group_size"]:
            swap_uid = target["members"].pop(0)
            source["members"].append(swap_uid)
        target["members"].append(uid)
        for group in [source, target]:
            for match in [m for m in flat["matches"] if m["group_id"] == group["id"]]:
                fresh = make_match(flat["current_stage_id"], group, match["round"], flat["users"], flat["event"]["points"])
                match["results"] = fresh["results"]
        add_log(flat, f"将选手 {uid} 从第 {source['id']} 组调整至第 {target['id']} 组")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/advance/tie")
def api_advance_tie():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        stage = current_stage(state)
        tied = [str(uid) for uid in payload["uids"]]
        selected = str(payload["selected_uid"])
        for uid in tied:
            if uid not in stage["tie_excluded_uids"]:
                stage["tie_excluded_uids"].append(uid)
            if uid in stage["supplemental_uids"]:
                stage["supplemental_uids"].remove(uid)
        stage["tie_excluded_uids"] = [uid for uid in stage["tie_excluded_uids"] if uid != selected]
        if selected not in stage["supplemental_uids"]:
            stage["supplemental_uids"].append(selected)
        add_log(flat, f"边界同分处理：录取 {selected}；{payload.get('reason', '运营确认同分处理结果')}")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/message/config")
def api_message_config():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        key = payload["key"]
        config = flat["event"]["message_settings"][key]
        config["enabled"] = bool(payload.get("enabled", config["enabled"]))
        config["title"] = str(payload.get("title", config["title"])).strip() or config["title"]
        config["content"] = str(payload.get("content", config["content"])).strip() or config["content"]
        add_log(flat, f"更新自动消息配置：{config['title']}（{'开启' if config['enabled'] else '关闭'}）")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/message/resend")
def api_message_resend():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        source = next(m for m in flat["messages"] if m["id"] == int(payload["message_id"]))
        add_message(flat, source["uid"], source["title"], source["content"])
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/message/resend-batch")
def api_message_resend_batch():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        batch_id = payload["batch_id"]
        unread = [m for m in flat["messages"] if m.get("batch_id", f"auto_{m['id']}") == batch_id and not m["read"]]
        if not unread:
            return jsonify({"error": "该批次没有未读用户"}), 400
        new_batch = f"remind_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        for message in unread:
            add_message(flat, message["uid"], message["title"], message["content"], new_batch)
        add_log(flat, f"向批次 {batch_id} 的 {len(unread)} 名未读用户重发通知")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/leaders/add")
def api_leaders_add():
    payload = request.get_json(force=True)
    uid = str(payload.get("uid", "")).strip()
    name = str(payload.get("name", "")).strip()
    if not uid.isdigit() or not name:
        return jsonify({"error": "领队 UID 必须为数字，昵称不能为空"}), 400
    with LOCK:
        state = load_state()
        if any(leader["uid"] == uid for leader in state["leaders"]):
            return jsonify({"error": "该领队 UID 已存在"}), 400
        state["leaders"].append({"uid": uid, "name": name, "capacity": max(1, int(payload.get("capacity", 8))), "enabled": True})
        add_log(flat_state(state), f"新增领队 {name}（UID {uid}）")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/leaders/update")
def api_leaders_update():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        leader = next(leader for leader in state["leaders"] if leader["uid"] == str(payload["uid"]))
        leader["capacity"] = max(1, int(payload.get("capacity", leader["capacity"])))
        leader["enabled"] = bool(payload.get("enabled", leader["enabled"]))
        add_log(flat_state(state), f"更新领队 {leader['name']}（UID {leader['uid']}）配置")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/leaders/delete")
def api_leaders_delete():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        uid = str(payload["uid"])
        if any(user.get("leader_uid") == uid for event in state["events"] for user in event["users"]):
            return jsonify({"error": "该领队名下仍有选手，请先调整选手归属"}), 400
        state["leaders"] = [leader for leader in state["leaders"] if leader["uid"] != uid]
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/players/leader")
def api_players_leader():
    payload = request.get_json(force=True)
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        user = next(user for user in flat["users"] if user["uid"] == str(payload["uid"]))
        leader = next(leader for leader in state["leaders"] if leader["uid"] == str(payload["leader_uid"]))
        assigned = sum(1 for item in flat["users"] if item.get("leader_uid") == leader["uid"] and item["uid"] != user["uid"])
        if not leader["enabled"] or assigned >= leader["capacity"]:
            return jsonify({"error": "该领队已停用或名额已满"}), 400
        user["leader_uid"] = leader["uid"]
        user["leader"] = leader["name"]
        add_log(flat, f"将选手 {user['uid']} 调整给 {leader['name']}（UID {leader['uid']}）")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/leaders/assign")
def api_leaders_assign():
    with LOCK:
        state = load_state()
        flat = flat_state(state)
        leaders = sorted([leader for leader in state["leaders"] if leader["enabled"]], key=lambda item: item["capacity"], reverse=True)
        if len(flat["users"]) > sum(leader["capacity"] for leader in leaders):
            return jsonify({"error": "可用领队容量不足，请先新增领队或提高容量"}), 400
        for user in flat["users"]:
            user["leader_uid"] = ""
            user["leader"] = "待分配"
        for user in flat["users"]:
            candidates = [item for item in leaders if sum(1 for u in flat["users"] if u.get("leader_uid") == item["uid"]) < item["capacity"]]
            if not candidates:
                return jsonify({"error": "领队容量不足，分配已停止"}), 400
            leader = max(candidates, key=lambda item: ((item["capacity"] - sum(1 for u in flat["users"] if u.get("leader_uid") == item["uid"])) / item["capacity"], item["capacity"]))
            user["leader_uid"] = leader["uid"]
            user["leader"] = leader["name"]
        add_message(flat, flat["current_uid"], "领队匹配成功", f"已为你匹配{current_user(flat)['leader']}（UID {current_user(flat)['leader_uid']}），并自动拉起点点小队群。")
        add_log(flat, "按容量优先和剩余容量比例均衡分配领队，并自动建群")
        save_state(state)
        return jsonify(public_state(state))


@app.post("/api/reset")
def api_reset():
    with LOCK:
        state = seed_state()
        save_state(state)
        return jsonify(public_state(state))


if __name__ == "__main__":
    load_state()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False, threaded=True)
