# 在镜像仓库之间迁移提交

工具：`scripts/sync_commits.py`。只需要 Python 3.11+ 和 Git，不需要安装项目依赖。

它把源仓库的已提交改动按顺序 cherry-pick 到目标仓库**当前分支**，保留每条提交信息、作者及作者时间。目标仓库可以有独立历史；新提交的父提交、committer 和 SHA 可能不同。不会配置 remote、push、强制覆盖分支或复制未提交文件。

## 准备

两个仓库都需要先在本地 checkout。先在目标仓库切换到需要接收改动的分支，并按你的远端流程同步；工作区必须干净，包括未跟踪文件。工具不会自动 stash 或切换分支。

## 预览与执行

例如，将 SnowMCP 中尚未进入其跟踪分支的修复迁移到公司镜像：

```bash
python3 scripts/sync_commits.py \
  --source /path/to/SnowMCP \
  --target /path/to/company-mirror \
  --range 'origin/feature/snow_mcp..HEAD'
```

范围在**源仓库**解析：不包含左端提交，包含右端提交，按从旧到新排列。`origin/...` 是本地跟踪引用，需要时先自行 fetch。

确认预览后加 `--apply`：

```bash
python3 scripts/sync_commits.py \
  --source /path/to/SnowMCP \
  --target /path/to/company-mirror \
  --range 'origin/feature/snow_mcp..HEAD' \
  --apply
```

也可以选取不连续的提交，按提供顺序迁移：

```bash
python3 scripts/sync_commits.py \
  --source /path/to/SnowMCP \
  --target /path/to/company-mirror \
  --commits OLDEST_SHA NEXT_SHA NEWEST_SHA \
  --apply
```

镜像间反向迁移只需交换 `--source` 和 `--target`。迁移成功后在目标仓库检查、测试，再自行 push。

## 冲突处理

有冲突时工具停止，已经迁移的提交保留，后续提交留在 Git sequencer 中。修复目标仓库的冲突文件并暂存：

```bash
git -C /path/to/company-mirror status
git -C /path/to/company-mirror add path/to/resolved-file
python3 scripts/sync_commits.py --target /path/to/company-mirror --continue
```

目标中已经有相同改动但 SHA 不同，可能产生空提交。检查后可跳过当前提交：

```bash
python3 scripts/sync_commits.py --target /path/to/company-mirror --skip
```

取消整个迁移序列，回到迁移前的 HEAD：

```bash
python3 scripts/sync_commits.py --target /path/to/company-mirror --abort
```

取消会放弃本轮冲突解决及当前序列的改动；迁移进行中不要夹杂无关编辑。继续/跳过/取消通过同一个工具执行，便于清理工作区 Git 目录内的状态文件。

## 边界

- 预览检查提交选择和目标状态，不保证应用时无冲突。
- 不自动去重不同 SHA 的相同补丁；空提交需检查后跳过。
- 拒绝 merge commit，避免猜测 mainline。请选取需要的普通提交。
- 不支持无初始提交的目标仓库、bare 仓库或 detached HEAD。
- 目标仓库的 Git hooks、签名设置和提交身份仍然生效。
- 传输通过本地 fetch 导入 Git 对象，不更改远端跟踪分支、标签或 FETCH_HEAD。

验证工具本身：

```bash
python3 -m unittest discover -s tests -p test_sync_commits.py -v
```
