# get_subscribe_hq_stock_list 获得订阅列表

> **Source**: https://help.tdx.com.cn/quant/docs/markdown/ctx.stock.md/mindoc-1h1137r4k2mas.html
> **Path**: `/docs/markdown/ctx.stock.md/mindoc-1h1137r4k2mas.html`

#  获得订阅列表get_subscribe_hq_stock_list

###  获得当前策略订阅的股票列表
```
`get_subscribe_hq_stock_list():
`
```
1

###  接口使用
```
`from tqcenter import tq

tq.initialize(__file__)

sub_list = tq.get_subscribe_hq_stock_list()
print(sub_list)
`
```
1
2
3
4
5
6

###  数据样本
```
`['600519.SH']
`
```
1


←

取消订阅更新unsubscribe_hq

刷新行情缓存refresh_cache

→
