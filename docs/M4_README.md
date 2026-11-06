# M4 商品结构

## 运行与演示
安装项目 requirements.txt，运行 `python app.py`，打开页面后选择 M4。
本模块仅使用项目自带真实聚合数据，主视图为热图与联动详情条形图。

1. **Compare structure**：2023年，以中国为收入锚点，在六国中按1.25倍范围匹配，得到中墨。HS87占比约为中国5.40%、墨西哥26.12%。
2. **Test specialization**：中国HS85占比约31.36%、RCA 2.140；HS95占比约2.60%、RCA 4.118。较大的出口份额不必对应较高的RCA。选中商品以背景、粗体标签与透明度突出，原排序和数值保持不变。
3. **Check change**：固定中墨，比较HS87的2010和2023年。中国占比从约2.08%升至5.40%，2023 RCA仍低于1；不是连续趋势或因果检验，也不声称2010年收入匹配。

## 范围与口径
- 候选固定为USA、DEU、CHN、MEX、NLD、ITA。收入比较默认2023、1.25倍，可改1.5倍；同年GDP/人位于锚点/factor至锚点×factor。相似仅相对锚点，不保证组内任意两国互相相似。
- 仅剩锚点时提示无可比伙伴，不自动放宽。1995–2023允许收入匹配；2024仅允许手动贸易比较，不借用2023收入。
- 商品份额分母为该国全部商品，RCA参照同年全球全部BACI出口实体；六国和Top-N选择不改变分母。
- BACI HS92 V202601，千当期美元；CHELEM GDP-CAP V202502，美元/人。缺失不补零；显示未知单元与数据覆盖。
- 默认商品行固定为2023中墨各自Top5并集加HS85、HS95、HS87，在三个引导步骤中保持可比。
- 控件仅影响M4。自定义条件后结论重新计算；CSV包含当前条件、来源、单位与参考范围。

## M5接入
见 [M4_M5_handoff.md](M4_M5_handoff.md)。现有 `M4-comparison.data` 与 `M4-inspect.value` 接口保持不变，无需等待公共数据重建。

## 检查
`python -m unittest discover -s tests -v`。覆盖全球分母、30年总额对账、缺失/重复/零值、收入匹配、六国范围、旧状态过滤、商品高亮、真实Dash回调、CSV及M5所需状态。

GDP历史窗口依据保留在 `data/reference/m4_income_policy.json`。原始数据核对记录见 `docs/M4_source_audit.json`；需要重新核对时运行 `python scripts/verify_m4_sources.py --source-root ../data`。本轮未更换输入数据或计算公式。
