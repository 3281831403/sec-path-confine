# sec-path-confine

## 题面

文件预览接口只允许读上传目录，攻击者用两层相对路径就读到了系统配置：归一化只替换分隔符，不折叠连续的点点段，向上回退仍然成立；包含判断用字符串前缀，同名前缀的兄弟目录被判为在根内；包含判断不补目录分隔符，根目录自身被排除；拼接后不做真实路径解析，符号链接指向外部也能通过；符号链接检查只比较文件名，不比较目标，同名文件可被替换；绝对路径检查漏掉盘符形式，Windows 路径直接逃逸；归一化不处理 Unicode 变体，全角斜杠绕过检查；策略校验不检查是否允许绝对路径，放行策略本身就有缺口；批量拼接复用根目录字符串，第二个根被忽略；越界时返回空串而不是抛异常，调用方拿到空路径后回退到工作目录。conf/paths.py 是核心，tests/unit/test_paths.py 15个红。要修的是：按上面的顺序把 10 个缺陷逐个修掉。

## 运行方式

在仓库根目录执行：

```bash
python -m pytest tests -q
```

初始状态必须恰好输出 `15 failed`，且不能出现 collection error、import error、syntax error 或 test error；所有失败都应来自 `conf/paths.py` 的 `NotImplementedError`。实现完成后应为 `15 passed`。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 安全 |
| 子方向 | 漏洞检测与攻防 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## tests 不可修改

`tests/unit/test_paths.py` 和 `tests/behaviour/test_paths_edge.py` 是固定的验收契约，不得修改、删除、跳过或参数化。只能实现 `conf/paths.py`，用测试结果验证修复，不能通过改动测试来改变初始的 `15 failed`。

## 测试拆分布局

这是测试拆分布局：`tests/unit/test_paths.py` 包含 10 条缺陷契约测试，分别对应题面中的 10 个缺陷；`tests/behaviour/test_paths_edge.py` 包含 5 条边界行为测试。两个目录合计 15 条测试，统一用 `pytest tests -q` 收集，初始恰好 15 failed。
