# 部署手册 — 非油品需求预测 POC(单文件静态页)

> 本手册自包含,按顺序执行即可。执行者是部署 agent,无需了解项目开发历史。
> 目标:把 POC 演示页部署到霖哥的阿里云 ECS,公网访问 `http://works.kindora.top/noneoil/`。

## 0. 项目与产物

| 项 | 说明 |
|---|---|
| 产物 | `原型_前端功能总览_v0.5.html` — **单文件自包含静态页**(数据已内嵌,图表库走 CDN),无后端、无构建、无依赖文件 |
| 部署形态 | nginx 静态站子路径 `/noneoil/` |
| 大小 | 约 278 KB |
| 注意 | 本地文件名含中文,上传时统一改名 `index.html` |

**⛔ 安全红线(必读):**
- **`llm_key.js` 绝对不能上传**。它是本地百炼 API key,若放到公网服务器,任何人都能用它消耗额度。页面 HTML 本身不含任何密钥(已验证),公网部署是安全的。
- 服务器版页面的 AI 对话功能默认显示"AI 服务未连接",访问者可点浮窗右上按钮配置自己的 key(存在访问者自己的浏览器里)——这是设计好的行为,不是故障,**不要"修复"它**。
- 本仓库根目录的 `llm_key.js` 与 `scripts/llm_config.json` 已在 .gitignore,若 clone 仓库部署,它们本来就不在;若从本机目录直接部署,见第 2 步的明确排除。

## 1. 服务器信息

| 项 | 值 |
|---|---|
| 服务器 | 阿里云 ECS,Ubuntu 24.04,`39.96.202.119` = `works.kindora.top` |
| 登录 | `root`,端口 22,私钥 `D:/OneDrive/AICoding/Key/aliyun/key.pem` |
| Web 架构 | 80 端口 nginx,静态站放 `/var/www/<项目名>/`,配置文件 `/etc/nginx/sites-enabled/portfolio` |
| 已有站点 | `/`(落地页) `/gas-ops/` `/kada-puzzle/` `/forest/` `/europe-population/` `/gas-station-inspection/` `/sql-crud/` + 8000 端口 LUMEN — **部署前确认 `/noneoil/` 不冲突** |

## 2. 第 0 步:判断网络环境(必做)

企业内网时 SSH 直连 22 端口会被防火墙拦(表现为 connect timeout,**不是服务器挂了**)。先探测:

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 4 -x http://10.22.98.21:8080 http://www.baidu.com
# 返回 200 且极快(<0.1s) → 在企业内网,SSH 必须加代理隧道
# 超时/失败 → 直连即可(家庭网络/手机热点通常直连)
```

内网时所有 ssh/scp 命令加: `-o "ProxyCommand connect -H 10.22.98.21:8080 %h %p"`
(`connect` 在 Git Bash `/mingw64/bin/connect` 自带)

## 3. 部署步骤(四步)

以下命令中 `<代理参数>` = 内网时的 `-o "ProxyCommand connect -H 10.22.98.21:8080 %h %p"`,非内网为空。

```bash
# ① 上传(在项目根目录 "D:/AICoding/11 非油品需求预测" 执行;只传这一个文件)
scp <代理参数> -i "D:/OneDrive/AICoding/Key/aliyun/key.pem" \
  "原型_前端功能总览_v0.5.html" root@39.96.202.119:/tmp/noneoil.html

# ② 服务器落位(改名 index.html;若重复部署,先备份旧的)
ssh <代理参数> -i "D:/OneDrive/AICoding/Key/aliyun/key.pem" root@39.96.202.119 '
  mkdir -p /var/www/noneoil &&
  [ -f /var/www/noneoil/index.html ] && cp /var/www/noneoil/index.html /var/www/noneoil/index.html.bak;
  mv /tmp/noneoil.html /var/www/noneoil/index.html &&
  chmod 644 /var/www/noneoil/index.html &&
  ls -la /var/www/noneoil/'

# ③ nginx 加子路径块
#    编辑 /etc/nginx/sites-enabled/portfolio,在"后续新项目"注释前插入:
```

```nginx
location /noneoil/ {
    alias /var/www/noneoil/;
    index index.html;
    try_files $uri $uri/ =404;
    add_header Cache-Control "no-cache";   # HTML 不缓存,改版即时生效
}
```

```bash
# ④ 校验并重载(顺序不能反)
ssh <代理参数> -i "D:/OneDrive/AICoding/Key/aliyun/key.pem" root@39.96.202.119 '
  nginx -t && systemctl reload nginx && echo RELOAD_OK'
```

## 4. 验证(部署后必做)

```bash
# ① 状态码(非内网)
curl -s -o /dev/null -w "%{http_code}" "http://works.kindora.top/noneoil/"
# 期望 200;内网时加 -x http://10.22.98.21:8080

# ② 内容抽查(确认是本页面且数据已内嵌)
curl -s "http://works.kindora.top/noneoil/" | grep -o "非油选品\|预测复盘\|门店总览" | sort -u
# 期望输出包含三者

# ③ 安全检查(确认无密钥泄漏)
curl -s "http://works.kindora.top/noneoil/" | grep -c "sk-"
# 期望 0;若非 0,立即删除 /var/www/noneoil/index.html 并检查部署源文件

# ④ 浏览器人工检查(可选)
# 打开 http://works.kindora.top/noneoil/,确认:顶栏 tab 可切换、决策台建议表有数据、
# 预测复盘页 KPI 显示(MAPE 5.4%/覆盖率 94.1%)、趋势图正常渲染
```

## 5. 回滚

```bash
ssh <代理参数> -i "D:/OneDrive/AICoding/Key/aliyun/key.pem" root@39.96.202.119 '
  [ -f /var/www/noneoil/index.html.bak ] && mv /var/www/noneoil/index.html.bak /var/www/noneoil/index.html && echo ROLLBACK_OK'
```

## 6. 页面行为说明(验收对照)

| 现象 | 是否正常 |
|---|---|
| 对话浮窗右上显示橙色"AI 服务未连接" | ✅ 正常(公网版不带 key,访问者可自行配置) |
| 对话提问后得到"系统内置回答" | ✅ 正常(未配置 key 时的回退) |
| 决策台 KPI 注明"库存为演示假设" | ✅ 正常(数据集无库存信息,诚实标注) |
| 页面标注"POC 调用外部 LLM·真实系统替换昆仑大模型" | ✅ 正常(交付红线要求,勿删) |
| ECharts 图表不显示 | ❌ 异常(检查访问端网络到 cdn.jsdelivr.net 的可达性) |

## 7. 常见坑

- **SSH 连接超时** → 先做第 2 步网络判断,内网必须走代理隧道
- **中文文件名** → scp 时路径加双引号;上传后统一叫 index.html,避免 URL 转义问题
- **nginx 配置改错** → `nginx -t` 不过就别 reload,恢复配置文件再试
- **更新版本** → 重复第 3 步①②即可(②会自动备份旧版);nginx 配置不用动
- **URL hash 直达** → 页面支持 `#stores` / `#cat` / `#events` / `#oil` / `#bt` 直达各 tab,可用于演示链接
