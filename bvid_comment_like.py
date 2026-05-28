#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频评论批量点赞脚本（支持通过BVID指定视频，点赞一级评论+子评论）
增强特性：
- 支持单个或多个BVID（视频列表）
- 自动获取视频所有评论（含回复）
- 随机延时 + 指数退避重试，降低风控概率
- 模拟真实浏览器请求头，补全关键Cookie（buvid3等）
- 预热请求建立会话
- 支持试运行模式（DRY_RUN）
"""

import requests
import time
import random
from typing import List, Dict, Optional

# ---------------------------- 配置区域（请务必修改） ----------------------------
# 从浏览器中获取以下Cookie值（F12 -> Application -> Cookies -> https://www.bilibili.com）
SESSDATA = "af4f1fa7,1795420185,fc138*52CjAyM79mE_G8feJlMxbEh0hi-QqMwfWmD70J_ZThEX6Gtt2AEaqVTqwPR2-z05a4124SVkJ3NnY3ZHlGLVhlRkhGWE4xUkJST2l0M2h4NF8tTWZXbTVTaGZUNXdTanhvWGlFYzlTUkI4SzZFaG9QS3dZRXZ3X3QtcVdsT2RYSG1FdGxiNnNhTFlnIIEC"
BILI_JCT = "471954978aa88e0f5a0ce1b48d83fc50"    # CSRF Token
BUVid3 = "8F81CF06-39D1-D4DB-03AC-4474A86B94CE93856infoc"              # 强烈建议填写，解决412风控
DEDE_USER_ID = "440966743"      # 可选，填上更好

# UA保持不变即可
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 需要批量点赞的视频BVID列表（支持多个）
BVID_LIST = [
    "BV12FVT6YEwE",   # 示例，请替换为实际BVID
    # "BV1GJ411x7h7",
]

# 点赞间隔（秒），风控敏感操作，建议不低于2秒
MIN_DELAY = 2.0
MAX_DELAY = 5.0

# 最大重试次数（点赞失败时）
MAX_RETRIES = 3

# 是否仅模拟运行（不实际点赞，只获取评论信息）
DRY_RUN = False

# 是否点赞子评论（回复），若为False则只点赞一级评论
LIKE_SUB_COMMENTS = True
# -----------------------------------------------------------------


def get_cookies() -> Dict[str, str]:
    """构造携带登录信息的Cookie字典，补全buvid3等防风控字段"""
    cookies = {
        "SESSDATA": SESSDATA,
        "bili_jct": BILI_JCT,
        "buvid3": BUVid3,
        "DedeUserID": DEDE_USER_ID,
    }
    return {k: v for k, v in cookies.items() if v}


def get_headers() -> Dict[str, str]:
    """构造真实浏览器请求头"""
    return {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Upgrade-Insecure-Requests": "1",
    }


def create_session() -> requests.Session:
    """创建带完整Cookie和Headers的requests Session"""
    session = requests.Session()
    session.cookies.update(get_cookies())
    session.headers.update(get_headers())
    return session


def get_aid_by_bvid(session: requests.Session, bvid: str) -> Optional[int]:
    """
    通过视频BVID获取视频的aid（av号）
    返回：aid (int) 或 None
    """
    url = "https://api.bilibili.com/x/web-interface/view"
    params = {"bvid": bvid}
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data["code"] != 0:
            print(f"获取视频信息失败 (code: {data['code']}): {data.get('message', '未知错误')}")
            return None
        aid = data["data"]["aid"]
        title = data["data"]["title"]
        print(f"获取到视频: {title} (bvid: {bvid}, aid: {aid})")
        return aid
    except Exception as e:
        print(f"请求视频信息异常: {e}")
        return None


def fetch_comments(session: requests.Session, aid: int) -> List[Dict]:
    """获取视频的所有一级评论（根评论）"""
    comments = []
    pn = 1
    while True:
        url = "https://api.bilibili.com/x/v2/reply"
        params = {
            "oid": aid,
            "type": 1,
            "pn": pn,
            "ps": 20,
            "sort": 0,   # 0: 按热度
        }
        try:
            resp = session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                print(f"获取评论第{pn}页失败: {data.get('message', '未知错误')}")
                break
            replies = data["data"]["replies"]
            if not replies:
                break
            for r in replies:
                comments.append({
                    "rpid": r["rpid"],
                    "message": r["content"]["message"][:50],
                    "is_sub": False,
                    "root_rpid": None
                })
            print(f"已获取第{pn}页根评论，当前累计 {len(comments)} 条")
            # 判断是否还有下一页
            if data["data"]["page"]["num"] >= data["data"]["page"]["size"]:
                break
            pn += 1
            time.sleep(random.uniform(0.5, 1.5))  # 翻页间隔
        except Exception as e:
            print(f"请求评论异常: {e}")
            break
    return comments


def fetch_sub_comments(session: requests.Session, aid: int, root_rpid: int, root_msg_preview: str) -> List[Dict]:
    """获取某条根评论下的所有子评论（回复）"""
    sub_comments = []
    pn = 1
    while True:
        url = "https://api.bilibili.com/x/v2/reply/reply"
        params = {
            "oid": aid,
            "type": 1,
            "root": root_rpid,
            "pn": pn,
            "ps": 20
        }
        try:
            resp = session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                print(f"  获取回复第{pn}页失败: {data.get('message', '未知错误')}")
                break
            replies = data["data"]["replies"]
            if not replies:
                break
            for r in replies:
                sub_comments.append({
                    "rpid": r["rpid"],
                    "message": r["content"]["message"][:50],
                    "is_sub": True,
                    "root_rpid": root_rpid,
                    "root_msg_preview": root_msg_preview
                })
            print(f"  根评论 {root_rpid} 下已获取第{pn}页回复，累计 {len(sub_comments)} 条")
            if data["data"]["page"]["num"] >= data["data"]["page"]["size"]:
                break
            pn += 1
            time.sleep(random.uniform(0.3, 0.8))
        except Exception as e:
            print(f"请求回复异常: {e}")
            break
    return sub_comments


def fetch_all_comments(session: requests.Session, aid: int, include_subs: bool) -> List[Dict]:
    """获取所有评论（根评论 + 可选子评论）"""
    print("开始获取一级评论...")
    root_comments = fetch_comments(session, aid)
    if not root_comments:
        return []

    if not include_subs:
        return root_comments

    print(f"\n开始获取每条根评论下的子评论...")
    all_comments = []
    for idx, root in enumerate(root_comments, 1):
        print(f"[{idx}/{len(root_comments)}] 根评论: {root['message']}...")
        subs = fetch_sub_comments(session, aid, root["rpid"], root["message"])
        all_comments.append(root)
        all_comments.extend(subs)
        time.sleep(random.uniform(0.5, 1.0))
    return all_comments


def like_comment(session: requests.Session, aid: int, rpid: int, is_sub: bool = False) -> bool:
    """
    对单条评论点赞（根评论或子评论通用）
    返回：是否成功
    """
    url = "https://api.bilibili.com/x/v2/reply/action"
    data = {
        "oid": aid,
        "type": 1,
        "rpid": rpid,
        "action": 1,        # 1: 点赞
        "csrf": BILI_JCT
    }
    try:
        resp = session.post(url, data=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result["code"] == 0:
            return True
        elif result["code"] == 412:
            print("触发风控(412)，强制等待60秒...")
            time.sleep(60)
            return False
        else:
            print(f"点赞失败 (rpid={rpid}): {result.get('message', '未知错误')}")
            return False
    except Exception as e:
        print(f"点赞请求异常 (rpid={rpid}): {e}")
        return False


def like_with_retry(session: requests.Session, aid: int, rpid: int, is_sub: bool) -> bool:
    """带指数退避重试的点赞"""
    for attempt in range(MAX_RETRIES):
        ok = like_comment(session, aid, rpid, is_sub)
        if ok:
            return True
        if attempt < MAX_RETRIES - 1:
            wait = 2 ** attempt  # 1, 2, 4 秒
            print(f"  重试 {attempt+1}/{MAX_RETRIES}，等待 {wait} 秒...")
            time.sleep(wait)
    return False


def warm_up_session(session: requests.Session):
    """预热请求：先访问B站首页，建立完整会话"""
    print("正在建立会话连接...")
    try:
        session.get('https://www.bilibili.com/', timeout=10)
        print("会话建立成功")
        time.sleep(random.uniform(1, 2))
    except Exception as e:
        print(f"会话建立警告: {e}，继续执行...")


def process_video(session: requests.Session, bvid: str) -> None:
    """处理单个视频：获取aid -> 获取评论 -> 点赞"""
    print(f"\n========== 开始处理视频: {bvid} ==========")
    
    # 1. 通过bvid获取aid
    aid = get_aid_by_bvid(session, bvid)
    if not aid:
        print(f"无法获取视频 {bvid} 的aid，跳过。")
        return
    
    # 2. 获取所有评论（根+子）
    comments = fetch_all_comments(session, aid, LIKE_SUB_COMMENTS)
    if not comments:
        print("该视频暂无评论。")
        return
    
    print(f"\n共获取到 {len(comments)} 条评论（根评论 + 子评论），开始依次点赞...")
    
    # 3. 逐条点赞
    success_count = 0
    for idx, comment in enumerate(comments, 1):
        rpid = comment["rpid"]
        msg_preview = comment["message"]
        if comment.get("is_sub", False):
            prefix = f"[子评论] 回复“{comment['root_msg_preview'][:20]}” -> {msg_preview}"
        else:
            prefix = f"[根评论] {msg_preview}"
        print(f"[{idx}/{len(comments)}] {prefix}... ", end="")
        
        if DRY_RUN:
            print("[模拟]")
            success_count += 1
        else:
            ok = like_with_retry(session, aid, rpid, comment.get("is_sub", False))
            if ok:
                print("点赞成功")
                success_count += 1
            else:
                print("点赞失败")
        
        # 随机延时，避免风控
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        time.sleep(delay)
    
    print(f"视频 {bvid} 完成！成功点赞 {success_count} / {len(comments)} 条评论。")


def main():
    # 基本检查
    if SESSDATA == "你的SESSDATA值" or BILI_JCT == "你的bili_jct值":
        print("错误：请先配置有效的 SESSDATA 和 bili_jct")
        return
    if not BUVid3 or BUVid3 == "你的buvid3值":
        print("警告：buvid3 未配置，可能容易触发风控412，建议从浏览器复制完整buvid3")
    
    print("=== B站视频评论批量点赞脚本（支持BVID指定视频、一级评论+子评论）===")
    if DRY_RUN:
        print("【试运行模式】不会实际点赞")
    if LIKE_SUB_COMMENTS:
        print("【配置】将同时点赞一级评论和子评论")
    else:
        print("【配置】仅点赞一级评论")
    print(f"待处理视频数量: {len(BVID_LIST)}")
    
    session = create_session()
    warm_up_session(session)
    
    for bvid in BVID_LIST:
        process_video(session, bvid)
        # 视频之间的间隔，避免风控
        if len(BVID_LIST) > 1:
            time.sleep(random.uniform(5, 10))
    
    print("\n所有视频处理完毕。")


if __name__ == "__main__":
    main()