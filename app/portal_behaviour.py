"""本地业务页面交互。"""

def detail_fragment(item):
    return '<select id="city"><option>北京</option><option>江苏</option></select><select id="ticket"><option>网球票</option><option>演出票</option></select><button id="voucher-preview">核对资格</button><output id="voucher"></output><script>document.querySelector(\'#voucher-preview\').onclick=()=>document.querySelector(\'#voucher\').textContent=document.querySelector(\'#city\').value+\' / \'+document.querySelector(\'#ticket\').value;document.querySelector(\'#city\').onchange=()=>document.querySelector(\'#ticket\').value=\'网球票\';</script>'
