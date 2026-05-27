# B站自动化工具集

提供两个实用脚本：
- **评论脚本**（基础版 `bili_anto_comment.py` / 增强版 `bili_anto_comment_e.py`）：自动向指定UP主的最新视频发送预设评论。
- **点赞脚本**（`bili_anto_like.py`）：自动对指定UP主最新视频下的所有评论（含一级评论和子评论）进行点赞，支持风控对抗。

## 功能特性

### 评论脚本
- 自动获取UP主昵称并填充到评论模板中（支持 `{nickname}` 占位符）
- 获取每个UP主的最新一条视频
- 向该视频发送自定义评论
- 支持多UP主批量处理，可配置发送间隔
- 增强版（`bili_anto_comment_e.py`）提供“防重复评论”检查（基于评论区第一页数据）

### 点赞脚本
- 自动获取指定UP主的最新视频
- 获取视频下所有一级评论（根评论）和可选子评论（回复）
- 逐条进行点赞操作
- 内置随机延时、指数退避重试、会话预热等防风控机制
- 支持试运行模式（`DRY_RUN`），仅获取评论列表不实际点赞

## 环境要求

- Python 3.7+
- 安装依赖：`pip install requests bilibili-api-python`

## 配置说明

### 通用配置（所有脚本）

脚本需要你提供B站登录凭证（Cookie中的关键字段），获取方法：
1. 登录 B 站网页版（https://www.bilibili.com）
2. 打开浏览器开发者工具 → 应用/存储 → Cookies → `https://www.bilibili.com`
3. 复制以下值：
   - `SESSDATA`
   - `bili_jct`（即 CSRF Token）
   - `DedeUserID`（部分脚本需要）
   - `buvid3`（点赞脚本强烈建议填写，可降低风控）

### 评论脚本配置（bili_anto_comment.py / bili_anto_comment_e.py）

打开脚本文件，修改以下配置项：

| 配置项 | 说明 |
|--------|------|
| `CREDENTIAL` | 登录凭证（填入 `sessdata`、`bili_jct`、`dedeuserid`） |
| `UP_MIDS`   | 目标UP主的UID列表（整数类型） |
| `SEND_INTERVAL` | 每次评论后的等待间隔（秒），建议 ≥5 秒 |
| `COMMENT_TEMPLATE` | 评论模板，使用 `{nickname}` 自动替换为UP主昵称 |

### 点赞脚本配置（bili_anto_like.py）

打开脚本文件，修改以下配置项：

| 配置项 | 说明 |
|--------|------|
| `SESSDATA`、`BILI_JCT`、`BUVid3`、`DEDE_USER_ID` | 从浏览器Cookie中获取，**强烈建议填写 `BUVid3`** 以避免412风控 |
| `UP_MID` | 目标UP主的UID（单个） |
| `MIN_DELAY` / `MAX_DELAY` | 点赞间隔秒数（随机），建议 2~5 秒 |
| `MAX_RETRIES` | 点赞失败时的最大重试次数 |
| `DRY_RUN` | 试运行模式，设为 `True` 时不实际点赞，仅输出模拟信息 |
| `LIKE_SUB_COMMENTS` | 是否点赞子评论（回复），`True` 为全部点赞，`False` 仅点赞一级评论 |

## 使用方法

### 评论脚本

#### 基础版（bili_anto_comment.py）
```bash
python bili_anto_comment.py
```
运行后脚本会依次处理列表中的每个UP主，输出详细日志。增强版会检查当前账号是否已在视频下评论过，避免重复发送。

### 点赞脚本

```bash
python bili_anto_like.py
```
脚本将：

1. 自动获取指定UP主的最新视频  
2. 获取该视频下的所有评论（含子评论，可选）  
3. 逐条点赞（实际请求或试运行模拟）  

## 注意事项

- 请确保Cookie有效且未过期，否则会返回 -101 错误。  
- 评论频率过高可能导致账号风险，建议适当调大 SEND_INTERVAL。  
- 点赞脚本的风控参数，务必配置完整的Cookie（特别是 buvid3），并使用合理的延时（2~5秒）。  
  如仍触发412，可尝试增加延时或更换账号。  
- 增强版评论脚本的“去重检查”基于评论区第一页（约20条），若之前评论较靠后可能无法检测到，但足以避免短时间内重复发送。  
- 请遵守B站社区规范，合理使用脚本。  

## 常见错误码

| 错误码 | 含义    | 解决方法    |
|---|---|---|
| -101   | 账号未登录或Cookie失效 | 重新获取Cookie    |
| -111   | CSRF Token验证失败 | 检查 bili_jct 是否正确    |
| -403 / 412 | 操作被拒绝（风控） | 增加风控、补全 buvid3 或更换账号 |

## 许可证

仅供学习交流使用，请勿用于商业或恶意刷屏行为。
