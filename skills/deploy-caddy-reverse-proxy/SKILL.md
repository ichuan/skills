---
name: deploy-caddy-reverse-proxy
description: "在远程服务器上部署 Caddy 反向代理，自动配置 SSL 证书和 systemd 服务。适用场景：(1) 为本地 web 服务配置反向代理，(2) 自动获取和管理 Let's Encrypt SSL 证书，(3) 配置 systemd 服务实现开机自启，(4) 支持 HTTP/WebSocket 流量代理。触发关键词：'deploy caddy'，'setup reverse proxy'，'配置 caddy 反向代理'，'caddy ssl'。"
---

# Deploy Caddy Reverse Proxy

## Overview

在远程服务器上自动部署 Caddy 反向代理服务器，支持：

- **自动 SSL 证书管理**：使用 Let's Encrypt 自动获取和续期证书
- **反向代理配置**：将域名流量代理到本地服务（HTTP/WebSocket）
- **Systemd 集成**：配置服务自动启动和崩溃重启
- **智能环境适配**：自动检测系统环境并选择最佳配置方案

## Prerequisites

执行部署前确认：

1. **服务器访问**：
   - 已配置 SSH 访问（支持 SSH config 别名）
   - 拥有 sudo 权限
   - 服务器能访问互联网（下载 Caddy 和申请证书）

2. **DNS 配置**：
   - 域名已指向服务器 IP（A 记录或 CNAME）
   - DNS 生效后才能申请 SSL 证书

3. **本地服务**：
   - Web 服务已在服务器上运行
   - 监听在 127.0.0.1 或 localhost（确保端口号）

## Workflow

### 1. 参数收集

使用 `AskUserQuestion` 工具交互式收集部署参数：

```markdown
**必需参数**：
- SSH 主机别名或地址（如 `dev` 或 `user@example.com`）
- 域名（如 `app.example.com`）
- 后端服务端口（如 `8000`、`3000`）

**可选参数**：
- 是否需要静态文件服务（如果前端已独立打包）
- 静态文件路径（如 `/var/www/app/dist`）
- 路由规则（如 `/api` 代理到端口 A，`/ui` 服务静态文件）
```

**示例问题**：

```markdown
question: "请提供服务器的 SSH 连接方式"
options:
  - label: "SSH config 别名（推荐）"
    description: "使用 ~/.ssh/config 中配置的主机别名，如 'dev'"
  - label: "完整 SSH 地址"
    description: "格式：user@hostname 或 user@ip"

question: "域名是什么？"
header: "Domain"

question: "后端服务监听的端口？"
header: "Backend Port"
```

### 2. 环境检测

连接到服务器后执行环境检查：

```bash
# 检查 Caddy 是否已安装
which caddy && caddy version

# 检查 CPU 架构（用于下载正确的二进制文件）
uname -m  # x86_64 → amd64, aarch64 → arm64

# 检查操作系统
cat /etc/os-release

# 检查可用用户（优先使用 www-data，不存在则创建 caddy 用户）
id www-data 2>/dev/null || id caddy 2>/dev/null

# 检查后端服务是否运行
sudo ss -tlnp | grep <backend_port>
```

**自适应策略**：
- 如果 Caddy 已安装且版本 >= 2.0，询问是否重新安装或使用现有版本
- 如果 `www-data` 用户存在，使用它；否则创建 `caddy` 系统用户
- 如果后端服务未运行，警告用户并询问是否继续

### 3. 安装 Caddy

如果 Caddy 未安装或需要更新：

```bash
# 下载 Caddy 二进制文件
cd /tmp
curl -L "https://caddyserver.com/api/download?os=linux&arch=<arch>" -o caddy
chmod +x caddy

# 安装到系统路径
sudo mv caddy /usr/bin/caddy

# 验证安装
/usr/bin/caddy version
```

**架构映射**：
- `x86_64` → `amd64`
- `aarch64` → `arm64`
- `armv7l` → `armv7`

### 4. 创建必要目录和用户

```bash
# 如果使用 www-data 用户（Debian/Ubuntu 默认）
sudo mkdir -p /etc/caddy /var/lib/caddy
sudo chown -R www-data:www-data /etc/caddy /var/lib/caddy

# 如果需要创建 caddy 用户（CentOS/RHEL/其他）
sudo groupadd --system caddy
sudo useradd --system --gid caddy \
  --create-home --home-dir /var/lib/caddy \
  --shell /sbin/nologin \
  --comment "Caddy web server" caddy
```

### 5. 生成配置文件

#### 5.1 Caddyfile

根据用户参数生成配置文件：

**场景 A：纯反向代理（最常见）**

```caddyfile
example.com {
    reverse_proxy http://127.0.0.1:8000

    log {
        output stdout
    }
}
```

**场景 B：静态文件 + API 代理**

```caddyfile
example.com {
    # 静态文件服务
    handle /ui/* {
        root * /var/www/app/dist
        try_files {path} /index.html
        file_server
    }

    # API 反向代理
    handle /api/* {
        reverse_proxy http://127.0.0.1:8000
    }

    log {
        output stdout
    }
}
```

**场景 C：多服务代理**

```caddyfile
example.com {
    # 主应用
    handle /app/* {
        reverse_proxy http://127.0.0.1:3000
    }

    # 后端 API
    handle /api/* {
        reverse_proxy http://127.0.0.1:8000
    }

    # WebSocket 服务
    handle /ws {
        reverse_proxy http://127.0.0.1:9000
    }

    # 默认路由
    handle {
        reverse_proxy http://127.0.0.1:3000
    }

    log {
        output stdout
    }
}
```

写入配置文件：

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null << 'EOF'
<生成的配置内容>
EOF

# 验证配置语法
sudo /usr/bin/caddy validate --config /etc/caddy/Caddyfile
```

#### 5.2 Systemd 服务文件

使用 `assets/caddy.service.template` 模板生成服务文件：

```bash
sudo tee /etc/systemd/system/caddy.service > /dev/null << 'EOF'
[Unit]
Description=Caddy
Documentation=https://caddyserver.com/docs/
After=network.target network-online.target
Requires=network-online.target

[Service]
Type=notify
User=www-data
Group=www-data
Environment=XDG_DATA_HOME=/var/lib/caddy
Environment=XDG_CONFIG_HOME=/var/lib/caddy
ExecStart=/usr/bin/caddy run --environ --config /etc/caddy/Caddyfile
ExecReload=/usr/bin/caddy reload --config /etc/caddy/Caddyfile --force
TimeoutStopSec=5s
LimitNOFILE=1048576
LimitNPROC=512
PrivateTmp=true
ProtectSystem=full
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF
```

**关键配置说明**：

- `Type=notify`：Caddy 支持 systemd 通知，确保证书加载完成后才标记为 active
- `AmbientCapabilities=CAP_NET_BIND_SERVICE`：允许非 root 用户绑定 80/443 端口
- `Environment=XDG_DATA_HOME=/var/lib/caddy`：证书存储路径，避免权限问题
- `LimitNOFILE=1048576`：高并发场景下的文件描述符限制

### 6. 启动服务

```bash
# 重载 systemd 配置
sudo systemctl daemon-reload

# 设置开机自启
sudo systemctl enable caddy

# 启动服务
sudo systemctl start caddy

# 等待 SSL 证书获取（首次启动需要 5-10 秒）
sleep 5

# 检查服务状态
sudo systemctl status caddy --no-pager
```

### 7. 验证部署

执行以下检查确保部署成功：

```bash
# 1. 检查 Caddy 监听端口
sudo ss -tlnp | grep caddy
# 预期输出：80, 443, 2019(管理端口)

# 2. 检查后端服务
sudo ss -tlnp | grep <backend_port>
# 确保后端服务正在运行

# 3. 查看证书获取日志
sudo journalctl -u caddy -n 30 --no-pager | grep -E 'certificate obtained|error'
# 预期输出：certificate obtained successfully

# 4. 测试 HTTPS 访问
curl -I https://<domain> -m 10
# 预期输出：HTTP/2 200
```

### 8. 生成部署报告

向用户展示部署结果：

```markdown
## ✅ Caddy 部署完成

### 部署配置
- **域名**: <domain>
- **后端服务**: 127.0.0.1:<port> ✅ 正在运行
- **SSL 证书**: Let's Encrypt（自动获取成功）
- **协议支持**: HTTP/2, HTTP/3, WebSocket

### 服务状态
- Caddy 版本: <version>
- 监听端口: 80 (HTTP → HTTPS), 443 (HTTPS), 2019 (管理)
- 运行用户: <user>
- 开机自启: 已启用

### 关键文件位置
- 配置文件: `/etc/caddy/Caddyfile`
- 服务文件: `/etc/systemd/system/caddy.service`
- 证书存储: `/var/lib/caddy/`
- 二进制文件: `/usr/bin/caddy`

### 常用命令
```bash
# 查看服务状态
sudo systemctl status caddy

# 查看实时日志
sudo journalctl -u caddy -f

# 重新加载配置（无中断）
sudo systemctl reload caddy

# 重启服务
sudo systemctl restart caddy

# 验证配置语法
sudo caddy validate --config /etc/caddy/Caddyfile
```

### 测试结果
✅ HTTPS 访问正常
✅ SSL 证书获取成功
✅ 反向代理工作正常

现在可以通过 `https://<domain>` 访问你的服务了！
```

## Troubleshooting

### 常见问题

#### 1. 证书获取失败

**错误**：`storage is probably misconfigured` 或 `permission denied`

**原因**：Caddy 无法写入证书存储目录

**解决方案**：

```bash
# 检查环境变量配置
sudo systemctl cat caddy | grep Environment
# 应包含：Environment=XDG_DATA_HOME=/var/lib/caddy

# 检查目录权限
ls -ld /var/lib/caddy
# 应为：drwxr-xr-x www-data www-data

# 修复权限
sudo chown -R www-data:www-data /var/lib/caddy
sudo systemctl restart caddy
```

#### 2. 端口绑定失败

**错误**：`bind: permission denied` 或 `address already in use`

**原因**：
- 无权限绑定 80/443 端口
- 端口已被其他服务占用

**解决方案**：

```bash
# 检查 capabilities
sudo systemctl cat caddy | grep AmbientCapabilities
# 应包含：AmbientCapabilities=CAP_NET_BIND_SERVICE

# 检查端口占用
sudo ss -tlnp | grep :443
# 如果被其他程序占用，停止该程序或修改 Caddyfile 使用其他端口

# 如果系统不支持 AmbientCapabilities，手动授权
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/caddy
```

#### 3. DNS 解析失败

**错误**：`no such host` 或 `DNS problem: NXDOMAIN`

**原因**：域名未正确指向服务器 IP

**解决方案**：

```bash
# 检查 DNS 记录
dig +short <domain>
# 应返回服务器公网 IP

# 检查服务器公网 IP
curl -4 ifconfig.me

# 如果 DNS 未生效，等待 TTL 过期（通常 5 分钟到 1 小时）
```

#### 4. 反向代理 502 错误

**错误**：访问域名返回 502 Bad Gateway

**原因**：后端服务未运行或监听地址错误

**解决方案**：

```bash
# 检查后端服务状态
sudo ss -tlnp | grep <backend_port>

# 测试本地访问
curl http://127.0.0.1:<backend_port>

# 检查 Caddy 日志
sudo journalctl -u caddy -f

# 如果后端服务监听在 0.0.0.0 而非 127.0.0.1，修改 Caddyfile
```

#### 5. WebSocket 连接失败

**错误**：WebSocket 握手失败或连接中断

**原因**：Caddy 2.x 默认支持 WebSocket，通常是后端问题

**解决方案**：

```bash
# 检查后端服务 WebSocket 端点
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: test" \
  http://127.0.0.1:<backend_port>/ws

# 如果需要特殊配置，在 Caddyfile 中添加：
handle /ws {
    reverse_proxy http://127.0.0.1:<port> {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

## Advanced Configuration

### 多域名配置

```caddyfile
app.example.com {
    reverse_proxy http://127.0.0.1:8000
}

api.example.com {
    reverse_proxy http://127.0.0.1:9000
}
```

### 自定义 SSL 证书邮箱

```caddyfile
{
    email admin@example.com
}

example.com {
    reverse_proxy http://127.0.0.1:8000
}
```

### 添加安全头

```caddyfile
example.com {
    reverse_proxy http://127.0.0.1:8000

    header {
        # HSTS
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        # 防止 XSS
        X-Content-Type-Options "nosniff"
        # 防止点击劫持
        X-Frame-Options "DENY"
        # CSP
        Content-Security-Policy "default-src 'self'"
    }
}
```

### 启用访问日志文件

```caddyfile
example.com {
    reverse_proxy http://127.0.0.1:8000

    log {
        output file /var/log/caddy/access.log {
            roll_size 100mb
            roll_keep 10
        }
    }
}
```

### 限流配置

```caddyfile
example.com {
    rate_limit {
        zone dynamic {
            key {remote_host}
            events 100
            window 1m
        }
    }

    reverse_proxy http://127.0.0.1:8000
}
```

## Resources

### Templates

- **assets/Caddyfile.template** - Caddyfile 配置模板
- **assets/caddy.service.template** - systemd 服务单元文件模板

### Documentation

- [Caddy 官方文档](https://caddyserver.com/docs/)
- [Caddyfile 语法参考](https://caddyserver.com/docs/caddyfile)
- [反向代理指令](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [自动 HTTPS 配置](https://caddyserver.com/docs/automatic-https)

### Maintenance

#### 查看证书信息

```bash
# 查看证书存储位置
ls -la /var/lib/caddy/caddy/certificates/

# 查看证书详情
sudo /usr/bin/caddy list-certificates
```

#### 强制续期证书

```bash
# Caddy 会自动续期，但如需手动触发：
sudo systemctl reload caddy
```

#### 更新 Caddy

```bash
# 下载新版本
cd /tmp
curl -L "https://caddyserver.com/api/download?os=linux&arch=amd64" -o caddy
chmod +x caddy

# 替换旧版本
sudo systemctl stop caddy
sudo mv caddy /usr/bin/caddy
sudo systemctl start caddy

# 验证版本
caddy version
```

#### 迁移配置

```bash
# 备份配置
sudo tar -czf caddy-backup-$(date +%Y%m%d).tar.gz \
  /etc/caddy /var/lib/caddy /etc/systemd/system/caddy.service

# 恢复配置
sudo tar -xzf caddy-backup-YYYYMMDD.tar.gz -C /
sudo systemctl daemon-reload
sudo systemctl restart caddy
```

## Best Practices

1. **部署前验证 DNS**：确保域名已解析到服务器 IP
2. **使用环境变量**：systemd 服务文件中必须设置 `XDG_DATA_HOME`
3. **最小权限原则**：使用 `www-data` 或 `caddy` 系统用户，避免 root
4. **监控日志**：首次部署后观察日志 5-10 分钟，确保证书获取成功
5. **备份证书**：证书存储在 `/var/lib/caddy`，定期备份
6. **测试重启**：部署完成后执行 `sudo reboot` 验证开机自启
7. **防火墙配置**：确保 80/443 端口对外开放（云服务器需在安全组配置）
