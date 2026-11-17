"""本地业务页面交互。"""

def detail_fragment(item):
    return "<select id=\"city\"><option>北京</option><option>江苏</option></select><select id=\"ticket\"><option>网球票</option><option>演出票</option></select><button id=\"voucher-preview\">核对资格</button><output id=\"voucher\"></output><output id=\"merchant\">书店</output><script>let city=document.querySelector('#city'),ticket=document.querySelector('#ticket'),voucher=document.querySelector('#voucher');let merchant=document.querySelector('#merchant');city.onchange=()=>{ticket.value='网球票';voucher.textContent='';merchant.textContent=city.value==='北京'?'书店':'咖啡馆'};ticket.onchange=()=>voucher.textContent='';document.querySelector('#voucher-preview').onclick=()=>voucher.textContent=city.value+' / '+ticket.value+' / '+(city.value==='江苏'&&ticket.value==='演出票'?'名额待核':'可领取');</script>"

def source_extension(item):
    return f"""<output id="merchant-detail" data-entry="{item['id']}"></output><button id="merchant-open">查看商户说明</button><output id="voucher-scope"></output><script>(()=>{{
let detail=document.querySelector('#merchant-detail'),scope=document.querySelector('#voucher-scope'),city=document.querySelector('#city'),ticket=document.querySelector('#ticket');
const reset=()=>{{detail.textContent='';scope.textContent='';}};city.addEventListener('change',reset);ticket.addEventListener('change',reset);
document.querySelector('#merchant-open').addEventListener('click',()=>{{let selectedCity=city.value,selectedTicket=ticket.value;detail.textContent='商户说明读取中';setTimeout(()=>{{detail.textContent=selectedCity+' / '+document.querySelector('#merchant').textContent+'：'+(selectedTicket==='网球票'?'可凭网球票核对':'演出票资格待核');}},60)}});
document.querySelector('#voucher-preview').addEventListener('click',()=>{{scope.textContent=city.value+' / '+ticket.value+' / '+detail.dataset.entry+'：'+(detail.textContent.includes('可凭')?'条款已见':'资格待核');}});
}})();</script>"""
