import asyncio
import time
from bilibili_api import user, comment, Credential
from bilibili_api.exceptions import ResponseCodeException

# ========== 配置区域 ==========
# 请填写你自己的身份凭证（确保Cookie有效）
CREDENTIAL = Credential(
    sessdata="b24f956c,1795249818,dbd22*52CjDC3UVp46hctdh6Tg4cwQNp8r2AFmG25D8Hw_EukSw7xNnuhOtanO6an5o7gX0IB6gSVjNDQXlaWW9mYjI3VXhSSURfY0pGVUdvam5ubnk0UE43M1ZXMks1VDBVT2JLWU9VWWpIU3BDQmxULU9vRUd1WUs0NEV5aUpMNjI4YVpvOVdsSnhUYXhRIIEC",
    bili_jct="d74ffc96b608ceeb77588a510cec58e7",  # 即csrf token
    dedeuserid="440966743"
)

# 需要评论的UP主UID列表（示例：替换为真实UID）
UP_MIDS = [
    440966743,   # UP主A
    3546604361484563,   # UP主B
]

# 评论发送间隔（秒），避免触发频率限制
SEND_INTERVAL = 5

# 评论模板（将 {nickname} 替换为UP主昵称）
COMMENT_TEMPLATE = "检测到{nickname}的最新视频：：：回去娶个媳妇，生个娃，背上房贷车贷，把日子过起来[星星眼]"
# =============================

async def get_up_nickname(uid: int, credential: Credential) -> str:
    """获取UP主昵称"""
    u = user.User(uid=uid, credential=credential)
    try:
        info = await u.get_user_info()
        return info.get('name', f'UID{uid}')
    except Exception as e:
        print(f"⚠️ 获取UP主 {uid} 昵称失败: {e}")
        return f"UID{uid}"

async def get_latest_video_aid(uid: int, credential: Credential):
    """获取UP主最新视频的aid和标题，返回 (aid, bvid, title) 或 None"""
    u = user.User(uid=uid, credential=credential)
    try:
        video_list = await u.get_videos(ps=1)          # ps=1 只获取最新一条
        if not video_list.get('list', {}).get('vlist'):
            print(f"⚠️ UP主 {uid} 暂无视频")
            return None
        latest = video_list['list']['vlist'][0]
        aid = latest['aid']
        bvid = latest['bvid']
        title = latest['title']
        return aid, bvid, title
    except ResponseCodeException as e:
        print(f"❌ 获取UP主 {uid} 视频失败: {e.code} - {e.msg}")
        return None
    except Exception as e:
        print(f"⚠️ 获取UP主 {uid} 视频时发生未知错误: {e}")
        return None

async def send_comment_to_video(aid: int, nickname: str, credential: Credential):
    """向指定aid的视频发送评论（内容包含UP主昵称）"""
    comment_text = COMMENT_TEMPLATE.format(nickname=nickname)
    try:
        resp = await comment.send_comment(
            oid=aid,
            type_=comment.CommentResourceType.VIDEO,
            text=comment_text,
            credential=credential
        )
        print(f"✅ 评论发送成功！UP主「{nickname}」视频aid={aid}，评论ID={resp['rpid']}")
        return True
    except ResponseCodeException as e:
        print(f"❌ 发送评论失败: {e.code} - {e.msg}")
        if e.code == -101:
            print("   提示：Cookie 可能已过期，请重新获取")
        elif e.code == -111:
            print("   提示：CSRF Token 验证失败，检查 bili_jct 值")
        return False
    except Exception as e:
        print(f"⚠️ 发送评论时发生未知错误: {e}")
        return False

async def process_up(uid: int, credential: Credential):
    """处理单个UP主：获取昵称 → 获取最新视频 → 发送评论"""
    print(f"\n--- 开始处理 UID: {uid} ---")
    
    # 1. 获取昵称
    nickname = await get_up_nickname(uid, credential)
    print(f"📢 UP主昵称: {nickname}")
    
    # 2. 获取最新视频
    video_info = await get_latest_video_aid(uid, credential)
    if not video_info:
        print(f"⏭️ 跳过 UID {uid}（无法获取视频）")
        return
    aid, bvid, title = video_info
    print(f"🎬 最新视频: 《{title}》 https://www.bilibili.com/video/{bvid}")
    
    # 3. 发送评论
    success = await send_comment_to_video(aid, nickname, credential)
    if success:
        print(f"✅ UID {uid} 处理完成")
    else:
        print(f"❌ UID {uid} 评论失败")

async def main():
    print(f"开始批量评论任务，共 {len(UP_MIDS)} 个UP主，评论间隔 {SEND_INTERVAL} 秒")
    for idx, uid in enumerate(UP_MIDS, 1):
        await process_up(uid, CREDENTIAL)
        if idx < len(UP_MIDS):          # 最后一个不需要等待
            print(f"⏳ 等待 {SEND_INTERVAL} 秒后继续...")
            await asyncio.sleep(SEND_INTERVAL)
    print("\n🎉 所有任务执行完毕！")

if __name__ == "__main__":
    asyncio.run(main())