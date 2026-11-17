"""本地业务页面交互。

演练门户默认行为稳定；仅在详情 URL 携带故障注入查询参数时模拟客服投诉中的
三类页面问题，供采集器验证“保留已确认范围、明确未知”的恢复逻辑：

- fault=reset：选定票根类别后页面把类别重置回首项（分类筛选被页面重置）。
- fault=cross-city：详情页把当前城市静默改写为另一城市（详情跳到其他城市）。
- fault=transient：领券预览首次返回短暂报错，稍后可恢复（预览短暂报错）。

故障参数只在环回演练页面生效，不调用任何外部系统。
"""

def detail_fragment(item):
    return "<select id=\"city\"><option>北京</option><option>江苏</option></select><select id=\"ticket\"><option>网球票</option><option>演出票</option></select><button id=\"voucher-preview\">核对资格</button><output id=\"voucher\"></output><output id=\"merchant\">书店</output><script>let city=document.querySelector('#city'),ticket=document.querySelector('#ticket'),voucher=document.querySelector('#voucher');let merchant=document.querySelector('#merchant');city.onchange=()=>{ticket.value='网球票';voucher.textContent='';merchant.textContent=city.value==='北京'?'书店':'咖啡馆'};ticket.onchange=()=>voucher.textContent='';document.querySelector('#voucher-preview').onclick=()=>voucher.textContent=city.value+' / '+ticket.value+' / '+(city.value==='江苏'&&ticket.value==='演出票'?'名额待核':'可领取');</script>"

def source_extension(item):
    return f"""<output id="merchant-detail" data-entry="{item['id']}"></output><button id="merchant-open">查看商户说明</button><output id="voucher-scope"></output><script>(()=>{{
let detail=document.querySelector('#merchant-detail'),scope=document.querySelector('#voucher-scope'),city=document.querySelector('#city'),ticket=document.querySelector('#ticket');
const reset=()=>{{detail.textContent='';scope.textContent='';}};city.addEventListener('change',reset);ticket.addEventListener('change',reset);
document.querySelector('#merchant-open').addEventListener('click',()=>{{let selectedCity=city.value,selectedTicket=ticket.value;detail.textContent='商户说明读取中';setTimeout(()=>{{detail.textContent=selectedCity+' / '+document.querySelector('#merchant').textContent+'：'+(selectedTicket==='网球票'?'可凭网球票核对':'演出票资格待核');}},60)}});
document.querySelector('#voucher-preview').addEventListener('click',()=>{{scope.textContent=city.value+' / '+ticket.value+' / '+detail.dataset.entry+'：'+(detail.textContent.includes('可凭')?'条款已见':'资格待核');}});
}})();</script>"""

def fault_injection(fault):
    """返回故障注入脚本；fault 为空时返回空字符串，页面行为与基线完全一致。"""
    if not fault:
        return ''
    if fault == 'reset':
        # 选择非首项票根类别后，页面在下一拍把类别重置回首项并清空已读结论。
        return ("<script>(()=>{let city=document.querySelector('#city'),ticket=document.querySelector('#ticket'),"
                "voucher=document.querySelector('#voucher'),detail=document.querySelector('#merchant-detail'),"
                "scope=document.querySelector('#voucher-scope');"
                "ticket.addEventListener('change',()=>{setTimeout(()=>{"
                "if(ticket.value!==ticket.options[0].value){ticket.value=ticket.options[0].value;"
                "voucher.textContent='';if(detail){detail.textContent='';}if(scope){scope.textContent='';}}},30);});"
                "})();</script>")
    if fault == 'cross-city':
        # 城市选择被静默改写：页面展示与读取到的城市都不是客服选定的城市。
        return ("<script>(()=>{let city=document.querySelector('#city'),merchant=document.querySelector('#merchant');"
                "city.addEventListener('change',()=>{setTimeout(()=>{let other=Array.from(city.options)"
                ".find(o=>o.value!==city.value);if(other){city.value=other.value;"
                "merchant.textContent=city.value==='北京'?'书店':'咖啡馆';}},30);});"
                "})();</script>")
    if fault == 'transient':
        # 每个（城市, 票根类别）坐标的首次预览短暂报错，同坐标再次核对时恢复。
        return ("<script>(()=>{let city=document.querySelector('#city'),ticket=document.querySelector('#ticket'),"
                "voucher=document.querySelector('#voucher');let failedKey=null;"
                "document.querySelector('#voucher-preview').addEventListener('click',e=>{"
                "e.stopImmediatePropagation();let key=city.value+' / '+ticket.value;"
                "if(failedKey!==key){failedKey=key;"
                "voucher.textContent=key+' / 系统繁忙请稍后重试';}"
                "else{voucher.textContent=key+' / '+"
                "(city.value==='江苏'&&ticket.value==='演出票'?'名额待核':'可领取');}},true);"
                "})();</script>")
    return ''
