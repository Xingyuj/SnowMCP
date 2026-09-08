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

## 选择提交身份

默认 `--identity preserve`：保留源提交的 Author（作者）和作者时间，Committer（提交者）使用目标仓库执行提交时的身份。这与旧版工具行为一致，并不复制源 Committer。

使用 `--identity local`：每条新提交的 Author 和 Committer 都使用目标仓库有效的 `user.name` / `user.email` 配置，作者时间重新生成。提交信息保持不变。

先设置目标仓库身份（仅影响该仓库）：

```bash
git -C /path/to/company-mirror config user.name "你的名字"
git -C /path/to/company-mirror config user.email "your.name@example.com"
```

然后迁移：

```bash
python3 scripts/sync_commits.py \
  --source /path/to/SnowMCP \
  --target /path/to/company-mirror \
  --range 'BASE..TIP' \
  --identity local \
  --apply
```

去掉 `--apply` 可预览将使用的身份。local 模式在开始时保存选定身份；冲突后仍通过 `--continue` / `--skip` / `--abort` 操作，无需重复传身份参数，也不会因中途修改 Git 配置而混用身份。已暂停的旧版同步保持原行为；要切换模式，应先取消该轮，再带上新参数重新同步。不要在暂停期间手动提交冲突结果，否则手动提交会使用你当时的 Git 身份设置。

完成后可检查：

```bash
git -C /path/to/company-mirror log -3 --format=fuller
```

该参数仅影响本轮新生成的提交，不修改已经同步完成的历史。

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
