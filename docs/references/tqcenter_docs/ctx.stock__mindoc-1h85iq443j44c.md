# exec_to_tdx 调用客户端功能

> **Source**: https://help.tdx.com.cn/quant/docs/markdown/ctx.stock.md/mindoc-1h85iq443j44c.html
> **Path**: `/docs/markdown/ctx.stock.md/mindoc-1h85iq443j44c.html`

#  调用客户端功能

###  客户端根据入参执行指定功能
```
`    def exec_to_tdx(url:str = ''):
`
```
1

###  输入参数
| 参数  | 是否必选  | 参数类型  | 参数说明
| url  | Y  | str  | 功能调用串或网址
- 若是功能串，请以 http://www.treeid 开头

###  接口使用
```
`from tqcenter import tq
tq.initialize(__file__)

exec_res1 = tq.exec_to_tdx(url='http://www.treeid/MAINQH')

exec_res2 = tq.exec_to_tdx(url='http://www.treeid/dlghttp://www.tdx.com.cn')
print(exec_res2)
`
```
1
2
3
4
5
6
7

###  数据样本
```
`{'ErrorId': '0', 'Msg': 'http://www.treeid/dlghttp://www.tdx.com.cn', 'run_id': '1'}
`
```
1


←

打印数据到客户端print_to_tdx

获取K线数据get_market_data

→
