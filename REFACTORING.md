# 重构记录

**日期**: 2026-04-09
**目标**: 根据当前业务逻辑重构代码，使结构更清晰、更易维护。不改变任何 API 合约或数据流。

---

## 重构前的问题

| 问题 | 涉及文件 | 影响 |
|------|----------|------|
| `app.py` 混合了路由、流水线编排、线程状态、WebSocket 逻辑 | `app.py` (411行) | 难以定位和修改业务逻辑 |
| `result_manager.py` 承担了 5 种职责（图片打开、EXIF、缩略图、JSON管理、哈希） | `result_manager.py` (320行) | 修改一个功能容易影响其他功能 |
| `llm_client.py` 包含 120 行内联 prompt 字符串，且 EXIF 处理与 `result_manager.py` 重复 | `llm_client.py` (430行) | Prompt 难以维护，重复代码增加 bug 风险 |
| 单张/批量分析的响应解析逻辑大量重复 | `llm_client.py` | 修改解析逻辑需要同步改两处 |
| `mediapipe_engine.py` 被 import 但从未调用 | `app.py`, `mediapipe_engine.py` | 误导代码阅读者 |
| `API_BASE` 在 `App.jsx` 和 `DetailPanel.jsx` 中重复硬编码 | `App.jsx`, `DetailPanel.jsx` | 端口变更需要多处修改 |
| `App.jsx` 管理了 10+ 个 state，是前端"上帝组件" | `App.jsx` (287行) | 状态逻辑与 UI 耦合严重 |

---

## 重构方案

共 6 个 Phase，按依赖顺序执行：

```
Phase 0（清理死代码）── 无依赖
Phase 1（前端 API 层）── 无依赖
Phase 2（image_utils）── 无依赖
Phase 4（prompts+LLM）── 依赖 Phase 2
Phase 3（pipeline）── 依赖 Phase 2 + Phase 4
Phase 5（usePhotoStore）── 依赖 Phase 1
```

---

## 各 Phase 详细说明

### Phase 0：清理死代码

**修改文件**：
- `backend/app.py` — 移除未使用的 `from mediapipe_engine import analyze_image`
- `backend/config.py` — 给 `MEDIAPIPE_*` 和 `EAR_THRESHOLD` 加注释标记为当前未使用

### Phase 1：前端提取 API 服务层

**新建文件**：`src/services/api.js`

将所有 API 调用集中到一个服务模块：
- 统一定义 `API_BASE`（基于 `window.FLASK_PORT`）
- 封装通用 `request()` 方法，统一 error handling
- 导出所有 API 函数：`loadPhotos`、`startDetection`、`cancelDetection`、`retryPhoto`、`updateResult`、`exportPhotos`
- 导出 URL 构建函数：`getThumbUrl()`、`getImageUrl()`、`buildFileThumbUrl()`、`getWsUrl()`

**修改文件**：
- `src/App.jsx` — 删除 `const API_BASE`，所有 `fetch()` 替换为 `api.*()` 调用
- `src/components/DetailPanel.jsx` — 删除本地 `API_BASE`，改用 `getThumbUrl()`
- `src/components/PhotoCard.jsx` — 删除本地 `buildThumbUrl()`，改用 `buildFileThumbUrl()`

### Phase 2：后端提取 image_utils.py

**新建文件**：`backend/image_utils.py`

从 `result_manager.py` 中提取所有图片处理相关函数：
- `open_image(file_path)` — 打开图片（含 RAW 格式支持）
- `open_and_prepare_image(file_path, max_width=None)` — **新增**，整合 EXIF 矫正 + 可选缩放 + RGB 转换，消除 `result_manager.py` 和 `llm_client.py` 中的重复逻辑
- `get_exif_orientation(img)` — 读取 EXIF 方向（原 `_get_exif_orientation_from_image`）
- `_clear_exif_orientation(img)` — 清除 EXIF 方向标记
- `_get_orientation_via_exiftool(file_path)` — 通过 ExifTool 读取方向
- `_extract_embedded_jpeg(file_path)` — 从 RAW 文件提取嵌入式 JPEG

**修改文件**：
- `backend/result_manager.py` (320→173行) — 删除已迁移函数，`_generate_thumbnail` 改用 `open_and_prepare_image`
- `backend/llm_client.py` — `encode_image_base64` 改用 `open_and_prepare_image`，从 33 行简化到 12 行

### Phase 3：后端提取 pipeline.py + tag_mapper.py

**新建文件**：`backend/pipeline.py` (209行)

从 `app.py` 中提取所有流水线相关逻辑：
- `init(socketio)` — 接收 socketio 实例，初始化模块状态
- `cancel()` / `is_cancelled()` — 取消控制
- `run_pipeline(folder_path, analyze_batch_fn)` — 主流水线编排
- `process_single_photo(folder_path, file_name, analyze_fn)` — 单张重试
- `process_batch()` / `process_one_photo()` — 批量和单张处理
- `_apply_llm_result()` — 应用 LLM 结果到照片记录
- `_emit_photo_update()` — 通过 WebSocket 推送照片更新

设计要点：通过 `init(socketio)` 注入依赖，避免循环引用。`analyze_batch_fn` 和 `analyze_fn` 作为参数传入，解耦 LLM 实现选择。

**新建文件**：`backend/tag_mapper.py` (36行)

从 `_apply_llm_result` 中提取业务规则映射：
- `REASON_TAG_MAP` — 英文原因代码到中文标签的映射
- `map_llm_result_to_updates(llm_result)` — 纯函数，将 LLM 返回转换为照片元数据更新，可独立测试

**修改文件**：
- `backend/app.py` (411→214行) — 仅保留 Flask 配置、路由定义和 `main()`

### Phase 4：整理 llm_client.py

**新建文件**：`backend/prompts.py` (123行)

从 `llm_client.py` 中提取两个 prompt 模板：
- `PROMPT_TEMPLATE` — 单张分析 prompt
- `BATCH_PROMPT_TEMPLATE` — 批量分析 prompt

**修改文件**：
- `backend/llm_client.py` (430→255行) — 提取共享辅助函数：
  - `_parse_llm_json(content)` — 统一 JSON 解析和 markdown 清理
  - `_log_token_usage(data, label)` — 统一 token 用量日志
  - `_post_to_llm(payload)` — 统一 API 请求发送

### Phase 5：前端提取 usePhotoStore Hook

**新建文件**：`src/hooks/usePhotoStore.js` (84行)

从 `App.jsx` 中提取照片状态管理逻辑：
- 管理 `photoNames`、`photoMap`、`photoVersion`、`selectedFileName`
- 提供 `loadPhotos()`、`updatePhoto()`、`patchPhoto()`、`selectPhoto()` 方法
- 提供 `getFilteredNames(filterTags)` 和 `getStatusCounts(filteredLength)` 计算方法

**修改文件**：
- `src/App.jsx` (287→210行) — 使用 `usePhotoStore()` hook，仅保留流程控制状态（`folderPath`、`isProcessing`、`progress` 等）

---

## 重构后文件结构

```
backend/
  app.py              411→214行  （路由 + Flask 配置）
  config.py           49→49行     （不变）
  result_manager.py   320→173行  （JSON管理 + 缩略图 + 哈希）
  llm_client.py       430→255行  （API调用，无 prompt，无 EXIF）
  image_utils.py      新建 169行 （图片打开、EXIF、RAW）
  pipeline.py         新建 209行 （流水线编排、线程）
  tag_mapper.py       新建  36行 （LLM结果→元数据映射）
  prompts.py          新建 123行 （Prompt模板）
  export_manager.py   66→66行     （不变）
  mock_llm_response.py 171→171行 （不变）
  mediapipe_engine.py 123→123行  （标记为未使用）

src/
  App.jsx              287→210行 （薄编排层）
  services/api.js      新建  79行 （API调用 + URL构建）
  hooks/usePhotoStore.js 新建 84行（照片状态管理）
  components/          不变
  utils/               不变
```

---

## 关键设计决策

### pipeline.py 的依赖注入

`pipeline.py` 需要 `socketio` 实例来发送 WebSocket 事件，但直接 import `app.py` 中的 `socketio` 会造成循环引用。解决方案是提供 `init(socketio)` 函数，在 `app.py` 创建 socketio 后调用：

```python
# app.py
socketio = SocketIO(app, ...)
pipeline.init(socketio)
```

### LLM 函数作为参数传入

`run_pipeline` 和 `process_single_photo` 接收 `analyze_batch_fn` / `analyze_fn` 作为参数，而非直接 import LLM 模块。这样 mock/real LLM 的选择逻辑保留在 `app.py`，pipeline 模块保持纯粹。

### open_and_prepare_image 消除重复

`result_manager.py::_generate_thumbnail` 和 `llm_client.py::encode_image_base64` 中有几乎相同的 EXIF 矫正 + 缩放 + RGB 转换逻辑。`open_and_prepare_image()` 将其统一为一个函数，两处调用者各减少约 15 行代码。

---

## API 合约变更

无。所有 REST API 端点、WebSocket 事件、数据格式均保持不变。
