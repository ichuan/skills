---
name: deploy-caddy-reverse-proxy
description: "Deploy Caddy reverse proxy on remote servers with automatic SSL and systemd integration. Use when users want to: (1) Set up reverse proxy for local web services, (2) Configure automatic Let's Encrypt SSL certificates, (3) Set up systemd service with auto-start, (4) Proxy HTTP/WebSocket traffic. Triggered by phrases like 'deploy caddy', 'setup reverse proxy', 'configure caddy', 'caddy ssl'."
---

# Deploy Caddy Reverse Proxy

## Overview

Automatically deploy Caddy reverse proxy server on remote servers with:

- **Automatic SSL Management**: Let's Encrypt certificate acquisition and renewal
- **Reverse Proxy Configuration**: Route domain traffic to local services (HTTP/WebSocket)
- **Systemd Integration**: Auto-start and crash recovery
- **Smart Environment Detection**: Automatic system detection and optimal configuration

## Prerequisites

Verify before deployment:

1. **Server Access**:
   - SSH access configured (supports SSH config aliases)
   - sudo privileges
   - Internet access (for downloading Caddy and obtaining certificates)

2. **DNS Configuration**:
   - Domain points to server IP (A record or CNAME)
   - DNS must be propagated before SSL certificate can be obtained

3. **Local Service**:
   - Web service already running on server
   - Listening on 127.0.0.1 or localhost (note the port number)

## Workflow

### 1. Parameter Collection

Use `AskUserQuestion` tool to interactively collect deployment parameters:

```markdown
**Required Parameters**:
- SSH host alias or address (e.g., `dev` or `user@example.com`)
- Domain name (e.g., `app.example.com`)
- Backend service port (e.g., `8000`, `3000`)

**Optional Parameters**:
- Whether static file serving is needed (if frontend is bundled separately)
- Static file path (e.g., `/var/www/app/dist`)
- Routing rules (e.g., `/api` proxies to port A, `/ui` serves static files)
```

**Example Questions**:

```markdown
question: "How do you connect to the server?"
options:
  - label: "SSH config alias (Recommended)"
    description: "Use host alias from ~/.ssh/config, e.g., 'dev'"
  - label: "Full SSH address"
    description: "Format: user@hostname or user@ip"

question: "What is the domain name?"
header: "Domain"

question: "What port is the backend service listening on?"
header: "Backend Port"
```

### 2. Environment Detection

Connect to server and perform environment checks:

```bash
# Check if Caddy is installed
which caddy && caddy version

# Check CPU architecture (for downloading correct binary)
uname -m  # x86_64 → amd64, aarch64 → arm64

# Check operating system
cat /etc/os-release

# Check available users (prefer www-data, create caddy user if not exists)
id www-data 2>/dev/null || id caddy 2>/dev/null

# Check if backend service is running
sudo ss -tlnp | grep <backend_port>
```

**Adaptive Strategy**:
- If Caddy is installed and version >= 2.0, ask whether to reinstall or use existing version
- If `www-data` user exists, use it; otherwise create `caddy` system user
- If backend service is not running, warn user and ask whether to continue

### 3. Install Caddy

If Caddy is not installed or needs update:

```bash
# Download Caddy binary
cd /tmp
curl -L "https://caddyserver.com/api/download?os=linux&arch=<arch>" -o caddy
chmod +x caddy

# Install to system path
sudo mv caddy /usr/bin/caddy

# Verify installation
/usr/bin/caddy version
```

**Architecture Mapping**:
- `x86_64` → `amd64`
- `aarch64` → `arm64`
- `armv7l` → `armv7`

### 4. Create Necessary Directories and Users

```bash
# If using www-data user (Debian/Ubuntu default)
sudo mkdir -p /etc/caddy /var/lib/caddy
sudo chown -R www-data:www-data /etc/caddy /var/lib/caddy

# If need to create caddy user (CentOS/RHEL/others)
sudo groupadd --system caddy
sudo useradd --system --gid caddy \
  --create-home --home-dir /var/lib/caddy \
  --shell /sbin/nologin \
  --comment "Caddy web server" caddy
```

### 5. Generate Configuration Files

#### 5.1 Caddyfile

Generate configuration based on user parameters:

**Scenario A: Pure Reverse Proxy (Most Common)**

```caddyfile
example.com {
    reverse_proxy http://127.0.0.1:8000

    log {
        output stdout
    }
}
```

**Scenario B: Static Files + API Proxy**

```caddyfile
example.com {
    # Static file serving
    handle /ui/* {
        root * /var/www/app/dist
        try_files {path} /index.html
        file_server
    }

    # API reverse proxy
    handle /api/* {
        reverse_proxy http://127.0.0.1:8000
    }

    log {
        output stdout
    }
}
```

**Scenario C: Multi-Service Proxy**

```caddyfile
example.com {
    # Main application
    handle /app/* {
        reverse_proxy http://127.0.0.1:3000
    }

    # Backend API
    handle /api/* {
        reverse_proxy http://127.0.0.1:8000
    }

    # WebSocket service
    handle /ws {
        reverse_proxy http://127.0.0.1:9000
    }

    # Default route
    handle {
        reverse_proxy http://127.0.0.1:3000
    }

    log {
        output stdout
    }
}
```

Write configuration file:

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null << 'EOF'
<generated configuration>
EOF

# Validate configuration syntax
sudo /usr/bin/caddy validate --config /etc/caddy/Caddyfile
```

#### 5.2 Systemd Service File

Generate service file using `assets/caddy.service.template`:

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

**Key Configuration Notes**:

- `Type=notify`: Caddy supports systemd notification, ensuring certificate loading completes before marking as active
- `AmbientCapabilities=CAP_NET_BIND_SERVICE`: Allows non-root user to bind ports 80/443
- `Environment=XDG_DATA_HOME=/var/lib/caddy`: Certificate storage path, avoids permission issues
- `LimitNOFILE=1048576`: File descriptor limit for high-concurrency scenarios

### 6. Start Service

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable caddy

# Start service
sudo systemctl start caddy

# Wait for SSL certificate acquisition (first start needs 5-10 seconds)
sleep 5

# Check service status
sudo systemctl status caddy --no-pager
```

### 7. Verify Deployment

Perform checks to ensure successful deployment:

```bash
# 1. Check Caddy listening ports
sudo ss -tlnp | grep caddy
# Expected output: 80, 443, 2019 (admin port)

# 2. Check backend service
sudo ss -tlnp | grep <backend_port>
# Ensure backend service is running

# 3. Check certificate acquisition logs
sudo journalctl -u caddy -n 30 --no-pager | grep -E 'certificate obtained|error'
# Expected output: certificate obtained successfully

# 4. Test HTTPS access
curl -I https://<domain> -m 10
# Expected output: HTTP/2 200
```

### 8. Generate Deployment Report

Show deployment results to user:

```markdown
## ✅ Caddy Deployment Complete

### Deployment Configuration
- **Domain**: <domain>
- **Backend Service**: 127.0.0.1:<port> ✅ Running
- **SSL Certificate**: Let's Encrypt (automatically obtained)
- **Protocol Support**: HTTP/2, HTTP/3, WebSocket

### Service Status
- Caddy Version: <version>
- Listening Ports: 80 (HTTP → HTTPS), 443 (HTTPS), 2019 (admin)
- Running User: <user>
- Auto-start: Enabled

### Key File Locations
- Configuration: `/etc/caddy/Caddyfile`
- Service File: `/etc/systemd/system/caddy.service`
- Certificate Storage: `/var/lib/caddy/`
- Binary: `/usr/bin/caddy`

### Common Commands
```bash
# Check service status
sudo systemctl status caddy

# View live logs
sudo journalctl -u caddy -f

# Reload configuration (zero-downtime)
sudo systemctl reload caddy

# Restart service
sudo systemctl restart caddy

# Validate configuration syntax
sudo caddy validate --config /etc/caddy/Caddyfile
```

### Test Results
✅ HTTPS access working
✅ SSL certificate obtained successfully
✅ Reverse proxy working correctly

Your service is now accessible at `https://<domain>`!
```

## Troubleshooting

### Common Issues

#### 1. Certificate Acquisition Failure

**Error**: `storage is probably misconfigured` or `permission denied`

**Cause**: Caddy cannot write to certificate storage directory

**Solution**:

```bash
# Check environment variable configuration
sudo systemctl cat caddy | grep Environment
# Should include: Environment=XDG_DATA_HOME=/var/lib/caddy

# Check directory permissions
ls -ld /var/lib/caddy
# Should be: drwxr-xr-x www-data www-data

# Fix permissions
sudo chown -R www-data:www-data /var/lib/caddy
sudo systemctl restart caddy
```

#### 2. Port Binding Failure

**Error**: `bind: permission denied` or `address already in use`

**Cause**:
- No permission to bind ports 80/443
- Port already in use by another service

**Solution**:

```bash
# Check capabilities
sudo systemctl cat caddy | grep AmbientCapabilities
# Should include: AmbientCapabilities=CAP_NET_BIND_SERVICE

# Check port usage
sudo ss -tlnp | grep :443
# If occupied by another program, stop it or modify Caddyfile to use different port

# If system doesn't support AmbientCapabilities, manually grant permission
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/caddy
```

#### 3. DNS Resolution Failure

**Error**: `no such host` or `DNS problem: NXDOMAIN`

**Cause**: Domain not correctly pointing to server IP

**Solution**:

```bash
# Check DNS record
dig +short <domain>
# Should return server public IP

# Check server public IP
curl -4 ifconfig.me

# If DNS not propagated, wait for TTL to expire (usually 5 minutes to 1 hour)
```

#### 4. Reverse Proxy 502 Error

**Error**: Accessing domain returns 502 Bad Gateway

**Cause**: Backend service not running or incorrect listening address

**Solution**:

```bash
# Check backend service status
sudo ss -tlnp | grep <backend_port>

# Test local access
curl http://127.0.0.1:<backend_port>

# Check Caddy logs
sudo journalctl -u caddy -f

# If backend service listens on 0.0.0.0 instead of 127.0.0.1, modify Caddyfile
```

#### 5. WebSocket Connection Failure

**Error**: WebSocket handshake fails or connection interrupted

**Cause**: Caddy 2.x supports WebSocket by default, usually a backend issue

**Solution**:

```bash
# Check backend service WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: test" \
  http://127.0.0.1:<backend_port>/ws

# If special configuration needed, add to Caddyfile:
handle /ws {
    reverse_proxy http://127.0.0.1:<port> {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

## Advanced Configuration

### Multi-Domain Configuration

```caddyfile
app.example.com {
    reverse_proxy http://127.0.0.1:8000
}

api.example.com {
    reverse_proxy http://127.0.0.1:9000
}
```

### Custom SSL Certificate Email

```caddyfile
{
    email admin@example.com
}

example.com {
    reverse_proxy http://127.0.0.1:8000
}
```

### Add Security Headers

```caddyfile
example.com {
    reverse_proxy http://127.0.0.1:8000

    header {
        # HSTS
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        # Prevent XSS
        X-Content-Type-Options "nosniff"
        # Prevent clickjacking
        X-Frame-Options "DENY"
        # CSP
        Content-Security-Policy "default-src 'self'"
    }
}
```

### Enable Access Log Files

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

### Rate Limiting Configuration

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

- **assets/Caddyfile.template** - Caddyfile configuration template
- **assets/caddy.service.template** - systemd service unit file template

### Documentation

- [Caddy Official Documentation](https://caddyserver.com/docs/)
- [Caddyfile Syntax Reference](https://caddyserver.com/docs/caddyfile)
- [Reverse Proxy Directive](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Automatic HTTPS Configuration](https://caddyserver.com/docs/automatic-https)

### Maintenance

#### View Certificate Information

```bash
# View certificate storage location
ls -la /var/lib/caddy/caddy/certificates/

# View certificate details
sudo /usr/bin/caddy list-certificates
```

#### Force Certificate Renewal

```bash
# Caddy renews automatically, but to manually trigger:
sudo systemctl reload caddy
```

#### Update Caddy

```bash
# Download new version
cd /tmp
curl -L "https://caddyserver.com/api/download?os=linux&arch=amd64" -o caddy
chmod +x caddy

# Replace old version
sudo systemctl stop caddy
sudo mv caddy /usr/bin/caddy
sudo systemctl start caddy

# Verify version
caddy version
```

#### Migrate Configuration

```bash
# Backup configuration
sudo tar -czf caddy-backup-$(date +%Y%m%d).tar.gz \
  /etc/caddy /var/lib/caddy /etc/systemd/system/caddy.service

# Restore configuration
sudo tar -xzf caddy-backup-YYYYMMDD.tar.gz -C /
sudo systemctl daemon-reload
sudo systemctl restart caddy
```

## Best Practices

1. **Verify DNS Before Deployment**: Ensure domain resolves to server IP
2. **Use Environment Variables**: systemd service file must set `XDG_DATA_HOME`
3. **Principle of Least Privilege**: Use `www-data` or `caddy` system user, avoid root
4. **Monitor Logs**: Watch logs for 5-10 minutes after first deployment to ensure certificate acquisition
5. **Backup Certificates**: Certificates stored in `/var/lib/caddy`, backup regularly
6. **Test Restart**: After deployment, run `sudo reboot` to verify auto-start works
7. **Firewall Configuration**: Ensure ports 80/443 are open (cloud servers need security group configuration)
