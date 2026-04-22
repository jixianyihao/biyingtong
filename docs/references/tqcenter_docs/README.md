# tqcenter 官方文档本地镜像

从 https://help.tdx.com.cn/quant/ 爬取的 TdxQuant 官方 API 文档镜像，方便在离线/无网络环境下查询和 grep。

**更新时间**: 2026-04-22
**源码路径**: `scripts/setup/crawl_tdx_docs.py`（重新跑即可刷新）
**原始清单**: `../tqcenter-docs-manifest.json`（79 个页面）
**本目录**: 71 个实际有内容的 API 文档页（7 个分类首页只做索引，无正文）

## 快速索引

### 入门与环境

| 功能 | 文件 |
|------|------|
| TdxQuant 简介 | [mindoc-1cfsjkbf8f3is.md](mindoc-1cfsjkbf8f3is.md) |
| 版本更新说明 | [mindoc-1cfsjkbf8f3is__TdxQuantVersion.md](mindoc-1cfsjkbf8f3is__TdxQuantVersion.md) |
| 安装 Python 及 VSCode | [mindoc-1cfsjkbf8f3is__mindoc-1d00970eq1rtc.md](mindoc-1cfsjkbf8f3is__mindoc-1d00970eq1rtc.md) |
| 安装通达信终端 | [mindoc-1cfsjkbf8f3is__mindoc-1d00kk3jsibbc.md](mindoc-1cfsjkbf8f3is__mindoc-1d00kk3jsibbc.md) |
| 快速开始第一个策略 | [mindoc-1cfsjkbf8f3is__mindoc-1cv7o3nje2gu8.md](mindoc-1cfsjkbf8f3is__mindoc-1cv7o3nje2gu8.md) |
| 什么是量化交易 | [mindoc-1h12t4q6fg29o.md](mindoc-1h12t4q6fg29o.md) |
| 常见问题 | [mindoc-tdxpy.md](mindoc-tdxpy.md) |

### 通用函数 (ctx.stock)

| API | 文件 |
|-----|------|
| `initialize` 初始化 | [ctx.stock__mindoc-1cv85e8u9nb0c.md](ctx.stock__mindoc-1cv85e8u9nb0c.md) |
| `refresh_cache` 刷新行情缓存 | [ctx.stock__mindoc-1h10f9145us1g.md](ctx.stock__mindoc-1h10f9145us1g.md) |
| `refresh_kline` 刷新 K 线缓存 | [ctx.stock__mindoc-1h10fh9m6recg.md](ctx.stock__mindoc-1h10fh9m6recg.md) |
| `download_file` 下载数据文件 | [ctx.stock__mindoc-1h10pqrdlj71o.md](ctx.stock__mindoc-1h10pqrdlj71o.md) |
| `get_trading_dates` 交易日列表 | [ctx.stock__mindoc-1h10q7i3702rk.md](ctx.stock__mindoc-1h10q7i3702rk.md) |
| `send_message` 发消息到客户端 | [ctx.stock__mindoc-1h10rkbndkb0k.md](ctx.stock__mindoc-1h10rkbndkb0k.md) |
| `send_file` 发文件到客户端 | [ctx.stock__mindoc-1h10u17ue9464.md](ctx.stock__mindoc-1h10u17ue9464.md) |
| `send_warn` 发预警信号 | [ctx.stock__mindoc-1h10u5k9qjh8o.md](ctx.stock__mindoc-1h10u5k9qjh8o.md) |
| `send_bt_data` 发回测数据 | [ctx.stock__mindoc-1h10vc2pot87c.md](ctx.stock__mindoc-1h10vc2pot87c.md) |
| `subscribe_hq` 订阅行情 | [ctx.stock__mindoc-1h1104d65vr68.md](ctx.stock__mindoc-1h1104d65vr68.md) |
| `unsubscribe_hq` 取消订阅 | [ctx.stock__mindoc-1h112vh7jtsms.md](ctx.stock__mindoc-1h112vh7jtsms.md) |
| `get_subscribe_hq_stock_list` 订阅列表 | [ctx.stock__mindoc-1h1137r4k2mas.md](ctx.stock__mindoc-1h1137r4k2mas.md) |
| `print_to_tdx` 导出数据到客户端 | [ctx.stock__mindoc-1h62l8kg2k4jc.md](ctx.stock__mindoc-1h62l8kg2k4jc.md) |
| `exec_to_tdx` 调用客户端功能 | [ctx.stock__mindoc-1h85iq443j44c.md](ctx.stock__mindoc-1h85iq443j44c.md) |

### 行情类信息

| API | 文件 |
|-----|------|
| `get_market_data` K 线 | [mindoc-1ctuhthaq5qmg__mindoc-1h10g60jt68sc.md](mindoc-1ctuhthaq5qmg__mindoc-1h10g60jt68sc.md) |
| `get_divid_factors` 分红配送 | [mindoc-1ctuhthaq5qmg__mindoc-1h10hsiat36k4.md](mindoc-1ctuhthaq5qmg__mindoc-1h10hsiat36k4.md) |
| `get_market_snapshot` 快照 | [mindoc-1ctuhthaq5qmg__mindoc-1h10iig4pb6e0.md](mindoc-1ctuhthaq5qmg__mindoc-1h10iig4pb6e0.md) |
| `get_stock_info` 证券基本信息 | [mindoc-1ctuhthaq5qmg__mindoc-1h10jj7r7jol4.md](mindoc-1ctuhthaq5qmg__mindoc-1h10jj7r7jol4.md) |
| `get_ipo_info` 新股申购 | [mindoc-1ctuhthaq5qmg__mindoc-1h137jr3khrqo.md](mindoc-1ctuhthaq5qmg__mindoc-1h137jr3khrqo.md) |
| `get_more_info` 股票更多信息 | [mindoc-1ctuhthaq5qmg__mindoc-1h3rtq1hij0ac.md](mindoc-1ctuhthaq5qmg__mindoc-1h3rtq1hij0ac.md) |
| `get_gb_info` 每天股本数据 | [mindoc-1ctuhthaq5qmg__mindoc-1h3ru0b1tssrc.md](mindoc-1ctuhthaq5qmg__mindoc-1h3ru0b1tssrc.md) |
| `get_relation` 股票所属板块 | [mindoc-1ctuhthaq5qmg__mindoc-1h84ec4p26qus.md](mindoc-1ctuhthaq5qmg__mindoc-1h84ec4p26qus.md) |
| 行情类信息总览 | [mindoc-1ctuhthaq5qmg.md](mindoc-1ctuhthaq5qmg.md) |

### 财务类数据 (TdxQuant.md 组)

| API | 文件 |
|-----|------|
| ⭐ `get_financial_data` 专业财务 | [TdxQuant__mindoc-1h10m001ic888.md](TdxQuant__mindoc-1h10m001ic888.md) |
| `get_financial_data_by_date` 按日期 | [TdxQuant__mindoc-1h10mdt617qss.md](TdxQuant__mindoc-1h10mdt617qss.md) |
| `get_gpjy_value` 股票交易数据 | [TdxQuant__mindoc-1h10muc82r55k.md](TdxQuant__mindoc-1h10muc82r55k.md) |
| `get_gpjy_value_by_date` 按日期 | [TdxQuant__mindoc-1h2pci5gh6h7k.md](TdxQuant__mindoc-1h2pci5gh6h7k.md) |
| `get_bkjy_value` 板块交易数据 | [TdxQuant__mindoc-1h10p0ncmp5mc.md](TdxQuant__mindoc-1h10p0ncmp5mc.md) |
| `get_bkjy_value_by_date` 按日期 | [TdxQuant__mindoc-1h10p3d31736g.md](TdxQuant__mindoc-1h10p3d31736g.md) |
| `get_scjy_value` 市场交易数据 | [TdxQuant__mindoc-1h10p8op6ia9g.md](TdxQuant__mindoc-1h10p8op6ia9g.md) |
| `get_scjy_value_by_date` 按日期 | [TdxQuant__mindoc-1h10pe678ta04.md](TdxQuant__mindoc-1h10pe678ta04.md) |
| `get_gp_one_data` 股票单个数据 | [TdxQuant__mindoc-1h10pk3rsg044.md](TdxQuant__mindoc-1h10pk3rsg044.md) |

### 板块 / 自选股 / ETF / 可转债

| API | 文件 |
|-----|------|
| `get_stock_list` 系统分类成分股 | [mindoc-1ctuhttn72svo__mindoc-1h10qo3uj48fg.md](mindoc-1ctuhttn72svo__mindoc-1h10qo3uj48fg.md) |
| `get_sector_list` A股板块列表 | [mindoc-1ctuhttn72svo__mindoc-1h10r5907noko.md](mindoc-1ctuhttn72svo__mindoc-1h10r5907noko.md) |
| `get_stock_list_in_sector` 板块成分股 | [mindoc-1ctuhttn72svo__mindoc-1h10r92mchgug.md](mindoc-1ctuhttn72svo__mindoc-1h10r92mchgug.md) |
| `create_sector` 创建自定义板块 | [mindoc-1h139a4ckchkk__mindoc-1h10rrkuj1drs.md](mindoc-1h139a4ckchkk__mindoc-1h10rrkuj1drs.md) |
| `delete_sector` 删除板块 | [mindoc-1h139a4ckchkk__mindoc-1h10s391lng6s.md](mindoc-1h139a4ckchkk__mindoc-1h10s391lng6s.md) |
| `rename_sector` 重命名板块 | [mindoc-1h139a4ckchkk__mindoc-1h10s7n863d50.md](mindoc-1h139a4ckchkk__mindoc-1h10s7n863d50.md) |
| `clear_sector` 清空板块 | [mindoc-1h139a4ckchkk__mindoc-1h10sbcnl1c94.md](mindoc-1h139a4ckchkk__mindoc-1h10sbcnl1c94.md) |
| `send_user_block` 添加自定义板块成分 | [mindoc-1h139a4ckchkk__mindoc-1h10sec960u0c.md](mindoc-1h139a4ckchkk__mindoc-1h10sec960u0c.md) |
| `get_user_sector` 自定义板块列表 | [mindoc-1h139a4ckchkk__mindoc-1h1hauh9inaac.md](mindoc-1h139a4ckchkk__mindoc-1h1hauh9inaac.md) |
| `get_kzz_info` 可转债 | [mindoc-1h13a594nhvb4__mindoc-1h137euvcjn98.md](mindoc-1h13a594nhvb4__mindoc-1h137euvcjn98.md) |
| `get_trackzs_etf_info` ETF 跟踪指数 | [mindoc-1h13a594nhvb4__mindoc-1h6hknp6pjppc.md](mindoc-1h13a594nhvb4__mindoc-1h6hknp6pjppc.md) |

### ⭐ 交易函数（P5 实盘部署用）

| API | 文件 |
|-----|------|
| `stock_account` 账户句柄 | [mindoc-1h7k4iqb1grk4__mindoc-1h7k4k5tk6q64.md](mindoc-1h7k4iqb1grk4__mindoc-1h7k4k5tk6q64.md) |
| `query_stock_orders` 查委托 | [mindoc-1h7k4iqb1grk4__mindoc-1h7k4rp481gt4.md](mindoc-1h7k4iqb1grk4__mindoc-1h7k4rp481gt4.md) |
| `query_stock_positions` 查持仓 | [mindoc-1h7k4iqb1grk4__mindoc-1h7k5ar9kc508.md](mindoc-1h7k4iqb1grk4__mindoc-1h7k5ar9kc508.md) |
| `order_stock` 下单 | [mindoc-1h7k4iqb1grk4__mindoc-1h7k5j4drr928.md](mindoc-1h7k4iqb1grk4__mindoc-1h7k5j4drr928.md) |
| `cancel_order_stock` 撤单 | [mindoc-1h7k4iqb1grk4__mindoc-1h84elp5atr6o.md](mindoc-1h7k4iqb1grk4__mindoc-1h84elp5atr6o.md) |
| `query_stock_asset` 查资产 | [mindoc-1h7k4iqb1grk4__mindoc-1h84fvcjulrnc.md](mindoc-1h7k4iqb1grk4__mindoc-1h84fvcjulrnc.md) |

### ⭐ 常量枚举 (`tqconst`)

**必读**：市场代码、周期、复权类型、order_type、price_type、委托状态全枚举
- [Dict.md](Dict.md)

### 通达信公式（项目中不使用）

| API | 文件 |
|-----|------|
| `formula_set_data_info` | [mindoc-1h3hrvkp4sc0g__mindoc-1h3hs08rn02uc.md](mindoc-1h3hrvkp4sc0g__mindoc-1h3hs08rn02uc.md) |
| `formula_set_data` | [mindoc-1h3hrvkp4sc0g__mindoc-1h3hsvcct5sdc.md](mindoc-1h3hrvkp4sc0g__mindoc-1h3hsvcct5sdc.md) |
| `formula_format_data` | [mindoc-1h3hrvkp4sc0g__mindoc-1h3hte6obagc0.md](mindoc-1h3hrvkp4sc0g__mindoc-1h3hte6obagc0.md) |
| `formula_get_data` | [mindoc-1h3hrvkp4sc0g__mindoc-1h3httgemshno.md](mindoc-1h3hrvkp4sc0g__mindoc-1h3httgemshno.md) |
| `formula_zb/xg/exp` | [mindoc-1h3hrvkp4sc0g__mindoc-1h3huq37005ro.md](mindoc-1h3hrvkp4sc0g__mindoc-1h3huq37005ro.md) |
| `formula_process_mul_*` | [mindoc-1h3hrvkp4sc0g__mindoc-1h4ad5lisvdfg.md](mindoc-1h3hrvkp4sc0g__mindoc-1h4ad5lisvdfg.md) |

### 场景化示例

| 示例 | 文件 |
|------|------|
| 执行选股策略并加入客户端自定义板块 | [mindoc-1h1525ci3mnkc__mindoc-1h15262vnafcc.md](mindoc-1h1525ci3mnkc__mindoc-1h15262vnafcc.md) |
| 订阅行情涨幅突破实时预警 | [mindoc-1h1525ci3mnkc__mindoc-1h1526nmnk5n4.md](mindoc-1h1525ci3mnkc__mindoc-1h1526nmnk5n4.md) |
| 计算调仓信号并快速买卖 | [mindoc-1h1525ci3mnkc__mindoc-1h1ep1rl20jv8.md](mindoc-1h1525ci3mnkc__mindoc-1h1ep1rl20jv8.md) |
| VBT 简单回测并输出图形 | [mindoc-1h1525ci3mnkc__mindoc-1h62qo3mceppc.md](mindoc-1h1525ci3mnkc__mindoc-1h62qo3mceppc.md) |

### 公众号文章

| 文章 | 文件 |
|------|------|
| 通达信TQ策略介绍和应用示例 | [gzh0122inweixinwenz.md](gzh0122inweixinwenz.md) |
| 通达信TQ策略介绍和应用示例（2026-01-22） | [gzh0122inweixinwenz__gzh20260122wzlz.md](gzh0122inweixinwenz__gzh20260122wzlz.md) |
| 打通通达信量化任督二脉：公式与Python双向数据互通闭环 | [gzh0122inweixinwenz__gzh20260302wzlz.md](gzh0122inweixinwenz__gzh20260302wzlz.md) |

## grep 提示

```bash
# 查找某 API 的所有提及
grep -r "get_financial_data" docs/references/tqcenter_docs/

# 查找某字段（如 FN197）的定义
grep -n "FN197" docs/references/tqcenter_docs/TdxQuant__mindoc-1h10m001ic888.md

# 查找某常量（如 STOCK_BUY）
grep -n "STOCK_BUY" docs/references/tqcenter_docs/Dict.md
```

## 失败页面（仅索引页，正文为空）

这些是 VuePress 分类页，路径存在但 `<div class="theme-default-content">` 为空。爬虫如实标为 FAIL，保持行为诚实：
- `TdxQuant.md/` — 财务类数据总览
- `mindoc-1ctuhttn72svo/` — 分类/板块成份股总览
- `mindoc-1h139a4ckchkk/` — 自选股/自定义板块总览
- `mindoc-1h13a594nhvb4/` — ETF/可转债/期货总览
- `mindoc-1h3hrvkp4sc0g/` — 调用通达信公式总览
- `mindoc-1h7k4iqb1grk4/` — 交易函数总览
- `mindoc-1h1525ci3mnkc/` — 场景化示例总览

具体子页均已成功抓取。
